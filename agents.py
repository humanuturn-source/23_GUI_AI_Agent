"""
agents.py
Multi-Agent LangGraph Workflow (no long-term memory):
- Router Agent (gemma2): Fast classification -> RAG_ONLY, BROWSER_AGENT, or HYBRID_RAG_BROWSER
- RAG Agent: Queries ChromaDB `serengeti_knowledge`
- Planner & Browser Agent (gemma4): Builds Playwright navigation/form/scrape plan & runs browser
- Verifier & Writer Agent (gemma4): Validates extracted data & saves run to SQLite
"""

import json
import re
import logging
from typing import TypedDict, Any, Dict
import ollama
from langgraph.graph import StateGraph, END

from ingest import get_serengeti_collection, get_embedding
from browser_agent import LocalBrowserAgent
from database import BrowserTaskDatabase

logger = logging.getLogger("BrowserMultiAgent")
ROUTER_MODEL = "gemma2"
WORKER_MODEL = "gemma4"


class AgentState(TypedDict):
    user_query: str
    route: str
    rag_context: str
    browser_plan: Dict[str, Any]
    browser_result: Dict[str, Any]
    verification_notes: str
    final_response: str


class SerengetiBrowserMultiAgent:
    def __init__(self, db: BrowserTaskDatabase, headless: bool = False) -> None:
        self.db = db
        self.browser = LocalBrowserAgent(headless=headless)
        self.serengeti_col = get_serengeti_collection()
        self.graph = self._build_graph()

    def _chat(self, model: str, system_prompt: str, user_prompt: str) -> str:
        res = ollama.chat(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            options={"temperature": 0.1},
        )
        return res["message"]["content"].strip()

    def _query_serengeti_rag(self, query: str, top_k: int = 5) -> str:
        try:
            count = self.serengeti_col.count()
            if count == 0:
                return "ChromaDB collection 'serengeti_knowledge' is empty. Run ingest.py first."
            results = self.serengeti_col.query(
                query_embeddings=[get_embedding(query)],
                n_results=min(top_k, count),
            )
            docs = results.get("documents", [[]])[0]
            return "\n---\n".join(docs) if docs else "No matching Serengeti context found."
        except Exception as exc:
            return f"RAG lookup error: {exc}"

    def _build_graph(self) -> Any:
        workflow = StateGraph(AgentState)

        workflow.add_node("router_agent", self.node_router)
        workflow.add_node("rag_agent", self.node_rag)
        workflow.add_node("browser_agent", self.node_browser)
        workflow.add_node("verifier_agent", self.node_verifier)

        workflow.set_entry_point("router_agent")
        workflow.add_conditional_edges(
            "router_agent",
            lambda s: s["route"],
            {
                "RAG_ONLY": "rag_agent",
                "BROWSER_AGENT": "browser_agent",
                "HYBRID_RAG_BROWSER": "rag_agent",
            },
        )
        workflow.add_conditional_edges(
            "rag_agent",
            lambda s: "browser_agent" if s["route"] == "HYBRID_RAG_BROWSER" else "verifier_agent",
            {
                "browser_agent": "browser_agent",
                "verifier_agent": "verifier_agent",
            },
        )
        workflow.add_edge("browser_agent", "verifier_agent")
        workflow.add_edge("verifier_agent", END)

        return workflow.compile()

    def node_router(self, state: AgentState) -> Dict[str, Any]:
        q = state["user_query"]
        prompt = (
            "Classify the request into EXACTLY ONE label:\n"
            "- RAG_ONLY: Question only about Serengeti ecology/wildlife from local docs.\n"
            "- BROWSER_AGENT: Task requires opening a URL, searching a website, filling a form, or scraping a live page.\n"
            "- HYBRID_RAG_BROWSER: Uses Serengeti knowledge AND searches/scrapes/fills a form on a website.\n"
            "Return ONLY the label."
        )
        raw = self._chat(ROUTER_MODEL, prompt, q).upper()
        if "HYBRID" in raw:
            route = "HYBRID_RAG_BROWSER"
        elif "BROWSER" in raw or "http" in q.lower() or "scrape" in q.lower() or "search" in q.lower():
            route = "BROWSER_AGENT"
        else:
            route = "RAG_ONLY"

        logger.info(f"[ROUTER - {ROUTER_MODEL}] -> {route}")
        return {"route": route}

    def node_rag(self, state: AgentState) -> Dict[str, Any]:
        logger.info("[RAG AGENT] Querying Serengeti ChromaDB...")
        ctx = self._query_serengeti_rag(state["user_query"], top_k=5)
        return {"rag_context": ctx}

    def node_browser(self, state: AgentState) -> Dict[str, Any]:
        logger.info(f"[BROWSER AGENT - {WORKER_MODEL}] Planning & executing Playwright task...")

        # Strip accidental outer quotes from chat prompts so JSON planning stays clean
        cleaned_query = state["user_query"].strip()
        if len(cleaned_query) >= 2 and cleaned_query[0] == cleaned_query[-1] and cleaned_query[0] in ('"', "'"):
            cleaned_query = cleaned_query[1:-1].strip()

        plan_prompt = (
            "Convert the user request and optional RAG context into a JSON object for Playwright:\n"
            '{"url": "https://...", "search_selector": null or CSS selector, '
            '"search_text": null or string, "submit_selector": null or CSS selector, '
            '"extra_selectors": [{"selector": "#field_id", "value": "text"}] or []}\n'
            "Rules:\n"
            "- Put form fields (such as #item_name, #quantity, etc.) in extra_selectors.\n"
            "- Put the submit button CSS selector (such as #submit_btn) in submit_selector.\n"
            "- If no specific URL is given, default to https://en.wikipedia.org/wiki/Serengeti.\n"
            "Return ONLY valid JSON."
        )

        raw_plan = self._chat(
            WORKER_MODEL,
            plan_prompt,
            f"Query: {cleaned_query}\nRAG Context: {state.get('rag_context', '')[:1200]}",
        )

        plan: Dict[str, Any] = {
            "url": "https://en.wikipedia.org/wiki/Serengeti",
            "search_selector": None,
            "search_text": None,
            "submit_selector": None,
            "extra_selectors": [],
        }

        match = re.search(r"\{.*\}", raw_plan, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, dict):
                    plan.update({k: v for k, v in parsed.items() if k in plan})
            except json.JSONDecodeError as exc:
                logger.warning(f"[BROWSER AGENT] Failed to parse plan JSON: {exc} | raw={raw_plan!r}")

        extra = plan.get("extra_selectors")
        if not isinstance(extra, list):
            extra = []
        else:
            # Keep only valid dict entries with non-empty selector
            extra = [
                {
                    "selector": str(item.get("selector", "")).strip(),
                    "value": "" if item.get("value") is None else str(item.get("value")),
                }
                for item in extra
                if isinstance(item, dict) and str(item.get("selector", "")).strip()
            ]

        submit_selector = plan.get("submit_selector")
        if isinstance(submit_selector, str):
            submit_selector = submit_selector.strip() or None
        else:
            submit_selector = None

        # Fallback if the user asked to click #submit_btn or filled form inputs without setting submit_selector
        if not submit_selector and (extra or "submit_btn" in cleaned_query or "click #submit_btn" in cleaned_query.lower()):
            submit_selector = "#submit_btn"

        plan["extra_selectors"] = extra
        plan["submit_selector"] = submit_selector
        logger.info(f"[BROWSER AGENT] Final plan: {json.dumps(plan)}")

        result = self.browser.execute_web_task(
            url=plan["url"],
            search_selector=plan.get("search_selector"),
            search_text=plan.get("search_text"),
            submit_selector=plan.get("submit_selector"),
            extra_selectors=plan.get("extra_selectors", []),
        )
        return {"browser_plan": plan, "browser_result": result}


    def node_verifier(self, state: AgentState) -> Dict[str, Any]:
        logger.info(f"[VERIFIER AGENT - {WORKER_MODEL}] Synthesizing & persisting to SQLite...")
        b_res = state.get("browser_result") or {}
        rag_ctx = state.get("rag_context") or "N/A"

        synth_prompt = (
            "You are a factual AI verifier and synthesizer. Ground your answer strictly in the "
            "provided Serengeti RAG context and/or live browser extraction. Be clear and concise."
        )
        user_payload = (
            f"User Query: {state['user_query']}\n"
            f"Serengeti RAG Context:\n{rag_ctx}\n\n"
            f"Browser URL: {b_res.get('url', 'N/A')}\n"
            f"Browser Title: {b_res.get('title', 'N/A')}\n"
            f"Browser Error: {b_res.get('error', 'None')}\n"
            f"Extracted Page Text:\n{b_res.get('extracted_text', 'N/A')[:2500]}"
        )
        answer = self._chat(WORKER_MODEL, synth_prompt, user_payload)
        verification_notes = (
            f"Route={state['route']} | BrowserError={b_res.get('error') or 'None'}"
        )

        if state["route"] in ("BROWSER_AGENT", "HYBRID_RAG_BROWSER"):
            self.db.save_run(
                query=state["user_query"],
                target_url=b_res.get("url", ""),
                page_title=b_res.get("title", ""),
                extracted_text=b_res.get("extracted_text", "")[:2000],
                verification_notes=verification_notes,
                status="FAILED" if b_res.get("error") else "COMPLETED",
            )

        return {
            "verification_notes": verification_notes,
            "final_response": answer,
        }

    def run(self, user_query: str) -> str:
        initial: AgentState = {
            "user_query": user_query,
            "route": "",
            "rag_context": "",
            "browser_plan": {},
            "browser_result": {},
            "verification_notes": "",
            "final_response": "",
        }
        out = self.graph.invoke(initial)
        return out["final_response"]

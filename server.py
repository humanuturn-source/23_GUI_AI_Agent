"""
server.py
OpenAI-Compatible FastAPI Backend for Open WebUI (Docker -> Mac Mini host).
Routes prompts to the Serengeti Browser Multi-Agent workflow and exposes SQLite run history.
"""

import sys
import logging
from typing import List, Any, Dict
from fastapi import FastAPI
from pydantic import BaseModel

from database import BrowserTaskDatabase
from agents import SerengetiBrowserMultiAgent

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
logger = logging.getLogger("BrowserAgentServer")

app = FastAPI(title="Local Browser Automation & Serengeti RAG Server")

db = BrowserTaskDatabase()
agent_system = SerengetiBrowserMultiAgent(db=db, headless=False)


class ChatMessage(BaseModel):
    role: str
    content: Any


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]


@app.get("/v1/models")
def list_models() -> dict:
    return {
        "object": "list",
        "data": [
            {
                "id": "serengeti-browser-agent",
                "object": "model",
                "owned_by": "local-mac-mini",
            }
        ],
    }


@app.get("/runs/recent")
def recent_runs() -> dict:
    return {"recent_browser_runs": db.get_recent_runs(limit=10)}


@app.post("/v1/chat/completions")
def chat_completions(request: ChatCompletionRequest) -> dict:
    normalized: List[Dict[str, str]] = []
    for m in request.messages:
        if isinstance(m.content, str):
            txt = m.content
        elif isinstance(m.content, list):
            txt = "".join(p.get("text", "") for p in m.content if isinstance(p, dict))
        else:
            txt = str(m.content)
        normalized.append({"role": m.role, "content": txt})

    user_query = next(
        (m["content"] for m in reversed(normalized) if m["role"] == "user"), ""
    )

    if "### Task:" in user_query and (
        "Generate a concise" in user_query or "Suggest 3-5 relevant" in user_query
    ):
        return {
            "id": "chatcmpl-meta",
            "object": "chat.completion",
            "model": request.model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Browser Agent Session"},
                    "finish_reason": "stop",
                }
            ],
        }

    reply = agent_system.run(user_query)
    return {
        "id": "chatcmpl-browser-agent",
        "object": "chat.completion",
        "model": request.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": reply},
                "finish_reason": "stop",
            }
        ],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

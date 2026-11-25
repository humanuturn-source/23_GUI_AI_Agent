import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.sync_api import sync_playwright


class LocalBrowserAgent:
    """Local Playwright browser & GUI automation agent running on the host machine."""

    def __init__(self, screenshots_dir: str = "data/screenshots", headless: bool = False):
        self.screenshots_dir = Path(screenshots_dir)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.headless = headless

    def _human_pause(self, min_sec: float = 0.2, max_sec: float = 0.6) -> None:
        time.sleep(random.uniform(min_sec, max_sec))

    def _fill_field(self, page: Any, selector: str, value: str) -> None:
        locator = page.locator(selector).first
        locator.wait_for(state="visible", timeout=5000)
        locator.click()
        self._human_pause(0.15, 0.35)
        locator.fill("")
        if value:
            locator.type(str(value), delay=random.randint(25, 65))

    def execute_web_task(
        self,
        url: str,
        search_selector: Optional[str] = None,
        search_text: Optional[str] = None,
        submit_selector: Optional[str] = None,
        extra_selectors: Optional[List[Dict[str, str]]] = None,
        press_enter: bool = False,
    ) -> Dict[str, Any]:
        extra_selectors = extra_selectors or []
        timestamp = int(time.time())
        before_screenshot = str(self.screenshots_dir / f"before_{timestamp}.png")
        after_screenshot = str(self.screenshots_dir / f"after_{timestamp}.png")

        result: Dict[str, Any] = {
            "url": url,
            "final_url": url,
            "title": "",
            "extracted_text": "",
            "before_screenshot": before_screenshot,
            "after_screenshot": after_screenshot,
            "actions_taken": [],
            "success": False,
            "error": None,
        }

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=self.headless,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                    ],
                )
                context = browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/131.0.0.0 Safari/537.36"
                    ),
                )
                context.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
                )

                page = context.new_page()
                page.set_default_timeout(10000)

                page.goto(url, wait_until="domcontentloaded")
                try:
                    page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:
                    pass
                self._human_pause(0.3, 0.7)

                page.screenshot(path=before_screenshot, full_page=False)
                result["actions_taken"].append(f"navigated_to:{url}")

                if search_selector and search_text is not None:
                    self._fill_field(page, search_selector, str(search_text))
                    result["actions_taken"].append(f"filled:{search_selector}={search_text}")
                    if press_enter and not submit_selector:
                        page.locator(search_selector).first.press("Enter")
                        result["actions_taken"].append(f"pressed_enter:{search_selector}")

                for item in extra_selectors:
                    if not isinstance(item, dict):
                        continue
                    selector = str(item.get("selector", "")).strip()
                    value = "" if item.get("value") is None else str(item.get("value"))
                    if not selector:
                        continue
                    self._fill_field(page, selector, value)
                    result["actions_taken"].append(f"filled:{selector}={value}")

                if submit_selector:
                    btn = page.locator(submit_selector).first
                    if btn.count() == 0:
                        btn = page.locator(
                            "button[type='submit'], input[type='submit'], button"
                        ).first
                    btn.wait_for(state="visible", timeout=5000)
                    self._human_pause(0.2, 0.5)
                    btn.click()
                    result["actions_taken"].append(f"clicked:{submit_selector}")

                    try:
                        page.wait_for_load_state("networkidle", timeout=5000)
                    except Exception:
                        pass
                    page.wait_for_timeout(600)

                # Gentle scroll to trigger dynamic sections and return to top
                page.evaluate("window.scrollTo(0, Math.min(document.body.scrollHeight, 400))")
                self._human_pause(0.2, 0.4)
                page.evaluate("window.scrollTo(0, 0)")

                page.screenshot(path=after_screenshot, full_page=False)
                result["final_url"] = page.url
                result["title"] = page.title()

                body_text = page.locator("body").inner_text().strip()
                result["extracted_text"] = body_text[:6000]
                result["success"] = True

                context.close()
                browser.close()

        except Exception as exc:
            result["error"] = str(exc)
            result["actions_taken"].append(f"error:{exc}")

        return result

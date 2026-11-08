"""Browser Automation Tools — Playwright-based web interaction for ChemAI.

Provides: browse_navigate, browse_read, browse_click, browse_input, browse_screenshot.
Concurrency-safe via asyncio.Lock. Idle cleanup after 60s.
"""
import asyncio
import json
import logging
import base64

logger = logging.getLogger(__name__)

# Module-level browser pool with asyncio.Lock for concurrency safety.
_browser_lock = asyncio.Lock()
_browser_instance = None
_page_instance = None
_last_used: float = 0
IDLE_TIMEOUT = 60  # seconds


async def _get_page():
    """Get or create a Playwright page instance. Lazy init + idle timeout cleanup."""
    global _browser_instance, _page_instance, _last_used
    now = asyncio.get_event_loop().time()

    async with _browser_lock:
        if _browser_instance and (now - _last_used) > IDLE_TIMEOUT:
            await _cleanup()

        if not _browser_instance:
            from playwright.async_api import async_playwright
            pw = await async_playwright().start()
            _browser_instance = await pw.chromium.launch(headless=True)
            _page_instance = await _browser_instance.new_page()
            logger.info("[Browser] Chrome launched (headless)")

        _last_used = now
        return _page_instance


async def _cleanup():
    """Close browser and page, reset globals."""
    global _browser_instance, _page_instance
    try:
        if _page_instance:
            await _page_instance.close()
        if _browser_instance:
            await _browser_instance.close()
    except Exception:
        pass
    _browser_instance = None
    _page_instance = None
    logger.info("[Browser] Cleaned up")


# ── Tool Functions ──

async def browse_navigate(url: str, wait_until: str = "networkidle") -> str:
    """浏览器导航 — 打开指定 URL 并等待页面加载完成。

    何时用：需要打开一个具体网页查看内容。参数 url 为完整 URL（含 https://）。
    会发生什么：加载页面，等待网络空闲，返回页面标题和文字内容。
    下一步：使用 browse_read 读取内容，或 browse_click 点击链接。
    NOT for 搜索信息 — 先用 web_search 获取 URL，再用此工具打开"""
    if not url.startswith("http"):
        url = "https://" + url
    try:
        page = await _get_page()
        await page.goto(url, wait_until=wait_until, timeout=30000)
        title = await page.title()
        return json.dumps({
            "title": title,
            "url": page.url,
            "text": (await page.inner_text("body"))[:8000],
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e), "url": url, "timeout": "timeout" in str(e).lower()}, ensure_ascii=False)


async def browse_read(selector: str = "body") -> str:
    """浏览器阅读 — 读取页面或指定元素的文字内容。

    何时用：浏览页面后需要提取网页上的文字信息。
    会发生什么：获取指定 CSS selector 的内部文本，截断到 8000 字符。
    下一步：基于内容回答用户问题。
    配合 browse_navigate 使用，不要单独调用此工具。"""
    try:
        page = await _get_page()
        text = await page.inner_text(selector)
        return json.dumps({"selector": selector, "text": text[:8000]}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e), "selector": selector}, ensure_ascii=False)


async def browse_click(selector: str) -> str:
    """浏览器点击 — 点击页面上的元素（按钮、链接等）。

    何时用：浏览页面后需要点击按钮、翻页链接、提交表单等。
    会发生什么：点击指定元素，等待 0.5s，返回点击前后的 URL 和页面标题。
    下一步：使用 browse_read 读取新页面内容。
    配合 browse_navigate 使用，不要单独调用此工具。"""
    try:
        page = await _get_page()
        before_url = page.url
        await page.click(selector, timeout=10000)
        await asyncio.sleep(0.5)
        after_url = page.url
        title = await page.title()
        return json.dumps({
            "clicked": selector,
            "before": before_url,
            "after": after_url,
            "title": title,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e), "selector": selector}, ensure_ascii=False)


async def browse_input(selector: str, text: str) -> str:
    """浏览器输入 — 在输入框中输入文本。

    何时用：浏览页面后需要在搜索框、表单中填入文字。
    会发生什么：清空指定输入框并填入文本。
    下一步：配合 browse_click 点击搜索/提交按钮。
    配合 browse_navigate 使用，不要单独调用此工具。"""
    try:
        page = await _get_page()
        await page.fill(selector, text, timeout=10000)
        return json.dumps({"input": selector, "text": text, "done": True}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e), "selector": selector}, ensure_ascii=False)


async def browse_screenshot(selector: str = "body") -> str:
    """浏览器截图 — 截取页面或指定元素的可视化截图。

    何时用：浏览页面后用户需要看到页面的视觉呈现。
    会发生什么：截取页面或元素的 PNG 截图，返回 base64 编码图片。
    下一步：将截图展示给用户。
    配合 browse_navigate 使用，不要单独调用此工具。"""
    try:
        page = await _get_page()
        if selector == "body":
            screenshot = await page.screenshot(full_page=False, type="png")
        else:
            el = await page.query_selector(selector)
            screenshot = await el.screenshot(type="png") if el else b""
        return json.dumps({
            "screenshot": base64.b64encode(screenshot).decode(),
            "type": "png",
            "selector": selector,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e), "selector": selector}, ensure_ascii=False)

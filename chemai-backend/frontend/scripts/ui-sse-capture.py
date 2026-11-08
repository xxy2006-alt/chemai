# ui-sse-capture.py — 捕获真实出题 SSE 原始 payload，检查反斜杠
from playwright.sync_api import sync_playwright
import json

BASE = "http://127.0.0.1:8001"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    captured = []
    pg.on("response", lambda r: None)
    # 用 page 脚本劫持 fetch 捕获 SSE 流文本
    pg.add_init_script(
        """
        window.__sseCapture = [];
        const origFetch = window.fetch;
        window.fetch = async (...args) => {
          const resp = await origFetch(...args);
          if (typeof args[0] === 'string' && args[0].includes('/api/agent/chat/langgraph/stream')) {
            const clone = resp.clone();
            const text = await clone.text();
            window.__sseCapture.push(text);
          }
          return resp;
        };
        """
    )
    pg.goto(BASE + "/#/login", wait_until="networkidle")
    pg.fill("input[placeholder='请输入账号']", "hai")
    pg.fill("input[type=password]", "hai123456")
    pg.click("button[type=submit]")
    pg.wait_for_timeout(2500)
    pg.click("button:has-text('新建对话')")
    pg.wait_for_timeout(800)

    pg.fill("textarea", "请出一道关于化学平衡的题目，内容包含可逆反应符号")
    pg.click("button:has-text('发送')")
    for _ in range(60):
        pg.wait_for_timeout(2000)
        if not pg.evaluate("() => !!document.querySelector('main textarea')?.disabled"):
            break
    pg.wait_for_timeout(1000)

    # 提取 SSE 文本里 tool_result 事件中的 result 字段（原始 JSON）
    dump = pg.evaluate(
        """() => {
          const raw = window.__sseCapture.join('');
          const events = raw.split('\\n').filter(l => l.startsWith('data: ') && !l.includes('[DONE]'));
          const results = [];
          for (const l of events) {
            try {
              const ev = JSON.parse(l.slice(6));
              if (ev.type === 'tool_result' && typeof ev.result === 'string') {
                results.push(ev.result.slice(0, 600));
              }
            } catch (e) {}
          }
          return { eventCount: events.length, results };
        }"""
    )
    print("capture:", json.dumps(dump, ensure_ascii=True)[:1800])
    b.close()

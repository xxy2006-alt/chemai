# ui-timer-test.py — 验证气泡内 live-timer 实时跳动
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8001"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto(BASE + "/#/login", wait_until="networkidle")
    pg.fill("input[placeholder='请输入账号']", "hai")
    pg.fill("input[type=password]", "hai123456")
    pg.click("button[type=submit]")
    pg.wait_for_timeout(2500)
    pg.click("button:has-text('新建对话')")
    pg.wait_for_timeout(600)

    pg.fill("textarea", "你好")
    pg.click("button:has-text('发送')")
    pg.wait_for_timeout(1200)

    # 取气泡内计时器文本两次，验证在跳动
    t1 = pg.evaluate(
        "() => { const el = document.querySelector('.live-timer.ticking'); return el ? el.textContent : null }"
    )
    pg.wait_for_timeout(900)
    t2 = pg.evaluate(
        "() => { const el = document.querySelector('.live-timer.ticking'); return el ? el.textContent : null }"
    )
    print("timer t1:", t1, "| t2:", t2, "| ticking:", t1 is not None and t1 != t2)
    pg.screenshot(path="docs/ui-review/16-agent-live-timer.png")
    b.close()

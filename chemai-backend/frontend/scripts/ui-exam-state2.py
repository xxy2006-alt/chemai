# ui-exam-state2.py — 逐步跟踪：历史真题库 → 试卷按钮 → 弹窗
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
    pg.goto(BASE + "/#/exam", wait_until="networkidle")
    pg.wait_for_timeout(3500)

    pg.click("button:has-text('历史真题库')")
    pg.wait_for_timeout(3500)
    s1 = pg.evaluate("() => ({ paperBtns: [...document.querySelectorAll('main button')].filter(b => /全国卷|上海卷|北京卷/.test(b.textContent)).length, len: document.body.innerText.length })")
    print("1. 点标签后:", s1)

    pg.evaluate("() => { const btns=[...document.querySelectorAll('main button')].filter(b => /全国卷/.test(b.textContent) && /\\d+\\s*题/.test(b.textContent)); if (btns.length) btns[0].click(); }")
    pg.wait_for_timeout(3500)
    s2 = pg.evaluate("() => ({ dialog: !!document.querySelector('[role=dialog]'), len: document.body.innerText.length })")
    print("2. 点试卷后:", s2)
    b.close()

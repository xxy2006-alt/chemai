# ui-exam-state.py — 转储出题工作台状态
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8001"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    errs = []
    pg.on("console", lambda m: errs.append(f"[{m.type}] {m.text[:100]}"))
    pg.on("pageerror", lambda e: errs.append(f"[PAGEERROR] {str(e)[:150]}"))
    pg.goto(BASE + "/#/login", wait_until="networkidle")
    pg.fill("input[placeholder='请输入账号']", "hai")
    pg.fill("input[type=password]", "hai123456")
    pg.click("button[type=submit]")
    pg.wait_for_timeout(2500)
    pg.goto(BASE + "/#/exam", wait_until="networkidle")
    pg.wait_for_timeout(4000)
    state = pg.evaluate(
        """() => ({
          tabs: [...document.querySelectorAll('main button')].filter(b => /历史真题库|题库管理|考试列表/.test(b.textContent)).map(b => b.textContent.trim()),
          bodyLen: document.body.innerText.length,
          rootChildren: document.getElementById('root').children.length,
        })"""
    )
    print("exam state:", state)
    print("logs:", errs[:6])
    b.close()

# ui-debug.py — 调试后端模式下 /class 空白问题
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8001"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    logs = []
    pg.on("console", lambda m: logs.append(f"[{m.type}] {m.text[:200]}"))
    pg.on("pageerror", lambda e: logs.append(f"[PAGEERROR] {str(e)[:300]}"))
    pg.on("requestfailed", lambda r: logs.append(f"[REQFAIL] {r.url[:120]} {r.failure}"))

    pg.goto(BASE + "/#/login", wait_until="networkidle")
    pg.fill("input[placeholder='请输入账号']", "hai")
    pg.fill("input[type=password]", "hai123456")
    pg.click("button[type=submit]")
    pg.wait_for_timeout(2500)
    pg.goto(BASE + "/#/class", wait_until="networkidle")
    pg.wait_for_timeout(3000)

    state = pg.evaluate(
        """() => ({
          htmlLen: document.body.innerHTML.length,
          textLen: document.body.innerText.length,
          skeletons: document.querySelectorAll('.animate-pulse').length,
          rootChildren: document.getElementById('root').children.length,
          firstText: document.body.innerText.slice(0, 80)
        })"""
    )
    print("state:", state)
    print("---- logs ----")
    for l in logs[:25]:
        print(l)
    b.close()

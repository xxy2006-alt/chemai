# ui-variant-debug.py — 转储工作台 AI 生成区按钮
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
    pg.wait_for_timeout(3000)

    dump = pg.evaluate(
        """() => {
          const btns = [...document.querySelectorAll('main button')].map(b => b.textContent.trim().slice(0, 24));
          const tab = [...document.querySelectorAll('main button')].filter(b => /AI 生成|手动录入|OCR 上传/.test(b.textContent)).map(b => b.textContent.trim());
          return { tabCount: tab, allBtns: btns.slice(0, 30) };
        }"""
    )
    print("dump:", dump)
    b.close()

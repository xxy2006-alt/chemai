# ui-nocount.py — 验证试卷行不再显示题数
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
    pg.wait_for_timeout(2500)
    pg.click("button:has-text('历史真题库')")
    pg.wait_for_timeout(2500)

    rows = pg.evaluate(
        """() => {
          const btns = [...document.querySelectorAll('main button')].filter(b => /卷/.test(b.textContent));
          const withCount = btns.filter(b => /\\d+\\s*题/.test(b.textContent)).length;
          const sample = btns.slice(0, 4).map(b => b.textContent.trim());
          return { total: btns.length, withCount, sample };
        }"""
    )
    print("rows:", rows)
    pg.screenshot(path="docs/ui-review/26-no-count.png")
    b.close()

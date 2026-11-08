# ui-exam-audit.py — 出题工作台现状审计：题型区/控件清单
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

    dump = pg.evaluate(
        """() => {
          const card = [...document.querySelectorAll('main .border')].find(el => el.textContent.includes('题型与数量'));
          if (!card) return { noTypesSection: true, mainText: document.body.innerText.slice(0, 200) };
          const chips = [...card.querySelectorAll('button')].filter(b => /题/.test(b.textContent) && !/生成/.test(b.textContent)).map(b => b.textContent.trim().slice(0, 12));
          const controls = [...card.querySelectorAll('button')].map(b => b.textContent.trim().slice(0, 12)).filter(Boolean);
          return { chips, controls };
        }"""
    )
    print("audit:", dump)
    b.close()

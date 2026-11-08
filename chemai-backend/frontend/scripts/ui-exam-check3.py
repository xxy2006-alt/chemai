# ui-exam-check3.py — 重查出题工作台控件
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
    pg.wait_for_timeout(6000)
    r = pg.evaluate(
        """() => {
          const cards = [...document.querySelectorAll('main .border')].map(el => el.textContent.slice(0, 30));
          const btns = [...document.querySelectorAll('main button')].map(b => b.textContent.trim().slice(0, 10)).filter(Boolean);
          return { cardCount: cards.length, cards: cards.slice(0, 6), btns: btns.slice(0, 30) };
        }"""
    )
    print("R:", r)
    b.close()

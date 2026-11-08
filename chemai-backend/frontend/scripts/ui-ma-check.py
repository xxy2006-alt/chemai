# ui-ma-check.py — 定位 mathnormal">ma 命中的上下文
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
    pg.evaluate(
        "() => { const btns=[...document.querySelectorAll('main button')].filter(b => /全国卷/.test(b.textContent) && /\\d+\\s*题/.test(b.textContent)); if (btns.length) btns[0].click(); }"
    )
    pg.wait_for_timeout(3000)

    hits = pg.evaluate(
        """() => {
          const dlg = document.querySelector('[role=dialog]');
          const out = [];
          for (const el of dlg.querySelectorAll('.mord.mathnormal')) {
            const t = el.textContent;
            if (t === 'ma' || t === 'th' || t === 'rm' || t === 'ath' || t === 'math') {
              const card = el.closest('.border, td, p');
              out.push({ t, ctx: (card ? card.textContent.slice(0, 80) : '').replace(/\\s+/g, ' ') });
            }
          }
          return out.slice(0, 8);
        }"""
    )
    print("hits:", hits)
    b.close()

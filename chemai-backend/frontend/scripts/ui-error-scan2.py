# ui-error-scan2.py — 剩余错误 + mathrm 字母残留位置
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

    info = pg.evaluate(
        """() => {
          const dlg = document.querySelector('[role=dialog]');
          const errors = [...dlg.querySelectorAll('.katex-error')].map(e => e.textContent.slice(0, 150));
          // mathrm 字母残留：找 mathnormal 里的 'ma' 片段及其所在最近卡片
          const hits = [];
          const all = dlg.querySelectorAll('.katex-html .mord');
          for (const el of all) {
            if (el.textContent === 'ma' || el.textContent === 'th' || el.textContent === 'rm') {
              const card = el.closest('.border, td');
              hits.push({ t: el.textContent, ctx: card ? card.textContent.slice(0, 60) : '' });
            }
          }
          return { errors, mathrmHits: hits.slice(0, 6) };
        }"""
    )
    print("scan2:", info)
    b.close()

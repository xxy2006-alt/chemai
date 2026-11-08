# ui-error-scan.py — 提取弹窗内全部 katex-error 的源码与位置
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

    errs = pg.evaluate(
        """() => {
          const dlg = document.querySelector('[role=dialog]');
          if (!dlg) return [];
          return [...dlg.querySelectorAll('.katex-error')].map(e => ({
            title: e.getAttribute('title') ? e.getAttribute('title').slice(0, 120) : '',
            text: e.textContent.slice(0, 120),
            ctx: (e.closest('td, .border, p') || {}).textContent ? (e.closest('td, .border, p') || {}).textContent.slice(0, 60) : ''
          }));
        }"""
    )
    print("katex errors:", len(errs))
    for e in errs:
        print("  T:", e["title"].encode("unicode_escape").decode()[:140])
        print("  X:", e["text"].encode("unicode_escape").decode()[:140])
    b.close()

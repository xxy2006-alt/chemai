# ui-panel-geo.py — 触发内联面板并测量几何（顶部可见性 + 内部滚动）
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
    pg.click("button:has-text('新建对话')")
    pg.wait_for_timeout(800)

    pg.fill("textarea", "请帮我出3道关于氧化还原反应的题目")
    pg.click("button:has-text('发送')")
    for _ in range(60):
        pg.wait_for_timeout(2000)
        if not pg.evaluate("() => !!document.querySelector('main textarea')?.disabled"):
            break
    pg.wait_for_timeout(1500)

    dump = pg.evaluate(
        """() => {
          const panels = [...document.querySelectorAll('[data-panel]')];
          if (!panels.length) {
            const card = document.querySelector('main textarea')?.closest('.flex.flex-col.overflow-hidden');
            const area = card ? card.querySelector('.overflow-y-auto') : null;
            return { panels: 0, tail: area ? area.innerText.slice(-150) : 'no-area' };
          }
          const el = panels[0];
          const r = el.getBoundingClientRect();
          const inner = el.querySelector('.overflow-y-auto');
          return {
            panels: panels.length,
            panelTop: Math.round(r.top), panelH: Math.round(r.height),
            viewportH: window.innerHeight,
            internalScroll: inner ? { sh: inner.scrollHeight, ch: inner.clientHeight } : null,
            visiblePart: Math.round(Math.min(r.bottom, window.innerHeight) - Math.max(r.top, 0)),
          };
        }"""
    )
    print("geo:", dump)
    pg.screenshot(path="docs/ui-review/23-panel-geo.png")
    b.close()

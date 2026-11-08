# ui-panel-probe.py — 探测内联面板实际渲染状态
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

    pg.fill("textarea", "请打开出题工作台，帮我出题")
    pg.click("button:has-text('发送')")
    for _ in range(50):
        pg.wait_for_timeout(2000)
        if not pg.evaluate("() => !!document.querySelector('main textarea')?.disabled"):
            break
    pg.wait_for_timeout(1500)

    dump = pg.evaluate(
        """() => {
          const area=[...document.querySelectorAll('main .overflow-y-auto')].find(el => el.innerText.length>300);
          if (!area) return { noArea: true };
          const tail = area.innerText.slice(-600);
          const tealHeaders = [...area.querySelectorAll('div')].filter(d => d.className && d.className.includes('text-teal') && d.textContent.length < 20).map(d => d.textContent.trim());
          const panels = document.querySelectorAll('[data-panel]').length;
          const kpChips = [...area.querySelectorAll('button')].filter(b => /盐类|电离|氧化|平衡|元素/.test(b.textContent)).length;
          return { panels, tealHeaders, kpChips, tail: tail.slice(-300) };
        }"""
    )
    print("probe:", dump)
    pg.screenshot(path="docs/ui-review/21-panel-probe.png")
    b.close()

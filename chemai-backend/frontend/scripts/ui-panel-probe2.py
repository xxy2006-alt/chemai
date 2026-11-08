# ui-panel-probe2.py — 精确定位消息区（含 textarea 的卡片内的滚动容器）
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

    pg.fill("textarea", "请打开出题工作台")
    pg.click("button:has-text('发送')")
    for _ in range(50):
        pg.wait_for_timeout(2000)
        if not pg.evaluate("() => !!document.querySelector('main textarea')?.disabled"):
            break
    pg.wait_for_timeout(1500)

    dump = pg.evaluate(
        """() => {
          // 消息区 = 含 textarea 的聊天卡片内的滚动容器
          const card = document.querySelector('main textarea')?.closest('.flex.flex-col.overflow-hidden');
          const area = card ? card.querySelector('.overflow-y-auto') : null;
          if (!area) return { noArea: true };
          const panels = document.querySelectorAll('[data-panel]').length;
          const panelInfo = [...document.querySelectorAll('[data-panel]')].map(el => {
            const r = el.getBoundingClientRect();
            return { top: Math.round(r.top), h: Math.round(r.height), vis: Math.round(Math.min(r.bottom, window.innerHeight) - Math.max(r.top, 0)) };
          });
          const tail = area.innerText.slice(-200);
          return {
            panels, panelInfo,
            areaScrollH: area.scrollHeight, areaClientH: area.clientHeight,
            tailHasWorkbench: area.innerText.includes('出题工作台'),
          };
        }"""
    )
    print("probe2:", dump)
    pg.screenshot(path="docs/ui-review/22-panel-probe2.png")
    b.close()

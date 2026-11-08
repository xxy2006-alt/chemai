# ui-bug1-verify.py — 精确定位消息区验证旧消息保留
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

    def send_and_wait(text):
        pg.fill("textarea", text)
        pg.click("button:has-text('发送')")
        for _ in range(60):
            pg.wait_for_timeout(2000)
            if not pg.evaluate("() => !!document.querySelector('main textarea')?.disabled"):
                break
        pg.wait_for_timeout(1000)

    send_and_wait("第一轮：请介绍氧化还原反应的概念")
    send_and_wait("第二轮：请配平 Fe2O3 + 3CO = 2Fe + 3CO2")

    dump = pg.evaluate(
        """() => {
          const card = document.querySelector('main textarea')?.closest('.flex.flex-col.overflow-hidden');
          const area = card ? card.querySelector('.overflow-y-auto') : null;
          if (!area) return { noArea: true };
          const t = area.innerText;
          // 用户气泡（self-end 深蓝气泡）计数与内容
          const userBubbles = [...area.querySelectorAll('div')].filter(d => d.className && d.className.includes('self-end') && d.className.includes('bg-primary')).map(d => d.textContent.slice(0, 20));
          return {
            userBubbles,
            hasFirst: t.includes('第一轮'),
            hasSecond: t.includes('第二轮'),
            len: t.length,
          };
        }"""
    )
    print("bug1 verify:", dump)
    pg.screenshot(path="docs/ui-review/24-bug1-verify.png")
    b.close()

# ui-repro.py — 复现：①发新消息旧内容消失 ②内联面板显示不全
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

    # 第一条消息
    pg.fill("textarea", "第一条消息：请介绍氧化还原反应")
    pg.click("button:has-text('发送')")
    for _ in range(40):
        pg.wait_for_timeout(2000)
        if not pg.evaluate("() => !!document.querySelector('main textarea')?.disabled"):
            break
    pg.wait_for_timeout(1000)
    n1 = pg.evaluate("() => document.querySelectorAll('main .overflow-y-auto .bg-surface, main .overflow-y-auto [class*=self-end]').length")
    print("第一条后消息元素数:", n1)

    # 第二条消息
    pg.fill("textarea", "第二条消息：请配平 Fe2O3 + CO = Fe + CO2")
    pg.click("button:has-text('发送')")
    for _ in range(40):
        pg.wait_for_timeout(2000)
        if not pg.evaluate("() => !!document.querySelector('main textarea')?.disabled"):
            break
    pg.wait_for_timeout(1000)

    # 检查第一条消息是否还在（bug 1）
    first_gone = pg.evaluate(
        "() => { const area=[...document.querySelectorAll('main .overflow-y-auto')].find(el => el.innerText.length>300);"
        "const t = area ? area.innerText : '';"
        "return { hasFirst: t.includes('第一条消息'), hasSecond: t.includes('第二条消息'), len: t.length }; }"
    )
    print("bug1 检查:", first_gone)
    pg.screenshot(path="docs/ui-review/19-repro-bug1.png")

    # bug 2：发送出题指令，看内联面板
    pg.fill("textarea", "请打开出题工作台")
    pg.click("button:has-text('发送')")
    for _ in range(40):
        pg.wait_for_timeout(2000)
        if not pg.evaluate("() => !!document.querySelector('main textarea')?.disabled"):
            break
    pg.wait_for_timeout(1500)

    panel = pg.evaluate(
        """() => {
          const area=[...document.querySelectorAll('main .overflow-y-auto')].find(el => el.innerText.length>300);
          if (!area) return { area: false };
          const header = [...area.querySelectorAll('div')].find(d => d.textContent === '出题工作台' && d.className.includes('text-teal'));
          const panel = header ? header.closest('div[class*=max-w]') || header.parentElement.parentElement : null;
          if (!panel) return { panel: false };
          const pr = panel.getBoundingClientRect();
          const ar = area.getBoundingClientRect();
          return {
            panelTop: Math.round(pr.top), panelBottom: Math.round(pr.bottom),
            areaTop: Math.round(ar.top), areaBottom: Math.round(ar.bottom),
            areaScrollH: area.scrollHeight, areaClientH: area.clientHeight,
            panelH: Math.round(pr.height),
            panelVisibleRatio: Math.round(pr.height) ? Math.min(1, Math.max(0, (Math.min(pr.bottom, ar.bottom) - Math.max(pr.top, ar.top)) / pr.height) * 100) : 0,
          };
        }"""
    )
    print("bug2 面板:", panel)
    pg.screenshot(path="docs/ui-review/20-repro-bug2.png")
    b.close()

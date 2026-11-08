# ui-console-debug.py — 查 console 错误 + 组卷弹窗关闭
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

BASE = "http://localhost:3000"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    errs = []
    pg.on("console", lambda m: errs.append(f"{m.type}: {m.text[:200]}") if m.type == "error" else None)
    pg.on("pageerror", lambda e: errs.append(f"pageerror: {str(e)[:200]}"))

    pg.goto(BASE + "/#/login", wait_until="networkidle")
    pg.fill("input[placeholder='请输入账号']", "hai")
    pg.fill("input[type=password]", "hai123456")
    pg.click("button[type=submit]")
    pg.wait_for_timeout(3000)
    pg.goto(BASE + "/#/exam", wait_until="networkidle")
    pg.wait_for_timeout(3500)

    # 打开组卷打印弹窗 → 点右上角关闭
    pg.click("button:has-text('组卷打印')")
    pg.wait_for_timeout(1200)
    pg.evaluate("() => { const c=document.querySelector('.ant-modal-close'); if (c) c.click(); }")
    pg.wait_for_timeout(1500)
    r = pg.evaluate(
        """() => {
          const modals = [...document.querySelectorAll('.ant-modal')];
          return { modalCount: modals.length, firstTitle: modals[0] ? modals[0].querySelector('.ant-modal-title')?.textContent : null };
        }"""
    )
    print("关闭后弹窗数:", r)
    print("console errors:", errs)
    b.close()

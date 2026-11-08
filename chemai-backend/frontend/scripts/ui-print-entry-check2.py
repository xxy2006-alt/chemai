# ui-print-entry-check2.py — 遍历考试找到有题目的，验证「打印试卷」按钮
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

BASE = "http://localhost:3000"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto(BASE + "/#/login", wait_until="networkidle")
    pg.fill("input[placeholder='请输入账号']", "hai")
    pg.fill("input[type=password]", "hai123456")
    pg.click("button[type=submit]")
    pg.wait_for_timeout(3000)
    pg.goto(BASE + "/#/exam", wait_until="networkidle")
    pg.wait_for_timeout(3500)
    pg.evaluate("() => { const t=[...document.querySelectorAll('.ant-tabs-tab')].find(x=>x.textContent.includes('考试列表')); t?.click(); }")
    pg.wait_for_timeout(2500)

    found = False
    for i in range(8):
        clicked = pg.evaluate(
            """(i) => {
              const btns = [...document.querySelectorAll('main button')].filter(x => x.textContent.includes('预览'));
              if (btns[i]) { btns[i].click(); return true; }
              return false;
            }""",
            i,
        )
        if not clicked:
            break
        pg.wait_for_timeout(2200)
        r = pg.evaluate(
            """() => {
              const dlg = document.querySelector('[role="dialog"]');
              if (!dlg) return { open: false };
              const btns = [...dlg.querySelectorAll('button')].map(x => x.textContent.trim());
              return {
                open: true,
                hasPrint: btns.some(t => t.includes('打印试卷')),
                empty: dlg.innerText.includes('暂无题目'),
                qCount: (dlg.innerText.match(/答案/g) || []).length,
              };
            }"""
        )
        print(f"  考试#{i}: {r}")
        pg.evaluate("() => { const c=document.querySelector('[role=dialog] button[aria-label=关闭]'); if (c) c.click(); }")
        pg.wait_for_timeout(800)
        if r.get("open") and r.get("hasPrint"):
            found = True
            pg.screenshot(path="docs/ui-review/74-print-paper-btn.png")
            break
    print("找到有题目考试且打印按钮存在:", found)
    b.close()

# ui-print-entry-check.py — 验证：工作台无组卷打印按钮，考试预览有打印试卷
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

BASE = "http://localhost:3000"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    errs = []
    pg.on("console", lambda m: errs.append(m.text[:120]) if m.type == "error" else None)

    pg.goto(BASE + "/#/login", wait_until="networkidle")
    pg.fill("input[placeholder='请输入账号']", "hai")
    pg.fill("input[type=password]", "hai123456")
    pg.click("button[type=submit]")
    pg.wait_for_timeout(3000)
    pg.goto(BASE + "/#/exam", wait_until="networkidle")
    pg.wait_for_timeout(3500)

    r1 = pg.evaluate(
        """() => {
          const main = document.querySelector('main');
          const workbenchBtns = [...main.querySelectorAll('button')].map(x => x.textContent.trim());
          return {
            hasGroupPrintInWorkbench: workbenchBtns.some(t => t.includes('组卷打印')),
            hasPrintAnywhere: workbenchBtns.some(t => t.includes('打印')),
            actionBtns: workbenchBtns.filter(t => t.length < 12 && t.length > 0).slice(0, 12),
          };
        }"""
    )
    print("1. 出题工作台操作区:", r1)

    # 考试列表 tab → 预览 → 打印试卷按钮
    pg.evaluate("() => { const t=[...document.querySelectorAll('.ant-tabs-tab')].find(x=>x.textContent.includes('考试列表')); t?.click(); }")
    pg.wait_for_timeout(2500)
    r2 = pg.evaluate(
        """() => {
          const main = document.querySelector('main');
          const previewBtns = [...main.querySelectorAll('button')].filter(x => x.textContent.includes('预览'));
          return { previewBtnCount: previewBtns.length };
        }"""
    )
    print("2. 考试列表预览按钮:", r2)
    pg.evaluate("() => { const b=[...document.querySelectorAll('main button')].find(x=>x.textContent.includes('预览')); b?.click(); }")
    pg.wait_for_timeout(2500)
    r3 = pg.evaluate(
        """() => {
          const dlg = document.querySelector('[role="dialog"]');
          const btns = dlg ? [...dlg.querySelectorAll('button')].map(x => x.textContent.trim()) : [];
          return { hasPrintPaper: btns.some(t => t.includes('打印试卷')), dialogBtns: btns };
        }"""
    )
    print("3. 试卷预览「打印试卷」按钮:", r3)
    pg.screenshot(path="docs/ui-review/73-print-entry.png")

    print("console 错误:", len([e for e in errs if 'Failed to load resource' not in e]))
    b.close()

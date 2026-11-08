# ui-agent-lyx-graph.py — 最终验证：找李世睿 → 工具卡片图形化诊断
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8001"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    errs = []
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.goto(BASE + "/#/login", wait_until="networkidle")
    pg.fill("input[placeholder='请输入账号']", "hai")
    pg.fill("input[type=password]", "hai123456")
    pg.click("button[type=submit]")
    pg.wait_for_timeout(2500)
    pg.goto(BASE + "/#/chat", wait_until="networkidle")
    pg.wait_for_timeout(2500)
    pg.fill("textarea", "找一下李世睿的学习情况")
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(60000)
    r = pg.evaluate(
        """() => {
          const main = document.querySelector('main');
          const text = main.innerText;
          const cards = [...main.querySelectorAll('div')].filter(el => {
            const cls = el.className || '';
            return cls.includes('bg-surface') && cls.includes('rounded-[var(--radius-md)]') && el.textContent.includes('完成');
          });
          const expanded = cards.filter(c => c.textContent.includes('成绩趋势') || c.textContent.includes('针对障碍出题练习'));
          return {
            toolCards: cards.length,
            hasGraphBarrier: text.includes('主导障碍'),
            hasTrendChart: text.includes('成绩趋势'),
            hasWeakTable: text.includes('薄弱知识点') && text.includes('次'),
            hasDiagBtn: text.includes('针对障碍出题练习'),
            expandedWithGraph: expanded.length,
            hasJsonFallback: /"student_id"/.test(text),
          };
        }"""
    )
    print("找李世睿:", r)
    pg.screenshot(path="docs/ui-review/46-agent-lyx-graph.png")
    non502 = [e for e in errs if "502" not in e and "Failed to load resource" not in e]
    print("console(非502):", len(non502))
    b.close()

# ui-diagnosis-card-debug.py — 复现：找李世睿，检查工具卡片与诊断面板渲染
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

BASE = "http://localhost:3000"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    errs = []
    pg.on("console", lambda m: errs.append(f"{m.type}: {m.text[:150]}") if m.type == "error" else None)
    pg.on("pageerror", lambda e: errs.append(f"PAGEERROR: {str(e)[:150]}"))

    pg.goto(BASE + "/#/login", wait_until="networkidle")
    pg.fill("input[placeholder='请输入账号']", "hai")
    pg.fill("input[type=password]", "hai123456")
    pg.click("button[type=submit]")
    pg.wait_for_timeout(3000)
    pg.goto(BASE + "/#/chat", wait_until="networkidle")
    pg.wait_for_timeout(2500)

    pg.fill("textarea", "找一下李世睿的学习情况")
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(50000)

    dump = pg.evaluate(
        """() => {
          const main = document.querySelector('main');
          // 工具卡片：含完成/执行中徽章的卡片容器
          const cards = [...main.querySelectorAll('div')].filter(el => {
            const cls = el.className || '';
            return cls.includes('bg-surface') && cls.includes('rounded-[var(--radius-md)]') &&
                   (el.textContent.includes('完成') || el.textContent.includes('执行中'));
          });
          const cardInfo = cards.map(c => ({
            text: c.innerText.slice(0, 120).replace(/\\n/g, ' | '),
            h: Math.round(c.getBoundingClientRect().height),
          }));
          // 诊断面板
          const panels = [...main.querySelectorAll('div')].filter(el => (el.className || '').includes('border-teal/25'));
          const panelInfo = panels.map(p => ({
            text: p.innerText.slice(0, 120).replace(/\\n/g, ' | '),
            h: Math.round(p.getBoundingClientRect().height),
          }));
          return {
            cardCount: cards.length,
            cards: cardInfo.slice(0, 5),
            panelCount: panels.length,
            panels: panelInfo.slice(0, 3),
            hasTrend: main.innerText.includes('成绩趋势'),
            hasBarrier: main.innerText.includes('主导障碍'),
            hasJson: /"student_id"|barrier_distribution/.test(main.innerText),
            bodyTail: main.innerText.slice(-200).replace(/\\n/g, ' | '),
          };
        }"""
    )
    print("工具卡片与面板:", dump)
    pg.screenshot(path="docs/ui-review/75-diagnosis-card-debug.png")
    print("console:", errs if errs else "无")
    b.close()

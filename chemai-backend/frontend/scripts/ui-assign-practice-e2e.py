# ui-assign-practice-e2e.py — 端到端：给李世睿布置针对性练习（批准→成功，不重复批准）
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

BASE = "http://localhost:3000"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    errs = []
    pg.on("console", lambda m: errs.append(m.text[:150]) if m.type == "error" else None)

    pg.goto(BASE + "/#/login", wait_until="networkidle")
    pg.fill("input[placeholder='请输入账号']", "hai")
    pg.fill("input[type=password]", "hai123456")
    pg.click("button[type=submit]")
    pg.wait_for_timeout(3000)
    pg.goto(BASE + "/#/chat", wait_until="networkidle")
    pg.wait_for_timeout(2500)
    # 新建对话（避免复用停在中断点的旧会话导致 INVALID_CHAT_HISTORY）
    pg.evaluate("() => { const b=[...document.querySelectorAll('button')].find(x=>x.textContent.includes('新建对话')); b?.click(); }")
    pg.wait_for_timeout(1500)

    pg.fill("textarea", "给李世睿布置针对性练习")
    pg.keyboard.press("Enter")

    # 等待审批卡出现（LLM 先诊断再请求批准，最多 150s）
    waited = 0
    while waited < 150:
        pg.wait_for_timeout(2000)
        waited += 2
        r = pg.evaluate(
            """() => {
              const el = [...document.querySelectorAll('div')].find(x =>
                (x.className || '').includes('bg-warning-soft') && x.textContent.includes('需要确认'));
              return !!el;
            }"""
        )
        if r:
            break
    # 审批卡数量 + 批准
    r1 = pg.evaluate(
        """() => {
          const cards = [...document.querySelectorAll('div')].filter(x =>
            (x.className || '').includes('bg-warning-soft') && x.textContent.includes('需要确认'));
          return { count: cards.length, texts: cards.map(c => c.innerText.slice(0, 70).replace(/\\n/g, ' ')) };
        }"""
    )
    print(f"1. 审批卡(等待{waited}s):", r1)
    clicked = pg.evaluate(
        """() => {
          const btns = [...document.querySelectorAll('button')];
          const ok = btns.find(x => x.textContent.trim() === '批准' || x.textContent.includes('批准'));
          if (ok) { ok.click(); return true; }
          return false;
        }"""
    )
    print("   点击批准:", clicked)
    pg.wait_for_timeout(50000)

    r2 = pg.evaluate(
        """() => {
          const main = document.querySelector('main');
          const text = main.innerText;
          const warnCards = [...main.querySelectorAll('div')].filter(x =>
            (x.className || '').includes('bg-warning-soft'));
          const okCards = [...main.querySelectorAll('div')].filter(x =>
            (x.className || '').includes('bg-success-soft'));
          return {
            hasFail: (text.match(/失败/g) || []).length,
            hasAssigned: /已为 1 名学生布置练习/.test(text),
            warnCards: warnCards.map(c => c.innerText.slice(0, 50).replace(/\\n/g, ' ')),
            okCards: okCards.map(c => c.innerText.slice(0, 50).replace(/\\n/g, ' ')),
            hasJsonError: /assigned_count|limit_exceeded/.test(text),
            tail: text.slice(-160).replace(/\\n/g, ' | '),
          };
        }"""
    )
    print("2. 结果:", r2)
    pg.screenshot(path="docs/ui-review/76-assign-practice.png")
    print("console 错误:", len([e for e in errs if 'Failed to load resource' not in e]))
    b.close()

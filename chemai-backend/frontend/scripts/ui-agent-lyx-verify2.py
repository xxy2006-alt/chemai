# ui-agent-lyx-verify2.py — 工具卡片 + 学生诊断面板 + 出题按钮（精确验证）
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
    pg.wait_for_timeout(45000)

    r = pg.evaluate(
        """() => {
          const main = document.querySelector('main');
          const text = main.innerText;
          // 工具卡片：圆角工具图标块 + 状态徽章（执行中/完成/失败）
          const cards = [...main.querySelectorAll('div')].filter(el => {
            const cls = el.className || '';
            return cls.includes('bg-surface') && cls.includes('rounded-[var(--radius-md)]') &&
                   (text.includes('诊断') || el.querySelector('.bg-teal-soft, .bg-error-soft'));
          });
          const toolNames = [...main.querySelectorAll('span')]
            .map(s => s.textContent.trim())
            .filter(t => ['搜索真题','AI 出题','障碍诊断','智能辅导','学生列表','诊断面板'].includes(t));
          return {
            hasToolCard: cards.length > 0,
            toolNameChips: toolNames,
            hasBadgeDone: text.includes('完成'),
            hasDiagPanel: text.includes('学生诊断 · 李世睿') || text.includes('班级障碍诊断'),
            hasStudentBarrier: /概念理解/.test(text) && /审题仔细/.test(text),
            hasWeakKps: text.includes('弱知识点') || text.includes('盐类水解') || text.includes('离子反应'),
            hasDiagToExamBtn: text.includes('针对障碍出题练习'),
            bodyHasLyx: text.includes('李世睿'),
          };
        }"""
    )
    print("找李世睿:", r)
    pg.screenshot(path="docs/ui-review/44-agent-lyx-toolcard.png")

    # 点按钮 → 触发消息发送（textarea 上方出现新用户气泡）
    clicked = pg.evaluate(
        """() => {
          const btns = [...document.querySelectorAll('main button')];
          const b = btns.find(x => x.textContent.includes('针对障碍出题练习'));
          if (b) { b.click(); return true; }
          return false;
        }"""
    )
    pg.wait_for_timeout(3000)
    r2 = pg.evaluate(
        """() => {
          const main = document.querySelector('main');
          const text = main.innerText;
          const bubbles = [...main.querySelectorAll('div')].filter(el =>
            el.className.includes('bg-primary') && el.className.includes('text-white'));
          return {
            clicked: true,
            newUserBubble: bubbles.length,
            lastBubbleText: bubbles.length ? bubbles[bubbles.length-1].textContent.slice(0, 60) : '',
          };
        }"""
    )
    print("点击出题按钮:", r2)
    pg.screenshot(path="docs/ui-review/45-agent-diag-btn-sent.png")

    non502 = [e for e in errs if "502" not in e and "Failed to load resource" not in e]
    print("console(非502):", len(non502))
    b.close()

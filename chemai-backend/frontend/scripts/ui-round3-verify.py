# ui-round3-verify.py — 第三轮验证：计时器 / 组卷打印 / 题库单题删除+批量加卷
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

BASE = "http://localhost:3000"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    errs = []
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)

    pg.goto(BASE + "/#/login", wait_until="networkidle")
    pg.fill("input[placeholder='请输入账号']", "hai")
    pg.fill("input[type=password]", "hai123456")
    pg.click("button[type=submit]")
    pg.wait_for_timeout(3000)
    pg.goto(BASE + "/#/exam", wait_until="networkidle")
    pg.wait_for_timeout(3500)

    # 1. AI 生成 + 计时器
    pg.evaluate(
        """() => {
          const btns = [...document.querySelectorAll('main button')];
          const kp = btns.find(b => b.textContent.includes('氧化还原反应'));
          if (kp) kp.click();
        }"""
    )
    pg.wait_for_timeout(500)
    pg.click("button:has-text('AI 生成题目')")
    pg.wait_for_timeout(4000)
    r1 = pg.evaluate(
        """() => {
          const text = document.querySelector('main').innerText;
          const timer = document.querySelector('.live-timer.ticking');
          return {
            hasTimerLabel: text.includes('AI 出题'),
            timerText: timer ? timer.textContent : null,
            timerVisible: !!timer,
          };
        }"""
    )
    print("1. 生成计时器:", r1)
    pg.wait_for_timeout(20000)

    # 2. 组卷打印弹窗（未保存题目应提示）
    pg.click("button:has-text('组卷打印')")
    pg.wait_for_timeout(1200)
    r2 = pg.evaluate(
        """() => {
          const modal = document.querySelector('.ant-modal');
          return {
            hasModal: !!modal,
            modalText: modal ? modal.innerText.slice(0, 120).replace(/\\n/g, ' ') : '',
          };
        }"""
    )
    print("2. 组卷打印弹窗:", r2)
    # 确认（题目未保存 → 提示）
    pg.evaluate("() => { const b=[...document.querySelectorAll('.ant-modal button')].find(x=>x.textContent.includes('加入考试并打印')); if (b) b.click(); }")
    pg.wait_for_timeout(1500)
    r2b = pg.evaluate(
        """() => {
          const msg = document.querySelector('.ant-message');
          return { hasMsg: !!msg, msgText: msg ? msg.textContent.slice(0, 60) : '' };
        }"""
    )
    print("   未保存提示:", r2b)
    pg.evaluate("() => { const c=document.querySelector('.ant-modal-close'); if (c) c.click(); }")
    pg.wait_for_timeout(1000)
    closed = pg.evaluate("() => !document.querySelector('.ant-modal')")
    print("   弹窗已关闭:", closed)
    pg.screenshot(path="docs/ui-review/70-round3-print.png")

    # 3. 题库管理：先选中一个题库 → 单题删除 + 批量加入考试
    pg.evaluate("() => { const t=[...document.querySelectorAll('.ant-tabs-tab')].find(x=>x.textContent.includes('题库管理')); if (t) t.click(); }")
    pg.wait_for_timeout(2000)
    pg.evaluate(
        """() => {
          const items = [...document.querySelectorAll('main .space-y-4 > div button, main button')];
          // 题库列表项（含「N 题」文本的按钮）
          const bank = items.find(b => /\\d+ 题/.test(b.textContent) && !b.textContent.includes('加入考试'));
          if (bank) { bank.click(); return true; }
          return false;
        }"""
    )
    pg.wait_for_timeout(2000)
    r3 = pg.evaluate(
        """() => {
          const main = document.querySelector('main');
          return {
            bankCount: main.innerText.includes('题') ? (main.innerText.match(/\\d+ 题/g) || []).length : 0,
            hasCheckbox: !!main.querySelector('.ant-checkbox'),
            deleteBtns: [...main.querySelectorAll('button')].filter(x => x.textContent.includes('删除')).length,
            addToExamBtns: [...main.querySelectorAll('button')].filter(x => x.textContent.includes('加入考试')).length,
            hasBatchBar: main.innerText.includes('已选 0 题'),
            hasQuestions: main.innerText.includes('答案'),
          };
        }"""
    )
    print("3. 题库管理:", r3)
    pg.screenshot(path="docs/ui-review/71-round3-bank.png")

    # 勾选一题 → 批量加入考试弹窗
    clicked = pg.evaluate(
        """() => {
          const cbs = [...document.querySelectorAll('.ant-checkbox-input')];
          if (cbs.length > 1) cbs[1].click();
          const btns = [...document.querySelectorAll('main button')].filter(x => x.textContent.includes('加入考试'));
          // 批量栏按钮在 DOM 中位于题目列表之前
          if (btns.length) { btns[0].click(); return true; }
          return false;
        }"""
    )
    print("   点击批量按钮:", clicked)
    pg.wait_for_timeout(1500)
    r4 = pg.evaluate(
        """() => {
          const modal = document.querySelector('.ant-modal');
          if (!modal) return { hasAddModal: false };
          return {
            hasAddModal: true,
            modalText: modal.innerText.slice(0, 100).replace(/\\n/g, ' '),
            hasExamSelect: !!modal.querySelector('.ant-select'),
          };
        }"""
    )
    print("4. 批量加入考试弹窗:", r4)
    pg.screenshot(path="docs/ui-review/72-round3-addtoexam.png")
    pg.evaluate("() => { const c=document.querySelector('.ant-modal-close'); if (c) c.click(); }")
    pg.wait_for_timeout(500)

    non502 = [e for e in errs if "502" not in e and "Failed to load resource" not in e]
    print("console(非502):", len(non502))
    b.close()

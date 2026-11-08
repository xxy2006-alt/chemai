# ui-agent-lyx-verify.py — Agent 找学生/出题按钮/学习方案跳转（旧版行为恢复验证）
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

    def send(text: str, wait_ms: int):
        pg.fill("textarea", text)
        pg.keyboard.press("Enter")
        pg.wait_for_timeout(wait_ms)

    # ── 1. 找学生 → 诊断面板 + 工具卡片 ──
    send("找一下李世睿的学习情况", 25000)
    r1 = pg.evaluate(
        """() => {
          const main = document.querySelector('main');
          // 工具卡片：含"完成/执行中"徽章的卡片（ToolCard）
          const toolCards = [...main.querySelectorAll('div')].filter(el =>
            el.className.includes('bg-surface') && el.className.includes('border') &&
            (el.textContent.includes('完成') || el.textContent.includes('执行中')) &&
            el.querySelector('span')?.textContent.length < 6
          );
          const diagPanel = [...main.querySelectorAll('div')].find(el =>
            el.className.includes('bg-surface') && el.textContent.includes('障碍诊断')
          );
          return {
            toolCardCount: toolCards.length,
            toolCardSamples: toolCards.slice(0, 4).map(t => t.textContent.slice(0, 30)),
            hasDiagPanel: !!diagPanel,
            diagPanelText: diagPanel ? diagPanel.textContent.slice(0, 150) : '',
            hasDiagToExamBtn: main.innerText.includes('针对障碍出题练习'),
            bodyHasLyx: main.innerText.includes('李世睿'),
          };
        }"""
    )
    print("1. 找李世睿:", r1)
    pg.screenshot(path="docs/ui-review/41-agent-lyx-diagnosis.png")

    # ── 2. 点击「针对障碍出题练习」→ Agent 打开出题面板 ──
    clicked = pg.evaluate(
        """() => {
          const btns = [...document.querySelectorAll('main button')];
          const b = btns.find(x => x.textContent.includes('针对障碍出题练习'));
          if (b) { b.click(); return true; }
          return false;
        }"""
    )
    print("2. 点击出题按钮:", clicked)
    pg.wait_for_timeout(30000)
    r2 = pg.evaluate(
        """() => {
          const main = document.querySelector('main');
          return {
            hasWorkbench: main.innerText.includes('出题工作台'),
            hasTypes: ['单选','多选','填空'].every(l => main.innerText.includes(l)),
          };
        }"""
    )
    print("   出题面板:", r2)
    pg.screenshot(path="docs/ui-review/42-agent-diag-to-exam.png")

    # ── 3. 生成学习方案 → 应跳转学生页 + 自动打开抽屉 + 自动出方案 ──
    send("给李世睿出一份个性化的学习方案", 40000)
    pg.wait_for_timeout(4000)
    r3 = pg.evaluate(
        """() => {
          return {
            url: location.hash,
            hasDrawer: !!document.querySelector('.fixed.inset-0.z-40'),
            hasPlanModal: !!document.querySelector('[role=dialog]'),
            bodyHasLyx: document.body.innerText.includes('李世睿'),
          };
        }"""
    )
    print("3. 跳转后:", r3)
    pg.wait_for_timeout(20000)  # 等方案生成
    r4 = pg.evaluate(
        """() => {
          const body = document.body.innerText;
          return {
            hasPlanTitle: /个性化学习计划|学习计划/.test(body),
            hasSendBtn: body.includes('发送'),
            hasDrawer: !!document.querySelector('.fixed.inset-0.z-40'),
          };
        }"""
    )
    print("   方案生成:", r4)
    pg.screenshot(path="docs/ui-review/43-agent-plan-auto.png")

    non502 = [e for e in errs if "502" not in e and "Failed to load resource" not in e]
    print("console(非502):", len(non502))
    b.close()

# ui-agent-e2e.py — 真实 Agent 出题流程验收（问题①②③）
# 登录 → 发送出题指令 → 检查工具卡片 / 内联面板 / 思考状态 / 不跳页
import time
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

    # 发送出题指令
    pg.fill("textarea", "请帮我出3道关于氧化还原反应的题目，知识点选 氧化还原反应")
    pg.click("button:has-text('发送')")

    # 观察流式过程：检查思考状态出现在气泡内
    phase_in_bubble = False
    for _ in range(20):
        pg.wait_for_timeout(1500)
        # 气泡内的思考状态（teal 脉冲点 + 阶段文案）
        phase_in_bubble = pg.evaluate(
            "() => { const els=[...document.querySelectorAll('main .overflow-y-auto .bg-surface')];"
            "return els.some(e => /分析中|执行中|回复中|等待|第 \\d+ 步/.test(e.textContent)); }"
        )
        if phase_in_bubble:
            break
    print("1. 思考状态在气泡内:", phase_in_bubble)
    pg.screenshot(path="docs/ui-review/12-agent-thinking-in-bubble.png")

    # 等 Agent 完成（LLM + 工具调用可能需要较长时间）：流式中 textarea 被禁用
    for _ in range(40):
        pg.wait_for_timeout(2000)
        busy = pg.evaluate("() => !!document.querySelector('main textarea')?.disabled")
        if not busy:
            break
    pg.wait_for_timeout(2000)

    # 2. 工具卡片：存在且可展开（tool_result JSON 已解析）
    cards = pg.evaluate(
        "() => [...document.querySelectorAll('main .overflow-y-auto button')]"
        ".filter(b => /搜索真题|AI 出题|障碍诊断|智能辅导|模拟实验|配平审核|导入试卷|布置练习|生成周报|联网搜索/.test(b.textContent))"
        ".length"
    )
    print("2. 工具卡片数:", cards)
    # 点击第一张卡片展开内容
    expanded = pg.evaluate(
        "() => { const btn=[...document.querySelectorAll('main .overflow-y-auto button')]"
        ".find(b => /搜索真题|AI 出题|障碍诊断|智能辅导|模拟实验|配平审核|导入试卷|布置练习|生成周报|联网搜索/.test(b.textContent));"
        "if (!btn) return false; btn.click(); return true; }"
    )
    pg.wait_for_timeout(600)
    has_content = pg.evaluate(
        "() => { const cards=[...document.querySelectorAll('main .overflow-y-auto .border-t')];"
        "return cards.some(c => c.textContent.length > 30); }"
    )
    print("   展开后卡片有内容:", has_content)

    # 3. 内联面板：不跳页，仍在 /#/chat，页面内有「出题工作台」面板
    url = pg.url
    inline_panel = pg.evaluate(
        "() => [...document.querySelectorAll('main .overflow-y-auto *')]"
        ".some(e => e.textContent === '出题工作台' && e.className.includes('text-teal'))"
    )
    print("3. URL 未跳页:", "/#/chat" in url, "| 内联出题面板:", inline_panel)
    pg.screenshot(path="docs/ui-review/13-agent-inline-panel.png")

    body = pg.evaluate("() => document.body.innerText.slice(-400)")
    print("4. 页面尾部文本:", body.replace(chr(10), " | ")[:300])

    non502 = [e for e in errs if "502" not in e]
    print("console errors(非502):", non502[:5])
    b.close()

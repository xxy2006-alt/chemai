# ui-agent-live.py — 新会话实时出题流验收（修正检测：工具卡按徽章识别）
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

    # 新会话
    pg.click("button:has-text('新建对话')")
    pg.wait_for_timeout(800)

    # 发送出题指令
    pg.fill("textarea", "请帮我出3道关于氧化还原反应的题目")
    pg.click("button:has-text('发送')")

    # 流式期间：思考状态在气泡内
    saw_status = False
    for _ in range(10):
        pg.wait_for_timeout(1000)
        saw_status = pg.evaluate(
            "() => { const els=[...document.querySelectorAll('main .overflow-y-auto .bg-surface')];"
            "return els.some(e => /分析中|执行中|回复中|等待|第 \\d+ 步/.test(e.textContent)); }"
        )
        if saw_status:
            break
    print("1. 思考状态在气泡内:", saw_status)

    # 等完成
    for _ in range(50):
        pg.wait_for_timeout(2000)
        if not pg.evaluate("() => !!document.querySelector('main textarea')?.disabled"):
            break
    pg.wait_for_timeout(1500)

    # 2. 工具卡片（按徽章文本识别，标签可能是中文也可能是英文原样）
    dump = pg.evaluate(
        """() => {
          const area = [...document.querySelectorAll('main .overflow-y-auto')].find(el => el.innerText.length > 300) || document.querySelector('main .overflow-y-auto');
          const badges = [...area.querySelectorAll('span')].filter(s => ['执行中','完成','失败'].includes(s.textContent.trim()));
          const cards = badges.map(sb => {
            const card = sb.closest('button');
            return card ? card.textContent.replace(/\\s+/g, ' ').slice(0, 50) : 'orphan';
          });
          const panel = [...area.querySelectorAll('*')].some(e => e.textContent === '出题工作台' && e.className.includes('text-teal'));
          const expanded = (() => { const first = badges[0] ? badges[0].closest('button') : null; if (first) first.click(); })();
          return { cardCount: badges.length, cards, panel, textLen: area.innerText.length };
        }"""
    )
    pg.wait_for_timeout(800)
    expanded = pg.evaluate(
        "() => { const area=[...document.querySelectorAll('main .overflow-y-auto')].find(el => el.innerText.length > 300);"
        "const body=[...area.querySelectorAll('div')].find(d => d.className.includes('border-t') && d.textContent.length > 40);"
        "return body ? body.textContent.slice(0, 120) : null; }"
    )
    print("2. 工具卡片:", dump.get("cardCount"), "| 内联面板:", dump.get("panel"), "| 展开内容:", (expanded or "无")[:120])

    url = pg.url
    print("3. URL 未跳页:", "/#/chat" in url)
    pg.screenshot(path="docs/ui-review/15-agent-live-questions.png")

    non502 = [e for e in errs if "502" not in e]
    print("console errors(非502):", non502[:5])
    b.close()

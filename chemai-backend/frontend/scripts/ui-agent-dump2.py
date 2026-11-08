# ui-agent-dump2.py — 精确定位消息区内容
import json
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8001"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto(BASE + "/#/login", wait_until="networkidle")
    pg.fill("input[placeholder='请输入账号']", "hai")
    pg.fill("input[type=password]", "hai123456")
    pg.click("button[type=submit]")
    pg.wait_for_timeout(4000)

    dump = pg.evaluate(
        """() => {
          const areas = [...document.querySelectorAll('main .overflow-y-auto')].map((el, i) => ({
            i, len: el.innerText.length, head: el.innerText.slice(0, 60).replace(/\\n/g, ' | ')
          }));
          const panel = [...document.querySelectorAll('main *')].find(e => e.textContent === '出题工作台' && e.className.includes('text-teal'));
          const toolBadges = [...document.querySelectorAll('main span')].filter(s => ['执行中','完成','失败'].includes(s.textContent.trim())).length;
          const toolBtns = [...document.querySelectorAll('main button')].filter(b => {
            const t = b.textContent; return t && t.length < 30 && /搜索|出题|诊断|辅导|实验|配平|导入|布置|周报|联网|show_|generate_|search_|diagnose_|balance_|simulate_/.test(t);
          }).map(b => b.textContent.trim().slice(0, 30));
          return JSON.stringify({ areas, hasInlinePanel: !!panel, toolBadges, toolBtns });
        }"""
    )
    print("dump2:", dump)
    pg.screenshot(path="docs/ui-review/14-agent-conversation.png")
    b.close()

# ui-agent-dump.py — 转储 Agent 对话后的消息区按钮/卡片结构
import sys
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8001"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto(BASE + "/#/login", wait_until="networkidle")
    pg.fill("input[placeholder='请输入账号']", "hai")
    pg.fill("input[type=password]", "hai123456")
    pg.click("button[type=submit]")
    pg.wait_for_timeout(2500)

    # 打开最近对话（第一条）
    pg.evaluate("() => { const items=[...document.querySelectorAll('.group')]; if (items.length) items[0].click(); }")
    pg.wait_for_timeout(2000)

    dump = pg.evaluate(
        """() => {
          const area = document.querySelector('main .overflow-y-auto');
          if (!area) return 'NO AREA';
          const btns = [...area.querySelectorAll('button')].map(b => b.textContent.trim().slice(0, 40));
          const badges = [...area.querySelectorAll('span')].filter(s => /执行中|完成|失败|通过|拦截|确认/.test(s.textContent)).map(s => s.textContent.trim());
          const heads = [...area.querySelectorAll('div')].filter(d => d.textContent && d.textContent.length < 30 && /出题|诊断|计划|学生/.test(d.textContent) && d.className.includes('text-teal')).map(d => d.textContent.trim());
          return JSON.stringify({ btns, badges, heads, areaLen: area.innerText.length });
        }"""
    )
    print("dump:", dump)
    b.close()

# ui-bank-dump.py — dump 题库管理 tab，检查删除按钮
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8001"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto(BASE + "/#/login", wait_until="networkidle")
    pg.fill("input[placeholder='请输入账号']", "hai")
    pg.fill("input[type=password]", "hai123456")
    pg.click("button[type=submit]")
    pg.wait_for_timeout(3000)
    pg.goto(BASE + "/#/exam", wait_until="networkidle")
    pg.wait_for_timeout(3500)
    pg.evaluate(
        "() => { const t=[...document.querySelectorAll('.ant-tabs-tab')].find(x=>x.textContent.includes('题库管理')); if (t) t.click(); }"
    )
    pg.wait_for_timeout(3000)
    dump = pg.evaluate("() => { const m=document.querySelector('main'); return m.innerText.slice(0, 500); }")
    print("题库管理 tab:", dump.replace(chr(10), ' | ')[:500])
    # 所有 button + title 属性
    btns = pg.evaluate(
        """() => {
          return [...document.querySelectorAll('main button')].map(b => ({ text: b.textContent.trim().slice(0, 20), title: b.getAttribute('title') || '' })).filter(x => x.text || x.title);
        }"""
    )
    print("按钮:", btns[:10])
    b.close()

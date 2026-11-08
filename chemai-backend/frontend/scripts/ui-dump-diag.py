# ui-dump-diag.py — 打开最近会话，dump 诊断面板 DOM 文本
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
    pg.wait_for_timeout(2500)
    pg.goto(BASE + "/#/chat", wait_until="networkidle")
    pg.wait_for_timeout(3000)
    # 打开第一个会话历史
    pg.evaluate("() => { const items=[...document.querySelectorAll('main div')].filter(el=>el.className.includes('cursor-pointer')&&el.textContent.includes('李世睿')); if(items.length) items[0].click(); }")
    pg.wait_for_timeout(3000)
    dump = pg.evaluate(
        """() => {
          const main = document.querySelector('main');
          const diagEls = [...main.querySelectorAll('div')].filter(el => el.textContent.includes('障碍诊断'));
          const out = [];
          diagEls.forEach((el, i) => {
            out.push(`[${i}] ${el.textContent.slice(0, 220).replace(/\\n/g, ' | ')}`);
          });
          const btn = [...main.querySelectorAll('button')].find(x => x.textContent.includes('针对障碍出题练习'));
          return { panels: out, hasBtn: !!btn, mainTail: main.innerText.slice(-400).replace(/\\n/g, ' | ') };
        }"""
    )
    print(dump)
    b.close()

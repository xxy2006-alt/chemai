# ui-variant-debug2.py — 调试蓝本弹窗试卷点击后状态
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
    pg.goto(BASE + "/#/exam", wait_until="networkidle")
    pg.wait_for_timeout(2500)
    pg.evaluate("() => { const btns=[...document.querySelectorAll('main button')].filter(b => b.textContent.includes('蓝本') && b.textContent.includes('作')); if (btns.length) btns[0].click(); }")
    pg.wait_for_timeout(2000)

    before = pg.evaluate(
        """() => {
          const dlg = document.querySelector('[role=dialog]');
          if (!dlg) return 'no dialog';
          const btns = [...dlg.querySelectorAll('button')].map(b => b.textContent.trim().slice(0, 20));
          return { btns };
        }"""
    )
    print("1. 弹窗按钮:", before)

    # 点击包含 全国卷2020 的按钮（精确）
    pg.evaluate(
        "() => { const btns=[...document.querySelectorAll('[role=dialog] button')].filter(b => b.textContent.includes('2020'));"
        "console.log('MATCH', btns.length, btns.map(b=>b.textContent.trim()).join('|'));"
        "if (btns.length) btns[0].click(); }"
    )
    pg.wait_for_timeout(3000)
    after = pg.evaluate(
        """() => {
          const dlg = document.querySelector('[role=dialog]');
          if (!dlg) return 'no dialog';
          return {
            btnCount: dlg.querySelectorAll('button').length,
            hasReturn: dlg.innerText.includes('返回目录'),
            hasTiMu: dlg.innerText.includes('题'),
            textLen: dlg.innerText.length
          };
        }"""
    )
    print("2. 点击后:", after)
    b.close()

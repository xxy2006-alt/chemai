# ui-exam-history.py — 历史真题库弹窗 + 题目渲染验收
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

    # 进入出题工作台 → 历史真题库
    pg.goto(BASE + "/#/exam", wait_until="networkidle")
    pg.wait_for_timeout(2500)
    pg.click("button:has-text('历史真题库')")
    pg.wait_for_timeout(2500)

    # 找一张试卷（优先 2020 全国卷：按钮含「全国卷」且含「题」）
    papers = pg.evaluate(
        "() => [...document.querySelectorAll('main button')].filter(b => /全国卷/.test(b.textContent) && /\\d+\\s*题/.test(b.textContent)).map(b => b.textContent.replace(/\\s+/g,' ').slice(0,30))"
    )
    print("1. 试卷列表:", papers[:6])

    # 点击第一张试卷
    clicked = pg.evaluate(
        "() => { const btns=[...document.querySelectorAll('main button')].filter(b => /全国卷/.test(b.textContent) && /\\d+\\s*题/.test(b.textContent)); if (!btns.length) return false; btns[0].click(); return true; }"
    )
    pg.wait_for_timeout(3000)
    print("2. 点击试卷:", clicked)

    # 3. 弹窗出现？内容有 KaTeX？图片加载？
    modal = pg.evaluate(
        """() => {
          const overlay = document.querySelector('[role=dialog]');
          if (!overlay) return { modal: false };
          const katex = overlay.querySelectorAll('.katex').length;
          const imgs = [...overlay.querySelectorAll('img')];
          const imgsOk = imgs.filter(i => i.naturalWidth > 0).length;
          return { modal: true, katexCount: katex, imgCount: imgs.length, imgsOk, hasTitle: overlay.innerText.includes('全国卷') };
        }"""
    )
    print("3. 弹窗检查:", modal)
    pg.screenshot(path="docs/ui-review/17-exam-history-modal.png")

    non502 = [e for e in errs if "502" not in e]
    print("console errors(非502):", non502[:5])
    b.close()

# ui-exam-modal2.py — 弹窗位置/尺寸/内容渲染验收
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

    pg.goto(BASE + "/#/exam", wait_until="networkidle")
    pg.wait_for_timeout(2500)
    pg.click("button:has-text('历史真题库')")
    pg.wait_for_timeout(2500)

    # 点击 2020 全国卷
    pg.evaluate(
        "() => { const btns=[...document.querySelectorAll('main button')].filter(b => /全国卷/.test(b.textContent) && /\\d+\\s*题/.test(b.textContent)); if (btns.length) btns[0].click(); }"
    )
    pg.wait_for_timeout(3000)

    info = pg.evaluate(
        """() => {
          const dlg = document.querySelector('[role=dialog]');
          if (!dlg) return { modal: false };
          const r = dlg.getBoundingClientRect();
          const body = dlg.querySelector('.flex-1, .overflow-y-auto');
          // 铑的配合物离子 题目是否渲染成 KaTeX 且无 Ω 垃圾
          const katexCount = dlg.querySelectorAll('.katex').length;
          const hasOmega = dlg.textContent.includes('\\Omega') || dlg.textContent.includes('Ω');
          const imgs = [...dlg.querySelectorAll('img')];
          const imgsOk = imgs.filter(i => i.naturalWidth > 0).length;
          const spacedGarbage = /C H 3/.test(dlg.textContent.replace(/[\\n\\s]/g, ' '));
          return {
            modal: true,
            top: Math.round(r.top), viewportH: window.innerHeight,
            width: Math.round(r.width), viewportW: window.innerWidth,
            katexCount, hasOmega, imgCount: imgs.length, imgsOk,
            spacedGarbage: dlg.textContent.includes('C H 3 C O I'),
            sampleLen: dlg.textContent.length
          };
        }"""
    )
    print("modal info:", info)
    pg.screenshot(path="docs/ui-review/18-exam-modal-top-filled.png")

    non502 = [e for e in errs if "502" not in e]
    print("console errors(非502):", non502[:5])
    b.close()

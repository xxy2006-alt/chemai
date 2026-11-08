# ui-exam-final.py — 历史弹窗最终验收：t3 表格题 + 全卷渲染健康度
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
    pg.evaluate(
        "() => { const btns=[...document.querySelectorAll('main button')].filter(b => /全国卷/.test(b.textContent) && /\\d+\\s*题/.test(b.textContent)); if (btns.length) btns[0].click(); }"
    )
    pg.wait_for_timeout(3000)

    dump = pg.evaluate(
        """() => {
          const dlg = document.querySelector('[role=dialog]');
          if (!dlg) return { modal: false };
          const html = dlg.innerHTML;
          const text = dlg.innerText;
          const katex = dlg.querySelectorAll('.katex').length;
          const katexErrors = dlg.querySelectorAll('.katex-error').length;
          const imgs = [...dlg.querySelectorAll('img')];
          const imgsOk = imgs.filter(i => i.naturalWidth > 0).length;
          return {
            modal: true,
            katex, katexErrors,
            hasGamma: html.includes('Gamma') || text.includes('Γ'),
            hasRawBf: html.includes('\\bf') || text.includes('\\bf'),
            hasMathrmLetters: /mathnormal">m<\\/span>/.test(html),
            imgsOk: imgsOk + '/' + imgs.length,
            hasTable: !!dlg.querySelector('table'),
            textLen: text.length
          };
        }"""
    )
    print("final:", dump)
    pg.screenshot(path="docs/ui-review/25-exam-final.png")
    non502 = [e for e in errs if "502" not in e]
    print("console(非502):", len(non502))
    b.close()

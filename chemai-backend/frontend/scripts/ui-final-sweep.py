# ui-final-sweep.py — 全卷最终巡检：katex 错误 / MathML 隐藏 / 公式单版本 / 选项分行
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
    pg.wait_for_timeout(3000)
    pg.click("button:has-text('历史真题库')")
    pg.wait_for_timeout(3000)
    for _ in range(5):
        pg.evaluate("() => { const b=[...document.querySelectorAll('main button')].filter(x => /全国卷2020/.test(x.textContent)); if (b.length) b[0].click(); }")
        pg.wait_for_timeout(2500)
        if pg.evaluate("() => !!document.querySelector('[role=dialog]')"):
            break

    check = pg.evaluate(
        """() => {
          const dlg = document.querySelector('[role=dialog]');
          const katexErrors = dlg.querySelectorAll('.katex-error').length;
          const mathml = dlg.querySelector('.katex-mathml');
          const mathmlHidden = mathml ? getComputedStyle(mathml).clip !== 'auto' : null;
          // 全卷可见层统计：每个公式的 katex-html 只算一份
          const visibleSpans = dlg.querySelectorAll('.katex-html');
          // 含 醇 的题干区：验证 75% 单版本
          const t1 = [...dlg.querySelectorAll('.border')].find(el => el.textContent.includes('乙醚'));
          const t1visible = t1 ? [...t1.querySelectorAll('.katex-html')].map(e => e.textContent).join(' ') : '';
          return {
            katexErrors,
            mathmlHidden,
            katexCount: visibleSpans.length,
            t1_75_count: (t1visible.match(/75%/g) || []).length,
            t1_spaced: t1visible.includes('C H 3'),
            t1_rawSource: t1visible.includes('75\\\\%'),
            imgOk: [...dlg.querySelectorAll('img')].filter(i => i.naturalWidth > 0).length,
          };
        }"""
    )
    print("final sweep:", check)
    pg.screenshot(path="docs/ui-review/30-final-sweep.png")
    non502 = [e for e in errs if "502" not in e]
    print("console(非502):", len(non502))
    b.close()

# ui-t1-verify.py — 浏览器验证 T1：MathML 隐藏、公式单版本、选项分行
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
    pg.wait_for_timeout(3000)
    pg.click("button:has-text('历史真题库')")
    pg.wait_for_timeout(3000)
    for attempt in range(5):
        pg.evaluate(
            "() => { const btns=[...document.querySelectorAll('main button')].filter(b => /全国卷2020/.test(b.textContent)); if (btns.length) btns[0].click(); }"
        )
        pg.wait_for_timeout(2500)
        if pg.evaluate("() => !!document.querySelector('[role=dialog]')"):
            break
    pg.wait_for_timeout(2000)

    check = pg.evaluate(
        """() => {
          const dlg = document.querySelector('[role=dialog]');
          const q = [...dlg.querySelectorAll('.border')].find(el => el.textContent.includes('乙醚'));
          if (!q) return { found: false };
          // 可见层（katex-html）文本
          const visibleHtml = [...q.querySelectorAll('.katex-html')].map(e => e.textContent);
          const visibleText = visibleHtml.join(' ');
          // MathML 是否被 CSS 隐藏
          const mathml = q.querySelector('.katex-mathml');
          const mathmlHidden = mathml ? (getComputedStyle(mathml).clip !== 'auto' || getComputedStyle(mathml).position === 'absolute') : 'no-mathml';
          // 选项分行：检查 <p> 元素
          const ps = [...q.querySelectorAll('p')].map(p => p.textContent.slice(0, 30));
          return {
            found: true,
            visible75Count: (visibleText.match(/75%/g) || []).length,
            visibleHasRawPercent: visibleText.includes('75\\\\%') || visibleText.includes('75%25'),
            mathmlHidden,
            optionPs: ps.filter(t => /^[A-D]/.test(t)),
            spacedRemnant: visibleText.includes('C H 3') || q.textContent.includes('C H 3'),
            zwspVisible: visibleText.includes('\\u200b'),
          };
        }"""
    )
    print("t1 check:", check)
    pg.screenshot(path="docs/ui-review/29-t1-single-version.png")
    b.close()

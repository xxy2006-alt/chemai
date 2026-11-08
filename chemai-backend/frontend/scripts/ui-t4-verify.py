# ui-t4-verify.py — t4 渲染 + 题型区/新建/打印验证
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
    pg.wait_for_timeout(3500)

    # 题型区
    dump = pg.evaluate(
        """() => {
          const card = [...document.querySelectorAll('main .border')].find(el => el.textContent.includes('题型与数量'));
          const chips = card ? [...card.querySelectorAll('button')].filter(b => /单选|多选|填空|计算|实验|推断/.test(b.textContent)).map(b => b.textContent.trim().slice(0, 6)) : [];
          return {
            chips,
            hasNewFolder: [...document.querySelectorAll('main button')].some(b => b.textContent.includes('新建题库')),
            hasPrint: [...document.querySelectorAll('main button')].some(b => b.textContent.includes('打印预览')),
          };
        }"""
    )
    print("1. 题型/新建/打印:", dump)

    # t4 弹窗
    pg.click("button:has-text('历史真题库')")
    pg.wait_for_timeout(3000)
    for _ in range(5):
        pg.evaluate("() => { const b=[...document.querySelectorAll('main button')].filter(x => /全国卷2020/.test(x.textContent)); if (b.length) b[0].click(); }")
        pg.wait_for_timeout(2500)
        if pg.evaluate("() => !!document.querySelector('[role=dialog]')"):
            break
    t4 = pg.evaluate(
        """() => {
          const dlg = document.querySelector('[role=dialog]');
          const q = [...dlg.querySelectorAll('.border')].find(el => el.textContent.includes('铑'));
          if (!q) return { found: false };
          const html = q.innerHTML;
          const visible = q.innerText;
          const imgs = [...q.querySelectorAll('img')].map(i => i.src.split('/').pop());
          return {
            found: true,
            subRendered: html.includes('<sub>3</sub>'),
            subVisible: visible.includes('<sub>3</sub>'),
            eqSingleLine: visible.includes('COI+H') && !visible.includes('COI+H\\n='),
            imgNames: imgs,
            ed9966count: imgs.filter(f => f.includes('ed9966')).length,
            katexErr: q.querySelectorAll('.katex-error').length,
          };
        }"""
    )
    print("2. t4:", t4)
    pg.screenshot(path="docs/ui-review/31-t4-fixed.png")
    non502 = [e for e in errs if "502" not in e]
    print("console(非502):", len(non502))
    b.close()

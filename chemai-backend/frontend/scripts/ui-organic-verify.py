# ui-organic-verify.py — 有机题：答案公式 KaTeX 渲染 + 结构图显示（UI 侧验证）
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

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

    # 选择知识点：有机化合物 + 酯化反应
    pg.evaluate("""() => {
      const btns = [...document.querySelectorAll('main button')];
      const kp = btns.find(b => b.textContent.includes('有机化合物'));
      if (kp) kp.click();
      const kp2 = btns.find(b => b.textContent.includes('酯化反应'));
      if (kp2) kp2.click();
    }""")
    pg.wait_for_timeout(500)
    # 单选/多选/填空 各选一个（默认单选已选中）
    pg.evaluate("""() => {
      const btns = [...document.querySelectorAll('main button')];
      const mc = btns.find(b => b.textContent.includes('多选'));
      if (mc) mc.click();
    }""")
    pg.wait_for_timeout(300)
    # AI 生成
    pg.click("button:has-text('AI 生成题目')")
    pg.wait_for_timeout(40000)

    result = pg.evaluate(
        """() => {
          const main = document.querySelector('main');
          const html = main.innerHTML;
          const cards = [...main.querySelectorAll('.border')].filter(el => el.textContent.includes('#1') || el.textContent.includes('答案'));
          return {
            katexCount: main.querySelectorAll('.katex').length,
            structureImgs: [...main.querySelectorAll('img')].filter(i => i.src.includes('question_images')).map(i => i.src.split('/').pop()),
            rawDollarVisible: /\\$CH_3|\\$C_2H_5|\\$CO_2\\$/.test(main.innerText),
            answerLabel: [...main.querySelectorAll('span')].filter(s => s.textContent.trim() === '答案').length,
            cardCount: cards.length,
          };
        }"""
    )
    print("1. 生成结果:", result)
    pg.screenshot(path="docs/ui-review/39-organic-question.png", full_page=False)
    print("   截图 docs/ui-review/39-organic-question.png")

    # 历史真题弹窗里的答案也走 KaTeX（抽查 t1 答案）
    pg.click("button:has-text('历史真题库')")
    pg.wait_for_timeout(3000)
    for _ in range(5):
        pg.evaluate(
            "() => { const b=[...document.querySelectorAll('main button')].filter(x => /全国卷2020/.test(x.textContent)); if (b.length) b[0].click(); }"
        )
        pg.wait_for_timeout(2500)
        if pg.evaluate("() => !!document.querySelector('[role=dialog]')"):
            break
    dlg = pg.evaluate(
        """() => {
          const d = document.querySelector('[role=dialog]');
          if (!d) return { found: false };
          return {
            found: true,
            answerLabels: [...d.querySelectorAll('span')].filter(s => s.textContent.trim() === '答案').length,
            katexInAnswers: [...d.querySelectorAll('.katex')].length,
          };
        }"""
    )
    print("2. 历史真题弹窗:", dlg)
    pg.screenshot(path="docs/ui-review/40-history-answers.png")

    non502 = [e for e in errs if "502" not in e and "Failed to load resource" not in e]
    print("console(非502):", len(non502))
    b.close()

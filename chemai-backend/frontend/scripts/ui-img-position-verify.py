# ui-img-position-verify.py — 题目配图位置整理验证（evals 的 UI 侧抽查）
# 回归用户反馈：「图片放在题目的位置有问题，图片应该在答案和题目内容的中间」
# 检查历史真题弹窗：T1 配图必须出现在【分析】之前（题干之后），且不重复。
# 用法：python scripts/ui-img-position-verify.py
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

    pg.click("button:has-text('历史真题库')")
    pg.wait_for_timeout(3000)
    for _ in range(5):
        pg.evaluate(
            "() => { const b=[...document.querySelectorAll('main button')].filter(x => /全国卷2020/.test(x.textContent)); if (b.length) b[0].click(); }"
        )
        pg.wait_for_timeout(2500)
        if pg.evaluate("() => !!document.querySelector('[role=dialog]')"):
            break

    # T1：国家卫健委/乙醚 题 —— 图片原本在【点评】之后（题目底部）
    t1 = pg.evaluate(
        """() => {
          const dlg = document.querySelector('[role=dialog]');
          const q = [...dlg.querySelectorAll('.border')].find(el => el.textContent.includes('乙醚'));
          if (!q) return { found: false };
          const imgs = [...q.querySelectorAll('img')];
          // 【分析】文本节点在 DOM 中的位置
          const walker = document.createTreeWalker(q, NodeFilter.SHOW_TEXT);
          let anaEl = null;
          while (walker.nextNode()) {
            if (walker.currentNode.textContent.includes('【分析】')) { anaEl = walker.currentNode; break; }
          }
          const pos = imgs.map(img => {
            if (!anaEl) return 'no-ana';
            return img.compareDocumentPosition(anaEl) & Node.DOCUMENT_POSITION_FOLLOWING ? 'before-ana(题干后)' : 'after-ana';
          });
          return {
            found: true,
            imgCount: imgs.length,
            imgPositions: pos,
            hasImgAfterAnswer: imgs.some(img => {
              const ansEl = [...q.querySelectorAll('span')].find(s => s.textContent.includes('答案:'));
              return ansEl && (img.compareDocumentPosition(ansEl) & Node.DOCUMENT_POSITION_FOLLOWING) === 0;
            }),
          };
        }"""
    )
    print("T1(乙醚题):", t1)

    # T6：电池示意图 —— 图紧跟题干，应在【分析】前且仅 1 张
    t6 = pg.evaluate(
        """() => {
          const dlg = document.querySelector('[role=dialog]');
          const q = [...dlg.querySelectorAll('.border')].find(el => el.textContent.includes('水介质电池'));
          if (!q) return { found: false };
          const imgs = [...q.querySelectorAll('img')];
          const walker = document.createTreeWalker(q, NodeFilter.SHOW_TEXT);
          let anaEl = null;
          while (walker.nextNode()) {
            if (walker.currentNode.textContent.includes('【分析】')) { anaEl = walker.currentNode; break; }
          }
          return {
            found: true,
            imgCount: imgs.length,
            allBeforeAna: imgs.every(img => anaEl && (img.compareDocumentPosition(anaEl) & Node.DOCUMENT_POSITION_FOLLOWING)),
          };
        }"""
    )
    print("T6(电池题):", t6)

    pg.screenshot(path="docs/ui-review/32-img-position.png", full_page=False)
    non502 = [e for e in errs if "502" not in e and "Failed to load resource" not in e]
    print("console(非502):", len(non502))
    b.close()

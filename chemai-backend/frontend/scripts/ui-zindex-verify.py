# ui-zindex-verify.py — 复现用户场景：抽屉 → 历史计划 → 计划详情 层叠验证
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
    pg.wait_for_timeout(3000)
    pg.goto(BASE + "/#/students", wait_until="networkidle")
    pg.wait_for_timeout(3500)

    # 打开李世睿抽屉
    pg.evaluate(
        """() => {
          const rows = [...document.querySelectorAll('.ant-table-tbody .ant-table-row')];
          const row = rows.find(r => r.innerText.includes('李世睿'));
          if (row) row.click();
        }"""
    )
    pg.wait_for_timeout(2500)

    # 点「历史计划」
    pg.evaluate(
        """() => {
          const btn = [...document.querySelectorAll('.ant-drawer button')].find(x => x.textContent.includes('历史计划'));
          if (btn) btn.click();
        }"""
    )
    pg.wait_for_timeout(2500)

    def z_of(sel):
        return pg.evaluate(
            """(sel) => {
              const el = document.querySelector(sel);
              if (!el) return null;
              const z = getComputedStyle(el).zIndex;
              const r = el.getBoundingClientRect();
              return { z, x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) };
            }""",
            sel,
        )

    drawer = z_of('.ant-drawer')
    hist = z_of('[role="dialog"]')
    print("1. 抽屉 vs 历史计划弹窗:")
    print("   drawer:", drawer)
    print("   history modal:", hist)
    # 历史弹窗中心是否在抽屉之上（弹窗的 y 是否比抽屉遮罩低不重要，关键 z 与可视）
    modal_on_top = hist and drawer and int(hist['z']) > int(drawer['z'])
    print("   历史计划 z > 抽屉 z:", modal_on_top)
    pg.screenshot(path="docs/ui-review/63-zindex-history-over-drawer.png")

    # 关抽屉 → 历史计划仍在
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(1500)
    hist2 = z_of('[role="dialog"]')
    print("2. 关抽屉后历史计划弹窗:", hist2 is not None)
    pg.screenshot(path="docs/ui-review/64-zindex-history-after-close.png")

    # 历史计划里选第一个计划 → 计划详情弹窗应在历史计划之上
    clicked = pg.evaluate(
        """() => {
          const dlg = document.querySelector('[role="dialog"]');
          if (!dlg) return false;
          const items = [...dlg.querySelectorAll('button')].filter(x => x.textContent.includes('查看'));
          if (items.length) { items[0].click(); return true; }
          return false;
        }"""
    )
    pg.wait_for_timeout(2500)
    dialogs = pg.evaluate(
        """() => {
          const dls = [...document.querySelectorAll('[role="dialog"]')];
          return dls.map(d => {
            const z = getComputedStyle(d).zIndex;
            const txt = d.innerText.slice(0, 30).replace(/\\n/g, ' ');
            return { z, txt };
          });
        }"""
    )
    print("3. 两个弹窗叠放:", dialogs)
    pg.screenshot(path="docs/ui-review/65-zindex-plan-over-history.png")

    non502 = [e for e in errs if "502" not in e and "Failed to load resource" not in e]
    print("console(非502):", len(non502))
    b.close()

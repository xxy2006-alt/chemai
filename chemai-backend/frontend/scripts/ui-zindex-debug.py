# ui-zindex-debug.py — 在 localhost:3000 实测抽屉 vs 历史计划弹窗的真实层叠
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

BASE = "http://localhost:3000"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto(BASE + "/#/login", wait_until="networkidle")
    pg.fill("input[placeholder='请输入账号']", "hai")
    pg.fill("input[type=password]", "hai123456")
    pg.click("button[type=submit]")
    pg.wait_for_timeout(3000)
    pg.goto(BASE + "/#/students", wait_until="networkidle")
    pg.wait_for_timeout(3500)

    # 页面根是否有 transform（stacking context 根因候选）
    root_info = pg.evaluate(
        """() => {
          const main = document.querySelector('main');
          const pageRoot = main ? main.firstElementChild : null;
          if (!pageRoot) return null;
          const cs = getComputedStyle(pageRoot);
          return {
            cls: pageRoot.className.slice(0, 60),
            transform: cs.transform,
            animation: cs.animationName,
            zIndex: cs.zIndex,
          };
        }"""
    )
    print("1. 页面根:", root_info)

    # 开李世睿抽屉
    pg.evaluate(
        """() => {
          const rows = [...document.querySelectorAll('.ant-table-tbody .ant-table-row')];
          const row = rows.find(r => r.innerText.includes('李世睿'));
          if (row) row.click();
        }"""
    )
    pg.wait_for_timeout(2500)

    # 点历史计划
    pg.evaluate(
        """() => {
          const btn = [...document.querySelectorAll('.ant-drawer button')].find(x => x.textContent.includes('历史计划'));
          if (btn) btn.click();
        }"""
    )
    pg.wait_for_timeout(2500)

    # 弹窗中心点 elementFromPoint — 看实际被谁覆盖
    probe = pg.evaluate(
        """() => {
          const dlg = [...document.querySelectorAll('[role="dialog"]')].find(d => d.textContent.includes('历史学习计划'));
          if (!dlg) return { found: false };
          const panel = dlg.querySelector('.bg-surface') || dlg;
          const r = panel.getBoundingClientRect();
          const cx = r.x + r.width / 2;
          const cy = r.y + r.height / 2;
          const hit = document.elementFromPoint(cx, cy);
          const walk = (el) => {
            const out = [];
            let cur = el;
            while (cur && cur !== document.body) {
              const cs = getComputedStyle(cur);
              out.push({ tag: cur.tagName, cls: (cur.className || '').toString().slice(0, 50), z: cs.zIndex, pos: cs.position, transform: cs.transform.slice(0, 40) });
              cur = cur.parentElement;
            }
            return out;
          };
          return {
            found: true,
            panelRect: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) },
            hitAtCenter: hit ? hit.className.toString().slice(0, 60) : null,
            hitChain: hit ? walk(hit).slice(0, 6) : [],
            dlgZ: getComputedStyle(dlg).zIndex,
            dlgPos: getComputedStyle(dlg).position,
            dlgParent: dlg.parentElement ? dlg.parentElement.className.toString().slice(0, 60) : 'none',
          };
        }"""
    )
    print("2. 弹窗中心点击命中:", probe)
    pg.screenshot(path="docs/ui-review/66-zindex-debug.png")
    b.close()

# ui-round2-verify2.py — 第二轮验证补充：删除确认弹窗（hover）+ 诊断 Statistic（跑一次诊断）
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

    # 删除题库 → antd Modal.confirm（先 hover 显示删除按钮）
    pg.goto(BASE + "/#/exam", wait_until="networkidle")
    pg.wait_for_timeout(3500)
    pg.evaluate("() => { const t=[...document.querySelectorAll('.ant-tabs-tab')].find(x=>x.textContent.includes('题库管理')); if (t) t.click(); }")
    pg.wait_for_timeout(2500)
    r2 = pg.evaluate(
        """() => {
          const main = document.querySelector('main');
          // 题库行（.group）内的删除图标按钮（Trash2，无 title/text）
          const group = main.querySelector('.group');
          if (!group) return false;
          const btns = [...group.querySelectorAll('button')];
          const del = btns.find(x => x.querySelector('svg'));
          if (del) { del.click(); return true; }
          return false;
        }"""
    )
    pg.wait_for_timeout(1500)
    r3 = pg.evaluate(
        """() => {
          const modal = document.querySelector('.ant-modal-confirm');
          return {
            hasConfirmModal: !!modal,
            confirmText: modal ? modal.textContent.slice(0, 50) : '',
            hasDangerBtn: !!document.querySelector('.ant-modal-confirm .ant-btn-dangerous'),
            hasOk: !!document.querySelector('.ant-modal-confirm .ant-btn-primary'),
          };
        }"""
    )
    print("1. 删除确认弹窗:", r3)
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(800)
    pg.screenshot(path="docs/ui-review/61-round2-confirm.png")

    # 诊断分析：先选班级+考试，跑一次诊断 → Statistic
    pg.goto(BASE + "/#/diagnosis", wait_until="networkidle")
    pg.wait_for_timeout(3500)
    pg.evaluate(
        """() => {
          const selects = document.querySelectorAll('.ant-select, main select');
          // 班级/考试下拉：页面自研 Select 触发 onChange 较难，直接点诊断按钮前先看表单
          const btn = [...document.querySelectorAll('main button')].find(x => x.textContent.includes('开始诊断') || x.textContent.includes('诊断'));
          return { hasDiagBtn: !!btn, selectCount: selects.length };
        }"""
    )
    pg.wait_for_timeout(800)
    # 尝试选班级
    pg.evaluate(
        """() => {
          const sel = document.querySelector('main select');
          if (sel && sel.options.length > 1) {
            sel.value = sel.options[1].value;
            sel.dispatchEvent(new Event('change', { bubbles: true }));
          }
        }"""
    )
    pg.wait_for_timeout(1000)
    # 第二个下拉（考试）
    pg.evaluate(
        """() => {
          const sels = [...document.querySelectorAll('main select')];
          const sel = sels[1];
          if (sel && sel.options.length > 1) {
            sel.value = sel.options[1].value;
            sel.dispatchEvent(new Event('change', { bubbles: true }));
          }
        }"""
    )
    pg.wait_for_timeout(1000)
    pg.evaluate(
        """() => {
          const btn = [...document.querySelectorAll('main button')].find(x => x.textContent.includes('开始诊断'));
          if (btn) btn.click();
        }"""
    )
    pg.wait_for_timeout(6000)
    r4 = pg.evaluate(
        """() => {
          const main = document.querySelector('main');
          return {
            hasStatistic: !!main.querySelector('.ant-statistic'),
            statisticCount: main.querySelectorAll('.ant-statistic').length,
            bodyHasMastery: main.innerText.includes('掌握度'),
          };
        }"""
    )
    print("2. 诊断 Statistic:", r4)
    pg.screenshot(path="docs/ui-review/62-round2-diagnosis.png")

    non502 = [e for e in errs if "502" not in e and "Failed to load resource" not in e]
    print("console(非502):", len(non502))
    b.close()

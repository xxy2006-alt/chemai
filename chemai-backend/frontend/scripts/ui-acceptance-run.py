# ui-acceptance-run.py — 验收一键脚本：跑验收清单关键路径，输出 PASS/FAIL 报告
# 用法：python scripts/ui-acceptance-run.py
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

BASE = "http://localhost:3000"
results = []

def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    errs = []
    pg.on("console", lambda m: errs.append(m.text[:120]) if m.type == "error" else None)

    # ① 登录（antd 表单）
    pg.goto(BASE + "/#/login", wait_until="networkidle")
    check("登录页 antd 表单渲染", pg.evaluate("() => !!document.querySelector('.ant-input-password') && !!document.querySelector('button[type=submit]')"))
    pg.fill("input[placeholder='请输入账号']", "hai")
    pg.fill("input[type=password]", "hai123456")
    pg.click("button[type=submit]")
    pg.wait_for_timeout(3000)
    check("登录成功进入对话页", pg.evaluate("() => location.hash.includes('/chat')"))

    # ② 学生管理：李世睿置顶 + 抽屉 + 历史计划层级
    pg.goto(BASE + "/#/students", wait_until="networkidle")
    pg.wait_for_timeout(3500)
    first_row = pg.evaluate("() => document.querySelector('.ant-table-tbody .ant-table-row')?.innerText || ''")
    check("李世睿置顶第一行", "李世睿" in first_row, first_row[:40])
    pg.evaluate("() => { const rows=[...document.querySelectorAll('.ant-table-tbody .ant-table-row')]; rows.find(r=>r.innerText.includes('李世睿'))?.click(); }")
    pg.wait_for_timeout(2200)
    check("抽屉打开(Statistic/Progress)", pg.evaluate("() => !!document.querySelector('.ant-statistic') && !!document.querySelector('.ant-progress')"))
    pg.evaluate("() => { const b=[...document.querySelectorAll('.ant-drawer button')].find(x=>x.textContent.includes('历史计划')); b?.click(); }")
    pg.wait_for_timeout(2200)
    on_top = pg.evaluate(
        """() => {
          const dlg = [...document.querySelectorAll('[role="dialog"]')].find(d => d.textContent.includes('历史学习计划'));
          if (!dlg) return false;
          const r = dlg.getBoundingClientRect();
          const hit = document.elementFromPoint(r.x + r.width/2, r.y + 40);
          return hit ? (hit.closest('[role="dialog"]') === dlg || dlg.contains(hit)) : false;
        }"""
    )
    check("历史计划弹窗在抽屉之上(可交互)", on_top)
    pg.evaluate("() => { const c=document.querySelector('.ant-modal-close'); c?.click(); }")
    pg.wait_for_timeout(800)

    # ③ 出题工作台：组卷打印入口 + 题型 chips
    pg.goto(BASE + "/#/exam", wait_until="networkidle")
    pg.wait_for_timeout(3500)
    check("题型 CheckableTag(6种)", pg.evaluate("() => document.querySelectorAll('.ant-tag-checkable').length >= 6"))
    check("组卷打印按钮存在", pg.evaluate("() => [...document.querySelectorAll('main button')].some(x => x.textContent.includes('组卷打印'))"))

    # ④ 题库管理：批量栏 + 单题操作
    pg.evaluate("() => { const t=[...document.querySelectorAll('.ant-tabs-tab')].find(x=>x.textContent.includes('题库管理')); t?.click(); }")
    pg.wait_for_timeout(2000)
    pg.evaluate("() => { const it=[...document.querySelectorAll('main button')].find(x=>/\\d+ 题/.test(x.textContent)); it?.click(); }")
    pg.wait_for_timeout(1800)
    check("题库批量栏(全选/加入考试)", pg.evaluate("() => document.querySelector('main').innerText.includes('已选 0 题')"))
    check("题库单题删除按钮", pg.evaluate("() => [...document.querySelectorAll('main button')].some(x => x.textContent.includes('删除'))"))
    check("题库单题加入考试按钮", pg.evaluate("() => [...document.querySelectorAll('main button')].some(x => x.textContent.includes('加入考试'))"))

    # ⑤ 诊断页 Statistic
    pg.goto(BASE + "/#/diagnosis", wait_until="networkidle")
    pg.wait_for_timeout(3000)
    check("诊断页可加载(无错误文案)", pg.evaluate("() => !document.querySelector('main').innerText.includes('加载失败')"))

    # 汇总
    print("\n=== 验收报告 ===")
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"通过 {passed}/{len(results)}")
    for name, ok, detail in results:
        if not ok:
            print(f"  FAILED: {name} {detail}")
    non502 = [e for e in errs if "Failed to load resource" not in e]
    print("console 错误:", len(non502))
    b.close()

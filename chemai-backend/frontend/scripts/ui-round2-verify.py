# ui-round2-verify.py — 第二轮优化验证：Tabs/CheckableTag/Statistic/Modal.confirm
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

    # 出题工作台：antd Tabs + Segmented + CheckableTag
    pg.goto(BASE + "/#/exam", wait_until="networkidle")
    pg.wait_for_timeout(3500)
    r = pg.evaluate(
        """() => {
          const main = document.querySelector('main');
          return {
            hasAntdTabs: !!main.querySelector('.ant-tabs'),
            tabLabels: [...main.querySelectorAll('.ant-tabs-tab')].map(t => t.textContent.trim()),
            hasSegmented: !!main.querySelector('.ant-segmented'),
            segLabels: [...main.querySelectorAll('.ant-segmented-item-label')].map(t => t.textContent.trim()),
            hasCheckableTag: !!main.querySelector('.ant-tag-checkable'),
            checkableLabels: [...main.querySelectorAll('.ant-tag-checkable')].map(t => t.textContent.trim()),
            hasInputNumber: !!main.querySelector('.ant-input-number'),
          };
        }"""
    )
    print("1. 出题工作台:", r)
    pg.screenshot(path="docs/ui-review/60-round2-exam.png")

    # 删除题库 → antd Modal.confirm
    pg.evaluate("() => { const t=[...document.querySelectorAll('.ant-tabs-tab')].find(x=>x.textContent.includes('题库管理')); if (t) t.click(); }")
    pg.wait_for_timeout(2500)
    r2 = pg.evaluate(
        """() => {
          const main = document.querySelector('main');
          const del = [...main.querySelectorAll('button')].find(x => x.title === '删除题库' || x.textContent.includes('删除'));
          if (del) del.click();
          return { clicked: !!del };
        }"""
    )
    pg.wait_for_timeout(1500)
    r3 = pg.evaluate(
        """() => {
          const modal = document.querySelector('.ant-modal-confirm');
          return {
            hasConfirmModal: !!modal,
            confirmText: modal ? modal.textContent.slice(0, 60) : '',
            hasDangerBtn: !!document.querySelector('.ant-modal-confirm .ant-btn-dangerous'),
          };
        }"""
    )
    print("2. 删除确认弹窗:", r3)
    pg.keyboard.press("Escape")
    pg.screenshot(path="docs/ui-review/61-round2-confirm.png")

    # 诊断分析：antd Statistic
    pg.goto(BASE + "/#/diagnosis", wait_until="networkidle")
    pg.wait_for_timeout(3500)
    r4 = pg.evaluate(
        """() => {
          const main = document.querySelector('main');
          return {
            hasStatistic: !!main.querySelector('.ant-statistic'),
            statisticCount: main.querySelectorAll('.ant-statistic').length,
          };
        }"""
    )
    print("3. 诊断分析:", r4)
    pg.screenshot(path="docs/ui-review/62-round2-diagnosis.png")

    non502 = [e for e in errs if "502" not in e and "Failed to load resource" not in e]
    print("console(非502):", len(non502))
    b.close()

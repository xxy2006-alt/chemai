# ui-antd-final.py — antd 接入全页面验证（登录/学生/班级/出题/OCR）
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

    # 班级学情
    pg.goto(BASE + "/#/class", wait_until="networkidle")
    pg.wait_for_timeout(3500)
    r = pg.evaluate(
        """() => {
          const main = document.querySelector('main');
          return {
            hasStatistic: !!main.querySelector('.ant-statistic'),
            hasAntdSelect: !!main.querySelector('.ant-select'),
            hasAntdTable: !!main.querySelector('.ant-table'),
            hasEChart: !!main.querySelector('canvas'),
          };
        }"""
    )
    print("1. 班级学情:", r)
    pg.screenshot(path="docs/ui-review/53-antd-class.png")

    # 出题工作台
    pg.goto(BASE + "/#/exam", wait_until="networkidle")
    pg.wait_for_timeout(3500)
    r = pg.evaluate(
        """() => {
          const main = document.querySelector('main');
          return {
            hasAntdSelect: main.querySelectorAll('.ant-select').length,
            hasAntdInput: !!main.querySelector('.ant-input'),
          };
        }"""
    )
    print("2. 出题工作台:", r)
    pg.screenshot(path="docs/ui-review/54-antd-exam.png")

    # 答题卡批改
    pg.goto(BASE + "/#/ocr", wait_until="networkidle")
    pg.wait_for_timeout(3000)
    r = pg.evaluate(
        """() => {
          const main = document.querySelector('main');
          return {
            hasDragger: !!main.querySelector('.ant-upload-drag'),
            draggerText: main.querySelector('.ant-upload-drag')?.innerText.slice(0, 60) || '',
          };
        }"""
    )
    print("3. 答题卡批改:", r)
    pg.screenshot(path="docs/ui-review/55-antd-ocr.png")

    # 学生管理表格 + 抽屉
    pg.goto(BASE + "/#/students", wait_until="networkidle")
    pg.wait_for_timeout(3500)
    pg.evaluate(
        """() => {
          const rows = [...document.querySelectorAll('.ant-table-tbody .ant-table-row')];
          const row = rows.find(r => r.innerText.includes('李世睿'));
          if (row) row.click();
        }"""
    )
    pg.wait_for_timeout(2500)
    r = pg.evaluate(
        """() => {
          const body = document.body;
          return {
            hasTable: !!body.querySelector('.ant-table'),
            hasDrawer: !!body.querySelector('.ant-drawer'),
            hasProgress: !!body.querySelector('.ant-progress'),
            hasStatistic: !!body.querySelector('.ant-statistic'),
          };
        }"""
    )
    print("4. 学生管理+抽屉:", r)
    pg.screenshot(path="docs/ui-review/56-antd-students-drawer.png")

    non502 = [e for e in errs if "502" not in e and "Failed to load resource" not in e]
    print("console(非502):", len(non502))
    b.close()

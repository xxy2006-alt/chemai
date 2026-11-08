# ui-antd-verify.py — antd 接入验证：登录页表单 / 学生表格 / 详情抽屉
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8001"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    errs = []
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)

    # 登录页（antd Form）
    pg.goto(BASE + "/#/login", wait_until="networkidle")
    pg.wait_for_timeout(2500)
    r1 = pg.evaluate(
        """() => {
          const body = document.body;
          return {
            hasAntdInput: !!document.querySelector('.ant-input'),
            hasAntdBtn: !!document.querySelector('.ant-btn-primary'),
            hasAntdCheckbox: !!document.querySelector('.ant-checkbox'),
            placeholder: document.querySelector('.ant-input')?.getAttribute('placeholder'),
          };
        }"""
    )
    print("1. 登录页 antd:", r1)
    pg.screenshot(path="docs/ui-review/50-antd-login.png")

    # 登录
    pg.fill("input[placeholder='请输入账号']", "hai")
    pg.fill("input[type=password]", "hai123456")
    pg.click("button[type=submit]")
    pg.wait_for_timeout(3000)

    # 学生管理（antd Table）
    pg.goto(BASE + "/#/students", wait_until="networkidle")
    pg.wait_for_timeout(3500)
    r2 = pg.evaluate(
        """() => {
          const main = document.querySelector('main');
          const table = main.querySelector('.ant-table');
          const rows = main.querySelectorAll('.ant-table-tbody .ant-table-row');
          return {
            hasAntdTable: !!table,
            rowCount: rows.length,
            firstRowText: rows[0] ? rows[0].innerText.slice(0, 60) : '',
            hasPagination: !!main.querySelector('.ant-pagination'),
            hasAntdTag: !!main.querySelector('.ant-tag'),
          };
        }"""
    )
    print("2. 学生表格:", r2)
    pg.screenshot(path="docs/ui-review/51-antd-students.png")

    # 打开李世睿抽屉（第一行 = 李世睿）
    pg.evaluate(
        """() => {
          const rows = [...document.querySelectorAll('.ant-table-tbody .ant-table-row')];
          const row = rows.find(r => r.innerText.includes('李世睿'));
          if (row) row.click();
        }"""
    )
    pg.wait_for_timeout(2500)
    r3 = pg.evaluate(
        """() => {
          const body = document.body;
          const drawer = document.querySelector('.ant-drawer');
          return {
            hasDrawer: !!drawer,
            drawerText: drawer ? drawer.innerText.slice(0, 120).replace(/\\n/g, ' | ') : '',
            hasStatistic: !!document.querySelector('.ant-statistic'),
            hasProgress: !!document.querySelector('.ant-progress'),
            hasTable: !!document.querySelector('.ant-table'),
          };
        }"""
    )
    print("3. 李世睿抽屉:", r3)
    pg.screenshot(path="docs/ui-review/52-antd-lyx-drawer.png")

    non502 = [e for e in errs if "502" not in e and "Failed to load resource" not in e]
    print("console(非502):", len(non502))
    b.close()

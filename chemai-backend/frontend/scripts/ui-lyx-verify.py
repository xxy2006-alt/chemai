# ui-lyx-verify.py — 验证李世睿在教师端/家长端的可见性
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8001"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})

    # ── 教师端：学生管理 ──
    pg.goto(BASE + "/#/login", wait_until="networkidle")
    pg.fill("input[placeholder='请输入账号']", "hai")
    pg.fill("input[type=password]", "hai123456")
    pg.click("button[type=submit]")
    pg.wait_for_timeout(2500)
    pg.goto(BASE + "/#/students", wait_until="networkidle")
    pg.wait_for_timeout(3000)

    # 页面文本里找 李世睿
    body = pg.evaluate("() => document.querySelector('main').innerText")
    print("1. 学生管理页含'李世睿':", "李世睿" in body)
    print("   含'202610201':", "202610201" in body)

    # 搜索
    try:
        pg.fill("input[placeholder*='搜索']", "李世睿")
        pg.wait_for_timeout(800)
        body2 = pg.evaluate("() => document.querySelector('main').innerText")
        print("2. 搜索'李世睿'后可见:", "李世睿" in body2)
        pg.screenshot(path="docs/ui-review/33-lyx-students.png")
    except Exception as e:
        print("2. 搜索失败:", str(e)[:100])

    # ── 班级学情 ──
    pg.goto(BASE + "/#/class", wait_until="networkidle")
    pg.wait_for_timeout(3500)
    body3 = pg.evaluate("() => document.querySelector('main').innerText")
    print("3. 班级学情含'李世睿':", "李世睿" in body3)
    pg.screenshot(path="docs/ui-review/34-lyx-class.png")

    # ── 家长端：李国华 lgh ──
    pg.goto(BASE + "/m/", wait_until="networkidle")
    pg.wait_for_timeout(2500)
    print("4. m/ 页面标题:", pg.title()[:60])
    pg.screenshot(path="docs/ui-review/35-lyx-m-home.png")
    b.close()

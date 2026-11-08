# ui-lyx-verify3.py — 学生管理首屏置顶 + 家长端(m/parent-login)绑定
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8001"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    errs = []
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)

    # ── 教师端：学生管理首屏 ──
    pg.goto(BASE + "/#/login", wait_until="networkidle")
    pg.fill("input[placeholder='请输入账号']", "hai")
    pg.fill("input[type=password]", "hai123456")
    pg.click("button[type=submit]")
    pg.wait_for_timeout(2500)
    pg.goto(BASE + "/#/students", wait_until="networkidle")
    pg.wait_for_timeout(3000)
    body = pg.evaluate("() => document.querySelector('main').innerText")
    print("1. 学生管理首屏含'李世睿':", "李世睿" in body)
    # 第一张学生卡内容
    first = pg.evaluate(
        """() => {
          const cards = [...document.querySelectorAll('main')];
          const t = document.querySelector('main').innerText;
          const idx = t.indexOf('李世睿');
          return idx >= 0 ? t.slice(Math.max(0, idx - 30), idx + 20).replace(/\\n/g, ' ') : 'NOT FOUND';
        }"""
    )
    print("   首屏李世睿上下文:", first)
    pg.screenshot(path="docs/ui-review/36-lyx-students-sorted.png")

    # ── 家长端：parent-login.html lgh ──
    pg.goto(BASE + "/m/parent-login.html", wait_until="networkidle")
    pg.wait_for_timeout(2000)
    try:
        inputs = pg.evaluate(
            "() => [...document.querySelectorAll('input')].map(i => ({ type: i.type, ph: i.placeholder, id: i.id, name: i.name }))"
        )
        print("2. 家长登录页 inputs:", inputs)
        pg.fill("input[type=text], input[type=tel], input:not([type=password])", "lgh")
        pg.fill("input[type=password]", "123456")
        pg.click("#loginBtn")
        pg.wait_for_timeout(3500)
        mbody = pg.evaluate("() => document.body.innerText")
        print("   登录后含'李世睿':", "李世睿" in mbody)
        # 孩子卡片数量（李世睿出现次数）
        cnt = mbody.count("李世睿")
        print("   李世睿出现次数:", cnt)
        pg.screenshot(path="docs/ui-review/37-lyx-parent.png")
    except Exception as e:
        print("2. 家长端登录失败:", str(e)[:150])

    non502 = [e for e in errs if "502" not in e and "Failed to load resource" not in e]
    print("console(非502):", len(non502))
    b.close()

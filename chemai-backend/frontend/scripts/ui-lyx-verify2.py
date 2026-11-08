# ui-lyx-verify2.py — 学生管理首屏可见性 + 家长端绑定 + Agent 内联面板题型
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
    # 第一个学生卡片
    first = pg.evaluate(
        "() => { const cards=[...document.querySelectorAll('main .grid > div, main .border')]; const t=cards[0]?.innerText||''; return t.slice(0,40); }"
    )
    print("   首屏第一卡片:", first)
    pg.screenshot(path="docs/ui-review/36-lyx-students-sorted.png")

    # ── 家长端：李国华 lgh 登录 → 孩子列表 ──
    pg.goto(BASE + "/m/", wait_until="networkidle")
    pg.wait_for_timeout(2000)
    # m/ 登录页：账号 lgh
    try:
        pg.fill("input[type=text], input[placeholder*='账']", "lgh")
        pg.fill("input[type=password]", "123456")
        pg.click("button[type=submit], button:has-text('登录')")
        pg.wait_for_timeout(3000)
        mbody = pg.evaluate("() => document.body.innerText")
        print("2. 家长端(m/)登录后含'李世睿':", "李世睿" in mbody)
        print("   含'李国华':", "李国华" in mbody)
        pg.screenshot(path="docs/ui-review/37-lyx-parent.png")
    except Exception as e:
        print("2. 家长端登录失败:", str(e)[:120])

    # ── Agent 内联出题面板：题型 chips ──
    pg.goto(BASE + "/#/chat", wait_until="networkidle")
    pg.wait_for_timeout(2500)
    pg.fill("textarea", "帮我出3道氧化还原反应的题目")
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(15000)
    body3 = pg.evaluate("() => document.querySelector('main').innerText")
    print("3. Agent 回复含'出题工作台':", "出题工作台" in body3)
    chips = pg.evaluate(
        """() => {
          const panel = [...document.querySelectorAll('main *')].find(el => el.textContent.includes('出题工作台') && el.querySelector('input[type=number]'));
          const root = panel || document.querySelector('main');
          return ['单选','多选','填空','计算','实验','推断'].map(l => ({ l, found: root.textContent.includes(l) }));
        }"""
    )
    print("   题型chips:", chips)
    pg.screenshot(path="docs/ui-review/38-inline-panel-types.png")

    non502 = [e for e in errs if "502" not in e and "Failed to load resource" not in e]
    print("console(非502):", len(non502))
    b.close()

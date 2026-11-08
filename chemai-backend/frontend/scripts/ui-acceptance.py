# ui-acceptance.py — 端到端验收：真实后端 + 生产构建 + 真实登录
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8001"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    errs = []
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)

    # 1. 打开生产构建首页
    pg.goto(BASE + "/", wait_until="networkidle")
    pg.wait_for_timeout(600)
    print("1. 首页:", pg.title(), "| 已登录态:", pg.evaluate("() => !!localStorage.getItem('token')"))

    # 2. 真实登录
    pg.goto(BASE + "/#/login", wait_until="networkidle")
    pg.fill("input[placeholder='请输入账号']", "hai")
    pg.fill("input[type=password]", "hai123456")
    pg.click("button[type=submit]")
    pg.wait_for_timeout(2500)
    print("2. 登录后 URL:", pg.url, "| token:", pg.evaluate("() => (localStorage.getItem('token')||'').slice(0,12)+'...'"))

    # 3. 对话工作台（真实会话列表）
    pg.wait_for_timeout(1500)
    convs = pg.evaluate("() => document.querySelectorAll('aside + main, .main').length")
    text = pg.evaluate("() => document.body.innerText.slice(0, 200)")
    print("3. 对话页文本:", text.replace(chr(10), " | ")[:160])

    # 4. 班级学情（真实数据 + echarts 渲染）
    pg.goto(BASE + "/#/class", wait_until="networkidle")
    pg.wait_for_timeout(3500)
    stat = pg.evaluate("() => document.body.innerText.match(/考试次数|班级人数|最近均分/g) || []")
    canvases = pg.evaluate("() => document.querySelectorAll('canvas').length")
    full = pg.evaluate("() => document.body.innerText.slice(0, 400)")
    print("4. 学情页统计卡:", stat, "| echarts canvas:", canvases)
    print("   文本:", full.replace(chr(10), " | ")[:300])
    pg.screenshot(path="docs/ui-review/10-class-real-data.png")

    # 5. 学生管理（真实学生）
    pg.goto(BASE + "/#/students", wait_until="networkidle")
    pg.wait_for_timeout(3500)
    stext = pg.evaluate("() => document.body.innerText.slice(0, 400)")
    print("5. 学生页文本:", stext.replace(chr(10), " | ")[:300])

    # 6. 出题工作台（知识点真实加载）
    pg.goto(BASE + "/#/exam", wait_until="networkidle")
    pg.wait_for_timeout(3500)
    kp = pg.evaluate("() => { const btns=[...document.querySelectorAll('button')]; return btns.filter(b=>/盐类|电离|氧化/.test(b.textContent)).length }")
    print("6. 出题页知识点按钮命中:", kp)

    non502 = [e for e in errs if "502" not in e and "401" not in e]
    print("console errors(非502/401):", non502[:5])
    b.close()

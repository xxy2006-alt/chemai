# ui-final-check.py — 归档后最终巡检：教师端 8 页 + m/ 学生端 1 页
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.add_init_script("localStorage.setItem('token','review-token')")
    errs = []
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)

    pages = [
        ("http://localhost:3000/#/login", "login"),
        ("http://localhost:3000/#/chat", "chat"),
        ("http://localhost:3000/#/class", "class"),
        ("http://localhost:3000/#/students", "students"),
        ("http://localhost:3000/#/exam", "exam"),
        ("http://localhost:3000/#/diagnosis", "diagnosis"),
        ("http://localhost:3000/#/ocr", "ocr"),
        ("http://localhost:3000/#/ocr-sheets", "ocr-sheets"),
    ]
    for url, label in pages:
        pg.goto(url, wait_until="networkidle")
        pg.wait_for_timeout(400)
        broken = pg.eval_on_selector_all(
            "img",
            "els => els.filter(e => e.naturalWidth===0).map(e => e.src)",
        )
        print(label, "OK" if not broken else f"BROKEN IMGS: {broken}")

    # m/ 学生端旧页面兼容（经 vite dev 静态服务）
    pg.goto("http://localhost:3000/m/index.html", wait_until="networkidle")
    pg.wait_for_timeout(600)
    m_ok = pg.evaluate("() => ({ title: document.title, hasChat: !!document.querySelector('.chat, .input-bar') })")
    print("m/index.html:", m_ok)

    # 旧教师端 URL 应不再可达（归档后 404）
    pg.goto("http://localhost:3000/pages/teacher.html", wait_until="networkidle")
    print("old /pages/teacher.html title:", pg.title())

    non502 = [e for e in errs if "502" not in e]
    print("console errors (非502):", non502[:5])
    b.close()

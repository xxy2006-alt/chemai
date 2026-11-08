# ui-assets-check.py — 验证素材加载
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.add_init_script("localStorage.setItem('token','review-token')")
    errs = []
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    for url, label in [
        ("http://localhost:3000/#/chat", "chat"),
        ("http://localhost:3000/#/login", "login"),
        ("http://localhost:3000/#/class", "class"),
        ("http://localhost:3000/#/students", "students"),
        ("http://localhost:3000/#/exam", "exam"),
        ("http://localhost:3000/#/diagnosis", "diagnosis"),
        ("http://localhost:3000/#/ocr", "ocr"),
        ("http://localhost:3000/#/ocr-sheets", "ocr-sheets"),
    ]:
        pg.goto(url, wait_until="networkidle")
        pg.wait_for_timeout(500)
        imgs = pg.eval_on_selector_all(
            "img",
            "els => els.map(e => e.src.split('/').slice(-2).join('/') + ' ' + (e.naturalWidth>0 ? 'OK' : 'BROKEN'))",
        )
        print(label, ":", imgs)
    print("console errors:", [e[:140] for e in errs])
    b.close()

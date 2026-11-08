# ui-final2-check.py — 懒加载 + 化学式实时预览验证
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.add_init_script("localStorage.setItem('token','review-token')")
    errs = []
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)

    for url, label in [
        ("http://localhost:3000/#/chat", "chat"),
        ("http://localhost:3000/#/class", "class(lazy+echarts)"),
        ("http://localhost:3000/#/students", "students(lazy)"),
        ("http://localhost:3000/#/exam", "exam(lazy)"),
    ]:
        pg.goto(url, wait_until="networkidle")
        pg.wait_for_timeout(700)
        try:
            broken = pg.eval_on_selector_all("img", "els => els.filter(e => e.naturalWidth===0).length")
            print(label, "OK" if not broken else f"BROKEN:{broken}")
        except Exception as e:
            pg.wait_for_timeout(800)
            try:
                broken = pg.eval_on_selector_all("img", "els => els.filter(e => e.naturalWidth===0).length")
                print(label, "OK(retry)" if not broken else f"BROKEN:{broken}")
            except Exception as e2:
                print(label, "EVAL FAIL:", str(e2)[:100])

    # 化学式实时预览：输入 Fe3+ + Cu2+ = Fe2+ + Cu
    pg.goto("http://localhost:3000/#/chat", wait_until="networkidle")
    pg.wait_for_timeout(400)
    pg.fill("textarea", "Fe3+ + Cu2+ = Fe2+ + Cu")
    pg.wait_for_timeout(300)
    info = pg.evaluate(
        "() => { const el = document.querySelector('.chem-mono'); "
        "return el ? { shown: el.offsetParent !== null, "
        "hasSuperscript: /[\u00b2\u00b3\u207a\u207b\u2082\u2083]/.test(el.textContent), "
        "len: el.textContent.length } : null }"
    )
    print("chem preview:", info)
    pg.screenshot(path="docs/ui-review/09-chat-chem-preview.png")

    non502 = [e for e in errs if "502" not in e]
    print("console errors (非502):", non502[:5])
    b.close()

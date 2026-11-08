# ui-console-only.py — 只抓 console 错误内容
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

BASE = "http://localhost:3000"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    errs = []
    pg.on("console", lambda m: errs.append(f"{m.type}: {m.text[:200]}") if m.type == "error" else None)
    pg.on("pageerror", lambda e: errs.append(f"PAGEERROR: {str(e)[:200]}"))

    pg.goto(BASE + "/#/login", wait_until="networkidle")
    pg.fill("input[placeholder='请输入账号']", "hai")
    pg.fill("input[type=password]", "hai123456")
    pg.click("button[type=submit]")
    pg.wait_for_timeout(3000)
    for path in ["/students", "/exam", "/class", "/diagnosis"]:
        pg.goto(BASE + "/#/" + path.lstrip("/"), wait_until="networkidle")
        pg.wait_for_timeout(3500)
    print("console/page 错误明细:", errs if errs else "无")
    b.close()

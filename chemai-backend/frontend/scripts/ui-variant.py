# ui-variant.py — 验证变种题功能（主工作台 + 内联面板）
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
    pg.wait_for_timeout(2500)

    # ── 主工作台 ──
    pg.goto(BASE + "/#/exam", wait_until="networkidle")
    pg.wait_for_timeout(2500)
    has_btn = pg.evaluate("() => [...document.querySelectorAll('main button')].some(b => b.textContent.includes('蓝本') && b.textContent.includes('作'))")
    print("1. 主工作台「选真题作蓝本」按钮:", has_btn)

    # 点击打开蓝本弹窗 → 目录 → 打开 2020 全国卷 → 选题
    pg.evaluate("() => { const btns=[...document.querySelectorAll('main button')].filter(b => b.textContent.includes('蓝本') && b.textContent.includes('作')); if (btns.length) btns[0].click(); }")
    pg.wait_for_timeout(2000)
    dir_ok = pg.evaluate("() => !!document.querySelector('[role=dialog]')")
    print("2. 蓝本弹窗打开:", dir_ok)
    pg.evaluate("() => { const btns=[...document.querySelectorAll('[role=dialog] button')].filter(b => b.textContent.includes('2020')); if (btns.length) btns[0].click(); }")
    pg.wait_for_timeout(2500)
    qs = pg.evaluate("() => document.querySelectorAll('[role=dialog] .overflow-y-auto button').length")
    print("3. 2020 卷题目按钮数:", qs)
    pg.evaluate("() => { const btns=[...document.querySelectorAll('[role=dialog] button')].filter(b => b.textContent.includes('作蓝本')); if (btns.length) btns[0].click(); }")
    pg.wait_for_timeout(800)
    variant_tag = pg.evaluate("() => { const t=[...document.querySelectorAll('main *')].filter(e => e.textContent.includes('蓝本:') && e.textContent.length < 40); return t.length ? t[0].textContent.length : 0 }")
    print("4. 设置蓝本后标签长度:", variant_tag)
    pg.screenshot(path="docs/ui-review/27-variant-main.png")

    # ── 内联面板 ──
    pg.goto(BASE + "/#/chat", wait_until="networkidle")
    pg.wait_for_timeout(2000)
    pg.click("button:has-text('新建对话')")
    pg.wait_for_timeout(800)
    pg.fill("textarea", "请打开出题工作台")
    pg.click("button:has-text('发送')")
    for _ in range(60):
        pg.wait_for_timeout(2000)
        if not pg.evaluate("() => !!document.querySelector('main textarea')?.disabled"):
            break
    pg.wait_for_timeout(1200)
    panel_btn = pg.evaluate("() => { const p=document.querySelector('[data-panel]'); return p ? [...p.querySelectorAll('button')].some(b => b.textContent.includes('选蓝本')) : false }")
    print("5. 内联面板「选蓝本」按钮:", panel_btn)
    pg.screenshot(path="docs/ui-review/28-variant-inline.png")

    non502 = [e for e in errs if "502" not in e]
    print("console(非502):", non502[:3])
    b.close()

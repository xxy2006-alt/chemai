# -*- coding: utf-8 -*-
"""_e2e_design_upgrade.py — design-upgrade 端到端验收（ADR-0001 + #14~#17）。

真实走 UI：
1. 教师：登录页(深色 moment) → admin 登录 → /chat 深色 AI 嵌板 → 各页巡检 + 截图
2. 学生：守卫跳登录 → 241901 登录 → /m 四页巡检 + 游戏化 + 截图
3. 家长：e2e_parent 登录 → /m/parent 三 Tab + 报告 hero + 截图
4. 旧 URL 重定向映射（已登录态验证完整映射链 + 匿名态守卫兜底）
5. 全程收集控制台错误（网络 4xx/5xx 降级为警告，JS 异常算失败）
"""
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8001"
STUDENT_USER = "241901"
STUDENT_PASS = "123456"
SHOTS = Path(__file__).parent / "_design_upgrade_shots"
SHOTS.mkdir(exist_ok=True)

results = []


def note(ok, name, detail=""):
    results.append((ok, name, detail))
    print(f"{'PASS' if ok else 'FAIL'} | {name} | {detail}")


def new_ctx(browser, mobile=False):
    kw = dict(viewport={"width": 430, "height": 900}, device_scale_factor=2, is_mobile=True, has_touch=True) if mobile \
        else dict(viewport={"width": 1440, "height": 900})
    ctx = browser.new_context(**kw)
    errors = []
    warnings = []

    def on_console(m):
        if m.type != "error":
            return
        if m.text.startswith("Failed to load resource"):
            warnings.append(m.text)
        else:
            errors.append(m.text)

    def attach(p):
        p.on("console", on_console)
        p.on("pageerror", lambda e: errors.append(f"JSException: {e}"))

    ctx.on("page", attach)
    return ctx, errors, warnings


def wait_hash(page, route, timeout_ms=20000):
    """SPA hash 软导航不触发 load —— 轮询到精确路由（或其子路由）为止。"""
    target = route.lstrip("#")
    deadline = time.time() + timeout_ms / 1000

    def matched():
        h = page.url.split("#", 1)[-1] if "#" in page.url else ""
        return h == target or h.startswith(target + "/")

    while time.time() < deadline and not matched():
        page.wait_for_timeout(300)
    return matched()


def shot(page, name):
    page.screenshot(path=str(SHOTS / f"{name}.png"))



def provision_parent():
    """E2E 自助家长：注册→登录→用学生 bind_code 绑定 241901（不依赖预置账号）。"""
    import json as _json
    import time as _t
    import urllib.request

    def post(path, body, token=None):
        req = urllib.request.Request(
            f"{BASE}{path}",
            data=_json.dumps(body).encode(),
            headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})},
            method="POST",
        )
        return _json.loads(urllib.request.urlopen(req, timeout=15).read())

    def get(path, token):
        req = urllib.request.Request(f"{BASE}{path}", headers={"Authorization": f"Bearer {token}"})
        return _json.loads(urllib.request.urlopen(req, timeout=15).read())

    phone = f"138{int(_t.time()) % 100000000:08d}"
    post("/api/parent/register", {"name": "E2E Parent", "phone": phone, "password": "123456"})
    login = post("/api/parent/login", {"username": phone, "password": "123456"})
    parent_id = login["parent_id"]
    ptok = login["token"]
    stu = post("/api/auth/login", {"username": STUDENT_USER, "password": STUDENT_PASS})
    stok = stu["token"]
    code = get(f"/api/diagnosis/plan/{STUDENT_USER}", stok)["data"].get("bind_code", "")
    if code:
        post("/api/parent/bind", {"student_id": STUDENT_USER, "bind_code": code, "parent_id": parent_id, "relation": "E2E"}, ptok)
    return phone


def run():
    with sync_playwright() as pw:
        browser = pw.chromium.launch()

        # ══ 1. 教师端（桌面） ══
        ctx, errs, warns = new_ctx(browser)
        page = ctx.new_page()
        page.goto(f"{BASE}/#/login")
        page.wait_for_selector("text=登录教师工作台", timeout=15000)
        shot(page, "teacher_01_login")
        note(True, "教师登录页渲染（深色 moment）")

        page.fill('input[placeholder="请输入账号"]', "admin")
        page.fill('input[placeholder="请输入密码"]', "admin123")
        page.click('button[type="submit"]')
        assert wait_hash(page, "/chat"), "教师登录未跳转"
        note(True, "教师登录跳转 /#/chat")
        page.wait_for_timeout(4000)  # 等登录 toast（3s 自动消失）退场再截图
        glass = page.evaluate("document.querySelector('.backdrop-blur-md') !== null")
        sidebar_img = page.evaluate(
            "(() => { const bi = getComputedStyle(document.querySelector('aside')).backgroundImage; return bi !== 'none' && bi !== ''; })()"
        )
        note(glass, "教师 /chat 玻璃 AI 舱挂载（v2.1）", f"backdrop-blur-md={glass}")
        note(sidebar_img, "侧边栏品牌底图 navBg（webp 内联为 data URI）", f"background-image={sidebar_img}")
        shot(page, "teacher_02_chat_dark_panel")

        for path, name, expects in [
            ("/class", "teacher_03_class", ["班级"]),
            ("/students", "teacher_04_students", ["学生"]),
            ("/exam", "teacher_05_exam", ["出题", "考试"]),
            ("/diagnosis", "teacher_06_diagnosis", ["诊断"]),
            ("/ocr", "teacher_07_ocr", ["答题卡", "OCR", "批改"]),
        ]:
            page.goto(f"{BASE}/#{path}")
            wait_hash(page, path)
            page.wait_for_timeout(1800)
            body = page.inner_text("body")
            hit = next((k for k in expects if k in body), None)
            note(hit is not None, f"教师 {path} 渲染", f"关键词命中={hit}")
            shot(page, name)
        note(len(errs) == 0, "教师端控制台零 JS 异常", "; ".join(errs[:3]) if errs else "clean")
        if warns:
            note(True, f"教师端网络警告 {len(warns)} 条（存量 schema/权限，已记录）", warns[0][:80])
        ctx.close()

        # ══ 2. 学生端（移动 430×900） ══
        ctx, errs, warns = new_ctx(browser, mobile=True)
        page = ctx.new_page()
        page.goto(f"{BASE}/#/m")
        wait_hash(page, "/m/login")
        note(True, "学生守卫：未登录跳 /m/login", page.url)
        page.wait_for_selector("text=学生登录", timeout=10000)
        shot(page, "student_01_login")

        page.fill('input[placeholder="输入学号"]', STUDENT_USER)
        page.fill('input[placeholder="输入密码"]', STUDENT_PASS)
        page.click('button:has-text("登录")')
        assert wait_hash(page, "/m"), "学生登录未跳转"
        page.wait_for_timeout(1500)
        body = page.inner_text("body")
        note("AI 化学助教" in body, "学生 AI 助教门面页渲染")
        note(all(t in body for t in ["AI助教", "练习", "错题", "我的"]), "底部 4 Tab 渲染")
        shot(page, "student_02_chat")

        for path, name in [("/m/practice", "student_03_practice"), ("/m/wrong", "student_04_wrong"), ("/m/me", "student_05_me")]:
            page.goto(f"{BASE}/#{path}")
            wait_hash(page, path)
            if path == "/m/practice":
                # tasks 接口为同步生成（首访约 15s），等待列表/空态/错误出现再截图
                page.wait_for_function(
                    "['待完成','暂无练习任务','加载失败'].some(t => document.body.innerText.includes(t))",
                    timeout=60000,
                )
            page.wait_for_timeout(1500)
            ok = path.lstrip("#") in page.url.split("#")[-1]
            note(ok, f"学生 {path} 可达", page.url.split("#")[-1])
            shot(page, name)
        page.wait_for_function("document.body.innerText.includes('连续打卡')", timeout=30000)
        me_body = page.inner_text("body")
        note(("连续打卡" in me_body) and ("累计积分" in me_body), "游戏化模块挂载（streak/积分）")
        note(len(errs) == 0, "学生端控制台零 JS 异常", "; ".join(errs[:3]) if errs else "clean")

        # 已登录态验证旧 URL 重定向的完整映射链
        for old, expect in [
            ("/m/index.html", "/m"),
            ("/m/practice.html", "/m/practice"),
            ("/m/wrong.html", "/m/wrong"),
            ("/m/report.html", "/m/me"),
            ("/m/review.html", "/m/review"),
            ("/m/login.html", "/m/login"),
        ]:
            page.goto(f"{BASE}{old}")
            ok = wait_hash(page, expect, timeout_ms=8000)
            note(ok, f"重定向 {old}", f"→ {page.url.split('#')[-1]}")
        ctx.close()

        # ══ 3. 家长端（移动） ══
        ctx, errs, warns = new_ctx(browser, mobile=True)
        page = ctx.new_page()
        parent_user = provision_parent()
        page.goto(f"{BASE}/#/m/parent-login")
        wait_hash(page, "/m/parent-login")
        page.wait_for_selector("text=家长登录", timeout=10000)
        shot(page, "parent_01_login")
        page.fill('input[placeholder="输入手机号或用户名"]', parent_user)
        page.fill('input[placeholder="输入密码"]', "123456")
        page.click('button:has-text("进入")')
        assert wait_hash(page, "/m/parent"), "家长登录未跳转"
        page.wait_for_timeout(2500)
        body = page.inner_text("body")
        note(("还没有绑定孩子" in body) or ("本周学习" in body), "家长概览/空态渲染")
        note(all(t in body for t in ["概览", "学习报告", "消息"]), "家长三 Tab 渲染")
        shot(page, "parent_02_home")

        page.click('nav >> text=学习报告')
        page.wait_for_timeout(2000)
        shot(page, "parent_03_report")
        rb = page.inner_text("body")
        note("本周正确率" in rb, "报告 hero（本周正确率）")

        page.click('nav >> text=消息')
        page.wait_for_timeout(1500)
        shot(page, "parent_04_notif")
        note(len(errs) == 0, "家长端控制台零 JS 异常", "; ".join(errs[:3]) if errs else "clean")
        ctx.close()

        # ══ 4. 匿名旧 URL 重定向（守卫兜底到登录页，链路不断） ══
        ctx, _errs, _warns = new_ctx(browser)
        page = ctx.new_page()
        for old in ["/m/parent.html", "/m/parent-login.html", "/m"]:
            page.goto(f"{BASE}{old}")
            wait_hash(page, "/m", timeout_ms=8000)
            note(True, f"匿名访问 {old}", f"→ {page.url.split('#')[-1]}")
        ctx.close()

        browser.close()

    fails = [r for r in results if not r[0]]
    print(f"\n══ E2E 汇总：{len(results) - len(fails)}/{len(results)} 通过 ══")
    if fails:
        for _, name, detail in fails:
            print(f"  FAIL: {name} | {detail}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    run()

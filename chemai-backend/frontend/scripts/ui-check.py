# ui-check.py — 新教师端 DOM 级验证（控制台错误 / 关键元素 / 布局）
# 用法: python scripts/ui-check.py <url>
import sys
from playwright.sync_api import sync_playwright

url = sys.argv[1]
errors = []

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.add_init_script("localStorage.setItem('token','review-token')")
    page.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url, wait_until="networkidle")
    page.wait_for_timeout(800)

    print(f"URL: {url}")
    print(f"title: {page.title()}")

    # 关键元素检查
    checks = []
    for sel, name in [
        ("aside", "侧边栏"),
        ("nav button", "导航项"),
        ("input[type=password]", "密码输入框"),
        ("textarea", "聊天输入框"),
        ("#root > *", "应用根节点"),
    ]:
        n = page.locator(sel).count()
        checks.append(f"  {name}: {n} 个")
    print("元素检查:")
    print("\n".join(checks))

    # 布局尺寸
    dims = page.evaluate("""() => {
      const aside = document.querySelector('aside');
      const main = document.querySelector('main');
      return { asideW: aside ? aside.offsetWidth : 0, mainW: main ? main.offsetWidth : 0 };
    }""")
    print(f"布局: {dims}")

    # 文本快照
    text = page.evaluate("() => document.body.innerText.slice(0, 300).replace(/\\n+/g, ' | ')")
    print(f"文本: {text}")

    print(f"控制台错误/警告: {len(errors)}")
    for e in errors[:8]:
        print(f"  - {e[:200]}")
    browser.close()

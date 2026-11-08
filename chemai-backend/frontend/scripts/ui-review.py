# ui-review.py — 新教师端 UI 截图（Phase 1 评审用）
# 用法: python scripts/ui-review.py <url> <out.png> [width] [height]
import sys, os
from playwright.sync_api import sync_playwright

url = sys.argv[1]
out = sys.argv[2]
width = int(sys.argv[3]) if len(sys.argv) > 3 else 1440
height = int(sys.argv[4]) if len(sys.argv) > 4 else 900

os.makedirs(os.path.dirname(out), exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": width, "height": height})
    page.add_init_script("localStorage.setItem('token','review-token')")
    page.goto(url, wait_until="networkidle")
    page.wait_for_timeout(600)
    page.screenshot(path=out)
    browser.close()
print("saved:", out)

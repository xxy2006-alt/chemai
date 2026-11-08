# ui-final-types.py — 综合验证：题型 chips（主工作台+内联面板）/新建/打印/多选生成
import requests, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8001"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto(BASE + "/#/login", wait_until="networkidle")
    pg.fill("input[placeholder='请输入账号']", "hai")
    pg.fill("input[type=password]", "hai123456")
    pg.click("button[type=submit]")
    pg.wait_for_timeout(2500)
    pg.goto(BASE + "/#/exam", wait_until="networkidle")
    pg.wait_for_timeout(7000)

    r = pg.evaluate(
        """() => {
          const btns = [...document.querySelectorAll('main button')].map(b => b.textContent.trim());
          const chips = btns.filter(t => ['单选','多选','填空','计算','实验','推断'].some(k => t.includes(k) && t.length < 8));
          return {
            chips,
            hasNewFolder: btns.some(t => t.includes('新建题库')),
            hasPrint: btns.some(t => t.includes('打印预览')),
            hasVariant: btns.some(t => t.includes('选真题作蓝本')),
          };
        }"""
    )
    print("1. 主工作台:", r)

# 内联面板（通过组件测试已有断言；此处 API 验证多选生成）
s = requests.Session()
login = s.post(BASE + "/api/auth/login", json={"username": "hai", "password": "hai123456"}).json()
h = {"Authorization": "Bearer " + login["token"]}
r = s.post(BASE + "/api/question/generate",
          json={"knowledge_points": ["氧化还原反应"], "difficulty": "medium", "quantity": 1,
                "question_types": ["multiple_choice"]}, headers=h, timeout=120)
qs = r.json().get("questions", [])
print("2. 多选生成:", r.status_code, "| questions:", len(qs))
if qs:
    q = qs[0]
    print("   content:", q.get("content", "")[:60], "| options:", len(q.get("options", [])), "| answer:", q.get("answer"))

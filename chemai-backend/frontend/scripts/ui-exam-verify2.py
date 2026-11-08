# ui-exam-verify2.py — 题型区/新建题库/多选生成/打印预览验证
import requests
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
    pg.wait_for_timeout(3500)

    dump = pg.evaluate(
        """() => {
          const card = [...document.querySelectorAll('main .border')].find(el => el.textContent.includes('题型与数量'));
          if (!card) return { noSection: true };
          const chips = [...card.querySelectorAll('button')].filter(b => /单选|多选|填空|计算|实验|推断/.test(b.textContent)).map(b => b.textContent.trim().slice(0, 8));
          const hasNewFolder = [...document.querySelectorAll('main button')].some(b => b.textContent.includes('新建题库'));
          const hasPrint = [...document.querySelectorAll('main button')].some(b => b.textContent.includes('打印预览'));
          return { chips, hasNewFolder, hasPrint };
        }"""
    )
    print("1. 题型区:", dump)

# 多选生成 API 验证
s = requests.Session()
login = s.post(BASE + "/api/auth/login", json={"username": "hai", "password": "hai123456"}).json()
h = {"Authorization": "Bearer " + login["token"]}
r = s.post(BASE + "/api/question/generate",
          json={"knowledge_points": ["氧化还原反应"], "difficulty": "medium", "quantity": 1,
                "question_types": ["multiple_choice"]}, headers=h, timeout=120)
qs = r.json().get("questions", [])
print("2. 多选生成:", r.status_code, "| questions:", len(qs))
if qs:
    print("   content:", qs[0].get("content", "")[:60], "| options:", len(qs[0].get("options", [])), "| answer:", qs[0].get("answer"))

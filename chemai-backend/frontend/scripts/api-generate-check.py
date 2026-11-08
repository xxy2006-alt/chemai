# api-generate-check.py — 直接调用 /api/question/generate 检查内容反斜杠
import requests, json

BASE = "http://127.0.0.1:8001"
s = requests.Session()
login = s.post(BASE + "/api/auth/login", json={"username": "hai", "password": "hai123456"}).json()
h = {"Authorization": "Bearer " + login["token"], "Content-Type": "application/json"}

body = {
    "knowledge_points": ["化学平衡"],
    "difficulty": "medium",
    "quantity": 1,
    "question_types": ["single_choice"],
}
r = s.post(BASE + "/api/question/generate", json=body, headers=h, timeout=120)
print("status:", r.status_code)
d = r.json()
qs = d.get("questions", [])
print("questions:", len(qs))
for q in qs[:1]:
    c = q.get("content", "")
    print("content repr:", json.dumps(c[:500], ensure_ascii=True))
    print("has \\\\rightleftharpoons:", "\\rightleftharpoons" in c)
    print("has CR:", "\r" in c)
    print("has raw backslash:", "\\" in c)

# content-dump4.py — 转储该题 content 剩余部分（1600-2873）
import requests, json

BASE = "http://127.0.0.1:8001"
s = requests.Session()
login = s.post(BASE + "/api/auth/login", json={"username": "hai", "password": "hai123456"}).json()
h = {"Authorization": "Bearer " + login["token"]}

r = s.get(BASE + "/api/exam-bank/historical", params={"region": "全国卷2020", "year": "2020", "page_size": 200}, headers=h)
for q in r.json().get("data", {}).get("questions", []):
    if "铑" in q.get("content", "") and "解答" in q.get("content", ""):
        c = q["content"]
        print(json.dumps(c[1500:2873], ensure_ascii=True))
        break

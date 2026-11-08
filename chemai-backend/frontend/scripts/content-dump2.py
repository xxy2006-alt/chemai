# content-dump2.py — 转储 nat_2020_t4 的 analysis 原始内容
import requests, json

BASE = "http://127.0.0.1:8001"
s = requests.Session()
login = s.post(BASE + "/api/auth/login", json={"username": "hai", "password": "hai123456"}).json()
h = {"Authorization": "Bearer " + login["token"]}

r = s.get(BASE + "/api/exam-bank/historical", params={"region": "全国卷2020", "year": "2020", "page_size": 200}, headers=h)
for q in r.json().get("data", {}).get("questions", []):
    if "铑" in q.get("content", ""):
        print("== content keys:", list(q.keys()))
        for k in ["analysis", "answer", "solution", "explanation", "audit"]:
            if q.get(k):
                print(f"== {k} RAW:", json.dumps(str(q[k])[:900], ensure_ascii=True))
        break

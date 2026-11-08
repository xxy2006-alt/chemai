# content-dump3.py — 全卷找「解答」+「铑」的题目并转储 content 原文
import requests, json, re

BASE = "http://127.0.0.1:8001"
s = requests.Session()
login = s.post(BASE + "/api/auth/login", json={"username": "hai", "password": "hai123456"}).json()
h = {"Authorization": "Bearer " + login["token"]}

for region in ["全国卷2020", "全国卷2021", "全国卷2022", "全国卷2023", "全国卷2024"]:
    r = s.get(BASE + "/api/exam-bank/historical", params={"region": region, "year": region[-4:], "page_size": 200}, headers=h)
    if r.status_code != 200:
        continue
    for q in r.json().get("data", {}).get("questions", []):
        c = q.get("content", "")
        if "铑" in c and "解答" in c:
            print("FOUND:", region, q.get("question_id"), "| len:", len(c))
            print(json.dumps(c[:1600], ensure_ascii=True))
            raise SystemExit
print("未找到同时含 铑+解答 的题")

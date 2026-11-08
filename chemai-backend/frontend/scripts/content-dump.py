# content-dump.py — 找出含「铑的配合物离子」的题目，转储原始 content
import requests, json, re

BASE = "http://127.0.0.1:8001"
s = requests.Session()
login = s.post(BASE + "/api/auth/login", json={"username": "hai", "password": "hai123456"}).json()
h = {"Authorization": "Bearer " + login["token"]}

# 全卷扫描：2020-2024 全国卷
for year in ["2020", "2021", "2022", "2023", "2024"]:
    r = s.get(BASE + "/api/exam-bank/historical", params={"region": "全国卷" + year, "year": year, "page_size": 200}, headers=h)
    if r.status_code != 200:
        continue
    for q in r.json().get("data", {}).get("questions", []):
        if "铑" in q.get("content", ""):
            print("FOUND in", year, "qid:", q.get("question_id") or q.get("exam_id"))
            c = q["content"]
            # 打印内容的前 400 字符，带转义显示
            print("RAW:", json.dumps(c[:400], ensure_ascii=True))
            print("---")
            break

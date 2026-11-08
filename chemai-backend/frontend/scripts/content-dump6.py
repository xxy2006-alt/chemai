# content-dump6.py — 找「分子式」题 + 「m a t h r m」逐字符版
import requests, json, re

BASE = "http://127.0.0.1:8001"
s = requests.Session()
login = s.post(BASE + "/api/auth/login", json={"username": "hai", "password": "hai123456"}).json()
h = {"Authorization": "Bearer " + login["token"]}

papers = s.get(BASE + "/api/exam-bank/papers", headers=h).json()
for g in papers.get("data", {}).get("groups", []):
    region = g.get("region")
    for y in g.get("years", []):
        year = y.get("year")
        for pp in y.get("papers", []):
            r = s.get(BASE + "/api/exam-bank/historical",
                      params={"region": pp.get("source_key", f"{region}{year}"), "year": year, "page_size": 300}, headers=h)
            if r.status_code != 200:
                continue
            for q in r.json().get("data", {}).get("questions", []):
                c = q.get("content", "") or ""
                if "分子式" in c and "四个氧原子" in c:
                    print("== 分子式题:", region, year, q.get("question_id"))
                    print(json.dumps(c[:1400], ensure_ascii=True))
                    raise SystemExit
print("未找到分子式题")

# content-dump5.py — 转储「气体（杂质）」表格题完整 content
import requests, json

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
                if "酸性高锰酸钾" in c or "气体（杂质）" in c:
                    print("FOUND:", region, year, q.get("question_id"), "len:", len(c))
                    print(json.dumps(c, ensure_ascii=True))
                    raise SystemExit
print("未找到")

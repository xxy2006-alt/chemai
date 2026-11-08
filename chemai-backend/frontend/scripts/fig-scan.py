# fig-scan.py — 扫描 2020 全国卷全部图片 URL，找出 404 的
import urllib.request
import json, re, urllib.parse, requests

BASE = "http://127.0.0.1:8001"

s = requests.Session()
login = s.post(BASE + "/api/auth/login", json={"username": "hai", "password": "hai123456"}).json()
h = {"Authorization": "Bearer " + login["token"]}

r = s.get(BASE + "/api/exam-bank/historical", params={"region": "全国卷2020", "year": "2020", "page_size": 200}, headers=h)
qs = r.json()["data"]["questions"]
urls = []
for q in qs:
    for m in re.finditer(r"\]\(([^)]+\.(?:jpg|png|jpeg|gif))\)", q.get("content", "")):
        urls.append(m.group(1))

bad = []
for u in urls:
    full = BASE + u
    resp = s.get(full, timeout=5)
    if resp.status_code != 200:
        bad.append((u, resp.status_code))
print("total:", len(urls), "| bad:", len(bad))
for u, code in bad[:12]:
    print("BAD", code, u)

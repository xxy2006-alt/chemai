# fig-pageimage.py — 检查 page_image 缩略图字段
import requests, json

BASE = "http://127.0.0.1:8001"
s = requests.Session()
login = s.post(BASE + "/api/auth/login", json={"username": "hai", "password": "hai123456"}).json()
h = {"Authorization": "Bearer " + login["token"]}

r = s.get(BASE + "/api/exam-bank/historical", params={"region": "全国卷2020", "year": "2020", "page_size": 200}, headers=h)
qs = r.json()["data"]["questions"]
withimg = [q for q in qs if q.get("page_image")]
print("questions:", len(qs), "| with page_image:", len(withimg))
for q in withimg[:15]:
    print("  page_image=", q.get("page_image"), "| region=", repr(q.get("region")), "| year=", repr(q.get("year")), "| source=", repr(q.get("source")))

# content-t4-seg.py — 转储 t4 ⑥ 方程式段原始字节
import requests, json

BASE = "http://127.0.0.1:8001"
s = requests.Session()
login = s.post(BASE + "/api/auth/login", json={"username": "hai", "password": "hai123456"}).json()
h = {"Authorization": "Bearer " + login["token"]}
r = s.get(BASE + "/api/exam-bank/historical", params={"region": "全国卷2020", "year": "2020", "page_size": 200}, headers=h)
for q in r.json()["data"]["questions"]:
    if q.get("question_id") == "nat_2020_t4":
        c = q["content"]
        i = c.find("textcircled")
        while i >= 0:
            print("== 段:", json.dumps(c[max(0, i-60):i+160], ensure_ascii=True))
            i = c.find("textcircled", i + 1)
        # sub 标签上下文
        j = c.find("<sub>")
        print("== sub 段:", json.dumps(c[max(0, j-60):j+60], ensure_ascii=True))
        break

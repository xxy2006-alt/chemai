# content-t4-check.py — t4 数据检查：sub标签/双反斜杠/图片重复
import requests, json, re

BASE = "http://127.0.0.1:8001"
s = requests.Session()
login = s.post(BASE + "/api/auth/login", json={"username": "hai", "password": "hai123456"}).json()
h = {"Authorization": "Bearer " + login["token"]}
r = s.get(BASE + "/api/exam-bank/historical", params={"region": "全国卷2020", "year": "2020", "page_size": 200}, headers=h)
for q in r.json()["data"]["questions"]:
    if q.get("question_id") == "nat_2020_t4":
        c = q["content"]
        print("len:", len(c))
        print("sub 标签:", len(re.findall(r"<sub>", c)), "| sup 标签:", len(re.findall(r"<sup>", c)))
        print("双反斜杠 \\\\:", c.count("\\\\"))
        print("图片 URL:", len(re.findall(r"!\[\]\(([^)]+)\)", c)))
        for m in re.finditer(r"!\[\]\(([^)]+)\)", c):
            print("   img:", m.group(1).split("/")[-1])
        print("page_image:", q.get("page_image"))
        # 找 \\ = \\ 上下文
        i = c.find("\\\\")
        while i >= 0 and i < len(c):
            print("   \\\\ 上下文:", json.dumps(c[max(0,i-25):i+30], ensure_ascii=True))
            i = c.find("\\\\", i + 1)
            if i > 4000: break
        break

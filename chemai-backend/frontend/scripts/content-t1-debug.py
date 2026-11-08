# content-t1-debug.py — 对比 nat_2020_t1：磁盘 JSON vs API 返回
import json, os, requests, re

BASE = "http://127.0.0.1:8001"

# 1. 磁盘源文件
disk_path = r"D:\化学\chemai-backend\data\exam_questions\01_全国卷\2020\2020年全国卷高考化学.json"
with open(disk_path, encoding="utf-8") as f:
    disk = json.load(f)

def find_q(obj, qid):
    if isinstance(obj, dict):
        if obj.get("question_id") == qid or obj.get("id") == qid:
            return obj
        for v in obj.values():
            r = find_q(v, qid)
            if r: return r
    elif isinstance(obj, list):
        for v in obj:
            r = find_q(v, qid)
            if r: return r
    return None

dq = find_q(disk, "nat_2020_t1")
print("磁盘找到:", bool(dq))
if dq:
    c = dq.get("content", "")
    print("== 磁盘 content 长度:", len(c))
    # 关键检查
    print("磁盘含 'C H' 空格模式:", bool(re.search(r"C H", c)))
    print("磁盘含 ZWSP:", "\u200b" in c)
    # 找"乙醚"附近 300 字符
    i = c.find("乙醚")
    print("== 磁盘乙醚段:", json.dumps(c[max(0,i-50):i+400], ensure_ascii=True))

# 2. API 返回
s = requests.Session()
login = s.post(BASE + "/api/auth/login", json={"username": "hai", "password": "hai123456"}).json()
h = {"Authorization": "Bearer " + login["token"]}
r = s.get(BASE + "/api/exam-bank/historical", params={"region": "全国卷2020", "year": "2020", "page_size": 200}, headers=h)
for q in r.json()["data"]["questions"]:
    if q.get("question_id") == "nat_2020_t1":
        ac = q["content"]
        print("== API content 长度:", len(ac))
        print("API 含 'C H' 空格模式:", bool(re.search(r"C H", ac)))
        print("API 含 ZWSP:", "\u200b" in ac)
        i = ac.find("乙醚")
        print("== API 乙醚段:", json.dumps(ac[max(0,i-50):i+400], ensure_ascii=True))
        break

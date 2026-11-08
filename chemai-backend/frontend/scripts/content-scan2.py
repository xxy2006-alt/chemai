# content-scan2.py — 全题库扫描重复/垃圾模式
import requests, json, re

BASE = "http://127.0.0.1:8001"
s = requests.Session()
login = s.post(BASE + "/api/auth/login", json={"username": "hai", "password": "hai123456"}).json()
h = {"Authorization": "Bearer " + login["token"]}

# 枚举全部地区
papers = s.get(BASE + "/api/exam-bank/papers", headers=h).json()
groups = papers.get("data", {}).get("groups", [])
print("regions:", len(groups))

all_q = []
for g in groups:
    region = g.get("region")
    for y in g.get("years", []):
        year = y.get("year")
        for pp in y.get("papers", []):
            r = s.get(BASE + "/api/exam-bank/historical",
                      params={"region": pp.get("source_key", f"{region}{year}"), "year": year, "page_size": 300}, headers=h)
            if r.status_code == 200:
                for q in r.json().get("data", {}).get("questions", []):
                    q["_region"] = region
                    q["_year"] = year
                    all_q.append(q)

print("total questions:", len(all_q))

patterns = {
    "逐字符空格数字(如 1 4 ×)": re.compile(r"\d \d"),
    "mathrm裸文本": re.compile(r"mathrm"),
    "裸LaTeX(\\bf|\\Gamma|{\\bf)": re.compile(r"\\bf|\\Gamma"),
    "ZWSP": re.compile(r"\u200b"),
    "重复公式(紧凑+空格双版本)": re.compile(r"(\d ?\d ?[×x]\s?\d ?\d ?[+\-]\s?\d ?\d ?[+\-]\s?\d ?\d ?\s?=\s?\d ?\d)\s*\(?"),
    "分子式双版本": re.compile(r"C ?1 ?4 ?H ?1 ?4 ?O ?4"),
}
counts = {k: 0 for k in patterns}
samples = {k: [] for k in patterns}

for q in all_q:
    c = q.get("content", "") or ""
    for name, pat in patterns.items():
        ms = pat.findall(c)
        if ms:
            counts[name] += len(ms)
            if len(samples[name]) < 2:
                i = c.find(ms[0]) if isinstance(ms[0], str) else c.find(str(ms[0]))
                samples[name].append(c[max(0, i-80):i+120])

print(json.dumps(counts, ensure_ascii=True, indent=1))
for name in patterns:
    if samples[name]:
        print(f"== {name} 样例 ==")
        for smp in samples[name][:1]:
            print(json.dumps(smp, ensure_ascii=True))

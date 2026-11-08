# content-scan.py — 扫描题库全部题目内容的垃圾 LaTeX 模式
import requests, json, re, glob, os

BASE = "http://127.0.0.1:8001"
s = requests.Session()
login = s.post(BASE + "/api/auth/login", json={"username": "hai", "password": "hai123456"}).json()
h = {"Authorization": "Bearer " + login["token"]}

patterns = {
    "mathrm带空格": re.compile(r"\\mathrm\s*\{\s*[^{}]*\s[^{}]*\}"),
    "mathbf带空格": re.compile(r"\\mathbf\s*\{\s*[^{}]*\s[^{}]*\}"),
    "Omega": re.compile(r"\\Omega"),
    "sup垃圾": re.compile(r"<sup>[^<]*</sup>"),
    "textcircled": re.compile(r"\\textcircled"),
    "下划线垃圾": re.compile(r"\$_\s*\\"),
    "带空格子脚本": re.compile(r"_\s*\{\s*\d"),
    "等号花括号": re.compile(r"\{\s*=\s*\}"),
    "波浪号": re.compile(r"~"),
    "ZWSP": re.compile(r"\u200b"),
    "全角空格公式": re.compile(r"[\u3000]"),
}

counts = {k: 0 for k in patterns}
total_q = 0
samples = {k: [] for k in patterns}

for region in ["全国卷2020", "全国卷2021", "全国卷2022", "全国卷2023", "全国卷2024"]:
    r = s.get(BASE + "/api/exam-bank/historical", params={"region": region, "year": region[-4:], "page_size": 300}, headers=h)
    if r.status_code != 200:
        continue
    for q in r.json().get("data", {}).get("questions", []):
        total_q += 1
        c = q.get("content", "") or ""
        for name, pat in patterns.items():
            ms = pat.findall(c)
            if ms:
                counts[name] += len(ms)
                if len(samples[name]) < 2:
                    samples[name].append(c[max(0, c.find(ms[0]) - 60):c.find(ms[0]) + 60])

print("total questions:", total_q)
for name in patterns:
    print(f"{name}: {counts[name]}")
print("\n== 样例 ==")
for name in patterns:
    for smp in samples[name][:1]:
        print(f"[{name}] ...{json.dumps(smp, ensure_ascii=True)}...")

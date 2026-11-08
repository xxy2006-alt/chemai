# content-disk.py — 直接读磁盘 JSON 源文件，对比 API 返回
import json, glob, os

base = r"D:\化学\chemai-backend\data\exam_questions\01_全国卷\2020"
for f in glob.glob(os.path.join(base, "*.json")):
    print("FILE:", os.path.basename(f))
    with open(f, encoding="utf-8") as fh:
        data = json.load(fh)
    # 找含铑的题
    def walk(o, path=""):
        if isinstance(o, dict):
            c = o.get("content") or o.get("question_content")
            if isinstance(c, str) and "铑" in c:
                return o
            for k, v in o.items():
                r = walk(v, path + "/" + k)
                if r: return r
        elif isinstance(o, list):
            for i, v in enumerate(o):
                r = walk(v, path + f"/{i}")
                if r: return r
        return None
    q = walk(data)
    if q:
        c = q["content"]
        print("== 磁盘 content 前 500:", json.dumps(c[:500], ensure_ascii=True))
        print("== 含解答? ", "解答" in c, "| len:", len(c))
        idx = c.find("【解答】")
        if idx >= 0:
            print("== 解答段(400):", json.dumps(c[idx:idx+400], ensure_ascii=True))
    break

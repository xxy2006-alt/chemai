"""
长沙市某中学（源数据：邵阳市第八中学）数据提取

从桌面数据分析目录提取：
- 9 个班名册（姓名 + 生成学号）
- 两场真实考试锚点（2025-11 期中联考总分；2026-09 高三第一次联考逐题得分）
- 2026-09 联考的逐题统计蓝图（满分/难度率/区分度/选项分布）

输出 _datagen/school.json，供灌数管线消费。
"""
import json
import re
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")

SOURCE_DIR = Path(r"C:\Users\Administrator\Desktop\数据分析\邵阳市第八中学")
OUT = Path(__file__).parent / "school.json"

# 真实联考的选项比例列（试题分析）
OPT_COLS = ["A选项", "B选项", "C选项", "D选项", "其他"]


def pct(v):
    if pd.isna(v):
        return None
    if isinstance(v, str):
        v = v.strip().rstrip("%")
        try:
            return float(v) / 100.0
        except ValueError:
            return None
    return float(v)


def extract_class_roster(cls_dir: Path):
    df = pd.read_excel(cls_dir / "基础数据" / "学生各科成绩明细.xlsx", sheet_name=0)
    names = [n for n in df["姓名"].dropna().tolist() if str(n).strip() not in ("", "姓名")]
    # 首行可能是表头说明（本班），过滤
    names = [str(n).strip() for n in names if re.fullmatch(r"[\u4e00-\u9fa5·]{2,4}", str(n).strip())]
    return names


def extract_history(cls_dir: Path):
    """历次考试对比（化学单科）→ [{date, label, {name: chemistry_score}}]"""
    f = cls_dir / "历次考试对比" / "学生历史考试成绩.xlsx"
    wb = pd.ExcelFile(f)
    out = []
    for sn in wb.sheet_names:
        if sn != "化学":  # 化学单科分，非全科总分
            continue
        df = pd.read_excel(f, sheet_name=sn)
        exam_cols = [c for c in df.columns if c != "学生名称"]
        for col in exam_cols:
            m = re.match(r"(\d{4}-\d{2}-\d{2})\s*(.*)", str(col))
            if not m:
                continue
            date, label = m.group(1), m.group(2).strip()
            scores = {}
            for _, row in df.iterrows():
                name = str(row["学生名称"]).strip()
                if not re.fullmatch(r"[\u4e00-\u9fa5·]{2,4}", name):
                    continue
                v = row[col]
                if pd.notna(v):
                    try:
                        scores[name] = float(v)
                    except (TypeError, ValueError):
                        pass
            out.append({"date": date, "label": label, "scores": scores})
    return out


def extract_chem_detail(cls_dir: Path):
    """2026-09 联考化学逐题得分：{name: {qno: score}} + 总分/客观/主观"""
    f = cls_dir / "基础数据" / "各科试卷题目得分明细.xlsx"
    df = pd.read_excel(f, sheet_name="化学")
    out = {}
    for _, row in df.iterrows():
        name = str(row["姓名"]).strip()
        if not re.fullmatch(r"[\u4e00-\u9fa5·]{2,4}", name):
            continue
        items = {}
        for col in df.columns:
            if col.startswith(("客观题", "主观题")) and not col.endswith("总分"):
                v = row[col]
                if pd.notna(v):
                    try:
                        items[col] = float(v)
                    except (TypeError, ValueError):
                        pass
        out[name] = {
            "total": _f(row.get("总分")),
            "objective_total": _f(row.get("客观题总分")),
            "subjective_total": _f(row.get("主观题总分")),
            "items": items,
        }
    return out


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def extract_blueprint(cls_dir: Path):
    """2026-09 联考试题分析（化学）→ 每题统计蓝图 + 选项分布"""
    f = cls_dir / "试卷分析" / "试题分析.xlsx"
    df = pd.read_excel(f, sheet_name="化学", header=0)
    # 选项比例在第二级表头下：第16~20列 = A/B/C/D/其他
    cols = list(df.columns)
    opt_positions = [c for c in cols if c == "选择题各选项比例" or str(c).startswith("Unnamed")]
    opt_map = dict(zip(opt_positions[:5], ["A", "B", "C", "D", "其他"]))
    df = df.rename(columns=opt_map)

    items = []
    for _, row in df.iterrows():
        qtype = row.get("题型")
        qno = row.get("题号")
        if pd.isna(qtype) or pd.isna(qno):
            continue
        qno_f = float(qno)
        qno_str = str(int(qno_f)) if qno_f == int(qno_f) else str(qno_f).rstrip("0").rstrip(".")
        opt = {k: pct(row.get(k)) for k in ("A", "B", "C", "D", "其他")}
        items.append({
            "qtype": "choice" if str(qtype).strip() == "客观题" else "subjective",
            "no": qno_str,
            "full_score": _f(row.get("满分")),
            "avg": _f(row.get("平均分")),
            "difficulty_ratio": _f(row.get("难度")),   # 得分率 0~1
            "discrimination": _f(row.get("区分度")),
            "full_rate": pct(row.get("满分率")),
            "zero_rate": pct(row.get("零分率")),
            "option_ratio": opt,
        })
    return items


def main():
    classes = {}
    anchors = {}       # exam_key -> {date, label, per_class: {class: {name: total}}}
    detail_2026 = {}   # class -> {name: {items...}}
    blueprint = None

    for cls_dir in sorted(SOURCE_DIR.glob("24*班")):
        cname = cls_dir.name  # 2419班
        names = extract_class_roster(cls_dir)
        classes[cname] = names

        for h in extract_history(cls_dir):
            key = h["date"]
            anchors.setdefault(key, {"date": h["date"], "label": h["label"], "per_class": {}})
            anchors[key]["per_class"][cname] = h["scores"]

        detail_2026[cname] = extract_chem_detail(cls_dir)

        bp = extract_blueprint(cls_dir)
        if blueprint is None:
            blueprint = bp

    # 学号：年级码(24) + 班号(19~27) + 序号(01..)
    roster = {}
    for cname, names in classes.items():
        m = re.fullmatch(r"24(\d{2})班", cname)
        class_no = m.group(1)
        roster[cname] = [
            {"student_no": f"24{class_no}{i + 1:02d}", "name": name}
            for i, name in enumerate(names)
        ]

    data = {
        "school": {"name": "长沙市某中学", "city": "长沙市"},
        "classes": sorted(classes.keys()),
        "roster": roster,
        "anchors": {k: v for k, v in sorted(anchors.items())},
        "detail_2026_09": detail_2026,
        "blueprint_2026_09": blueprint,
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    # 摘要
    total = sum(len(v) for v in roster.values())
    print(f"classes={len(roster)} students={total}")
    for k, a in data["anchors"].items():
        print(f"anchor {k} {a['label']}: {len(a['per_class'])} classes,",
              f"{sum(len(s) for s in a['per_class'].values())} scores")
    sample = detail_2026["2419班"]["危恩泽"]
    print(f"detail sample 2419危恩泽: total={sample['total']} items={len(sample['items'])}")
    print(f"blueprint items={len(blueprint)}")
    full = sum(i["full_score"] or 0 for i in blueprint)
    print(f"blueprint full_score sum={full}")
    for i in blueprint[:3]:
        print(" ", i)


if __name__ == "__main__":
    main()

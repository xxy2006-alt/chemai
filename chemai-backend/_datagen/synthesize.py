# -*- coding: utf-8 -*-
"""
作答合成器

原则：
- 真实锚点优先：2026-09 联考逐题得分原样使用；2025-11 期中用真实总分拟合逐题
- 其余考试：学生能力（由两次真实成绩锚定）× 真实难度率 → 正误；逐题分合成后
  贪婪拟合到目标总分，保证 总分=逐题和 的跨表硬一致
- 选项字母按真实选项分布抽样（联考卷）；答错才落 barrier_type（考察维度）
- 主观题作答文本按得分档位从题库 wrong/partial/zero bank 抽取
"""
import json
import random
from pathlib import Path

from paper_real_202609 import PAPER_REAL_202609
from papers_monthly import MONTHLY_PAPERS

HERE = Path(__file__).parent
SCHOOL = json.loads((HERE / "school.json").read_text(encoding="utf-8"))

# 考试时间线：key=日期, paper=卷面, anchor=真实锚点(逐题/总分), trend=能力插值时间点0~1
EXAMS = [
    {"date": "2025-09-04", "label": "高二上开学摸底考试·化学", "paper": "A", "anchor": None, "t": 0.0},
    {"date": "2025-11-13", "label": "高二上期中联考·化学", "paper": "A", "anchor": "2025-11-13", "t": 0.22},
    {"date": "2026-01-22", "label": "高二上期末考试·化学", "paper": "B", "anchor": None, "t": 0.42},
    {"date": "2026-03-20", "label": "高二下第一次月考·化学", "paper": "A", "anchor": None, "t": 0.58},
    {"date": "2026-04-23", "label": "高二下期中考试·化学", "paper": "B", "anchor": None, "t": 0.72},
    {"date": "2026-06-18", "label": "高二下期末考试·化学", "paper": "B", "anchor": None, "t": 0.88},
    {"date": "2026-09-10", "label": "长沙市2026年9月高三第一次联考·化学", "paper": "REAL", "anchor": "2026-09-10", "t": 1.0},
]

PAPERS = {"REAL": PAPER_REAL_202609, "A": MONTHLY_PAPERS[0], "B": MONTHLY_PAPERS[1]}


def rotated_paper(paper_key: str, exam_index: int) -> dict:
    """无锚点月考的卷面轮换：A/B 卷按场次偏移组成不同卷面（分值骨架一致）"""
    if paper_key not in ("A", "B"):
        return PAPERS[paper_key]
    a, b = MONTHLY_PAPERS[0], MONTHLY_PAPERS[1]
    pool = a["choice"] + b["choice"]
    start = (exam_index * 7) % len(pool)
    choice = [pool[(start + i * 2) % len(pool)] for i in range(14)]
    # 同号题可能同时来自 A/B 卷，按位置重新编号去重
    for i, q in enumerate(choice):
        q = dict(q)
        q["no"] = str(i + 1)
        choice[i] = q
    subjective = [a, b][exam_index % 2]["subjective"]
    return {"choice": choice, "subjective": subjective}


def paper_payload(paper_key: str, paper: dict = None):
    """卷面 → 导入 questions 规格"""
    p = paper or PAPERS[paper_key]
    questions = []
    for q in p["choice"]:
        questions.append({
            "no": f"客观题{q['no']}", "qtype": "single_choice", "full_score": 3,
            "answer": q["answer"], "content": q["content"], "options": q["options"],
            "analysis": q["analysis"], "knowledge_points": q["kp"],
            "probe_dimension": q["probe"], "difficulty": q["difficulty"],
        })
    for s in p["subjective"]:
        questions.append({
            "no": s["no"], "qtype": "fill_blank", "full_score": s["full_score"],
            "answer": s["answer"], "content": s["content"], "options": None,
            "analysis": None, "knowledge_points": s["kp"],
            "probe_dimension": s["probe"], "difficulty": s["difficulty"],
        })
    return questions


def ratio_to_tier(paper_key: str, qno: str):
    """题在卷内的得分率档位（客观题只有对/错）"""
    paper = PAPERS[paper_key]
    for q in paper["choice"]:
        if q["no"] == qno:
            return None
    return None


def choice_correct_letter(paper_key: str, qno: str) -> str:
    paper = PAPERS[paper_key]
    for q in paper["choice"]:
        if q["no"] == qno:
            return q["answer"]
    raise KeyError(qno)


def wrong_letter_for(paper_key: str, qno: str, correct: str, rng) -> str:
    """答错字母：联考卷用真实错误分布；月考卷在其余字母中近似均匀"""
    if paper_key == "REAL":
        bp = next(i for i in SCHOOL["blueprint_2026_09"] if i["no"] == qno)
        opt = bp["option_ratio"]
        wrong = {k: v for k, v in opt.items() if k in ("A", "B", "C", "D") and k != correct}
        # 其他/D 兜底均摊
        total = sum(v or 0 for v in wrong.values())
        if total <= 0:
            letters = [l for l in ("A", "B", "C", "D") if l != correct]
            return rng.choice(letters)
        r = rng.random() * total
        acc = 0.0
        for letter, v in wrong.items():
            acc += v or 0
            if r <= acc:
                return letter
        return list(wrong.keys())[-1]
    letters = [l for l in ("A", "B", "C", "D") if l != correct]
    return rng.choice(letters)


def subjective_text(paper_key: str, sub_no: str, score: float, full: float, rng) -> str:
    """主观题作答文本：按得分档位从内容库抽取"""
    paper = PAPERS[paper_key]
    sub = next(s for s in paper["subjective"] if s["no"] == sub_no)
    ratio = score / full if full else 0
    if ratio >= 0.999:
        return sub["answer"]
    if ratio >= 0.6:
        return rng.choice(sub["partial_bank"])
    if ratio > 0:
        return rng.choice(sub["wrong_bank"] + sub["partial_bank"])
    return rng.choice(sub["zero_bank"])


def student_ability(roster_entry, detail_2026, anchor_2025) -> float:
    """能力值 = 真实化学得分率加权（0~1）"""
    name = roster_entry["name"]
    a26 = detail_2026.get(name, {}).get("total")
    a25 = (anchor_2025 or {}).get(name)
    vals = []
    if a25 is not None:
        vals.append(a25 / 100.0)
    if a26 is not None:
        vals.append(a26 / 100.0)
    if not vals:
        return 0.36  # 真实年级化学均分水平
    return sum(vals) / len(vals)


def fit_items_to_total(specs, target: float, rng, preset_choice_scores=None,
                       preset_choice_flags=None):
    """
    specs: [{"no","qtype","full_score","p_correct"}]
    拟合策略：选择题按概率抽签后不再改动（保住真实感选项分布）；
    总分差距全部由主观题分数以 1 分粒度微调吸收，保证 逐题和==总分。
    返回 {no: score}, {no: is_correct}
    """
    scores, correct_flags = {}, {}
    subjective = []
    for sp in specs:
        if sp["qtype"] == "single_choice" and preset_choice_scores is not None:
            correct_flags[sp["no"]] = preset_choice_flags[sp["no"]]
            scores[sp["no"]] = preset_choice_scores[sp["no"]]
            continue
        hit = rng.random() < sp["p_correct"]
        if sp["qtype"] == "single_choice":
            correct_flags[sp["no"]] = hit
            scores[sp["no"]] = sp["full_score"] if hit else 0.0
        else:
            subjective.append(sp)
            r = rng.random()
            if hit:
                correct_flags[sp["no"]] = True
                scores[sp["no"]] = sp["full_score"] if r < 0.5 else round(sp["full_score"] * rng.uniform(0.6, 0.99))
            else:
                correct_flags[sp["no"]] = False
                scores[sp["no"]] = 0.0 if r < 0.45 else round(sp["full_score"] * rng.uniform(0.05, 0.59))

    # 总分微调：只在各题初始档位内移动（错题保持在及格线下），
    # 保证拟合不改变正误结构 —— 障碍归因的因果性不被洗掉
    bounds = {}
    for s in subjective:
        full = s["full_score"]
        if correct_flags[s["no"]]:
            lo = round(full * 0.6)
            bounds[s["no"]] = (lo, round(full))
        else:
            bounds[s["no"]] = (0, max(0, round(full * 0.59)))

    guard = 0
    while abs(sum(scores.values()) - target) > 0.01 and guard < 400:
        guard += 1
        diff = target - sum(scores.values())
        adjustable = [
            s for s in subjective
            if (scores[s["no"]] < bounds[s["no"]][1] if diff > 0 else scores[s["no"]] > bounds[s["no"]][0])
        ]
        if not adjustable:
            break
        s = rng.choice(adjustable)
        step = 1.0 if diff > 0 else -1.0
        lo, hi = bounds[s["no"]]
        scores[s["no"]] = max(lo, min(hi, scores[s["no"]] + step))

    return scores, correct_flags


def build_exam_payload_for_class(cls_name: str, roster: list, exam: dict, rng,
                                 exam_index: int = 0):
    """为一个班的一场考试构建导入 payload"""
    paper_key = exam["paper"]
    paper = rotated_paper(paper_key, exam_index) if exam["anchor"] is None else None
    specs = paper_payload(paper_key, paper)
    anchor_2025 = SCHOOL["anchors"].get("2025-11-13", {}).get("per_class", {}).get(cls_name, {})
    anchor_2026 = SCHOOL["anchors"].get("2026-09-10", {}).get("per_class", {}).get(cls_name, {})
    detail_2026 = SCHOOL["detail_2026_09"].get(cls_name, {})

    # 班级平均能力（用于个体校准）
    abilities = {r["student_no"]: student_ability(r, detail_2026, anchor_2025) for r in roster}
    mean_ability = sum(abilities.values()) / max(len(abilities), 1)

    # 场次难度抖动：真实月考卷难度不同，班级均分随之波动（锚点考试保持真实值）
    exam_factor = rng.uniform(0.90, 1.10) if exam["anchor"] is None else 1.0

    scores_rows = []
    for r in roster:
        sno, name = r["student_no"], r["name"]
        ability = abilities[sno]

        # 目标总分
        if exam["anchor"] == "2026-09-10":
            real = detail_2026.get(name)
            if real and real.get("total") is not None:
                # 真实逐题原样使用
                item_scores, item_flags = {}, {}
                for spec in specs:
                    qno = spec["no"]
                    key = qno  # 明细列名与卷面规格一致（客观题N / 主观题x.y）
                    raw = real["items"].get(key)
                    if raw is None:
                        raw = 0.0
                    item_scores[qno] = raw
                    item_flags[qno] = spec["full_score"] > 0 and raw >= spec["full_score"] * (
                        1.0 if spec["qtype"] == "single_choice" else 0.6
                    )
                scores_rows.append(_row(sno, item_scores, item_flags, specs, paper_key, rng))
                continue

        if exam["anchor"] == "2025-11-13":
            target = anchor_2025.get(name)
            if target is None:
                # 该班无此锚点（如 2427 班缺 2025-11 数据）→ 按下一锚点回推
                b = anchor_2026.get(name)
                target = (b * 0.88 if b is not None else 52.0) * rng.uniform(0.97, 1.03)
                target = max(5.0, min(99.0, target))
        else:
            a = anchor_2025.get(name)
            b = anchor_2026.get(name)
            if a is not None and b is not None:
                target = a + (b - a) * exam["t"]
            elif b is not None:
                target = b * (0.86 + 0.14 * exam["t"])
            elif a is not None:
                target = a * (1.0 + 0.14 * (1 - exam["t"]))
            else:
                target = 55.0
            # 波动：场次难度 × 个体起伏
            target *= exam_factor * rng.uniform(0.96, 1.04)
            target = max(5.0, min(99.0, target))

        # 个人错因画像：目标错题维度配额（Dirichlet，概念略占优），
        # 生成时自顶向下：先画像、后配额、再在维度内挑最难的题落错
        raw = [rng.random() for _ in range(3)]
        w = {"concept": raw[0] * 1.8, "reading": raw[1] * 1.3, "expression": raw[2] * 1.0}
        wsum = sum(w.values())
        w = {k: v / wsum for k, v in w.items()}

        # 逐题概率 = 难度率 × 能力校准
        calibrated = []
        for spec in specs:
            base = difficulty_ratio_for(paper_key, spec)
            p = base + 2.2 * (ability - mean_ability)
            calibrated.append({**spec, "p_correct": max(0.03, min(0.97, p))})

        # 选择题错题配额：按画像分配到维度，维度内按难度从高到低落错
        choice_specs = [s for s in calibrated if s["qtype"] == "single_choice"]
        p_miss_mean = sum(1 - s["p_correct"] for s in choice_specs) / max(len(choice_specs), 1)
        miss_target = max(1, round(len(choice_specs) * p_miss_mean))
        by_dim = {}
        for s in choice_specs:
            by_dim.setdefault(s.get("probe_dimension"), []).append(s)
        miss_quota = {dim: round(miss_target * w.get(dim, 1/3)) for dim in by_dim}
        # 修正配额总和
        while sum(miss_quota.values()) > miss_target:
            dim = max(miss_quota, key=miss_quota.get)
            miss_quota[dim] -= 1
        while sum(miss_quota.values()) < miss_target and miss_target > 0:
            dim = max(by_dim, key=lambda d: len(by_dim[d]))
            miss_quota[dim] += 1
        choice_miss = set()
        for dim, items in by_dim.items():
            quota = min(miss_quota.get(dim, 0), len(items))
            hardest = sorted(items, key=lambda s: s["p_correct"])[:quota]
            choice_miss.update(s["no"] for s in hardest)
        choice_flags = {s["no"]: s["no"] not in choice_miss for s in choice_specs}
        choice_scores = {s["no"]: (s["full_score"] if choice_flags[s["no"]] else 0.0) for s in choice_specs}

        item_scores, item_flags = fit_items_to_total(calibrated, round(target), rng,
                                                      preset_choice_scores=choice_scores,
                                                      preset_choice_flags=choice_flags)
        scores_rows.append(_row(sno, item_scores, item_flags, calibrated, paper_key, rng))

    return {
        "name": exam["label"],
        "class_name": cls_name,
        "subject": "化学",
        "exam_date": exam["date"],
        "grade_name": "高三",
        "grade_year": 2024,
        "questions": specs,
        "scores": scores_rows,
    }


def difficulty_ratio_for(paper_key: str, spec: dict) -> float:
    """题的基准得分率：联考卷用真实统计；月考卷由难度 1~5 反推"""
    if paper_key == "REAL":
        bp_no = spec["no"].replace("客观题", "").replace("主观题", "")
        bp = next(i for i in SCHOOL["blueprint_2026_09"] if i["no"] == bp_no)
        return bp["difficulty_ratio"] or 0.5
    table = {1: 0.85, 2: 0.75, 3: 0.55, 4: 0.38, 5: 0.22}
    return table.get(spec.get("difficulty"), 0.5)


def _row(sno, item_scores, item_flags, specs, paper_key, rng):
    items, texts = {}, {}
    for spec in specs:
        qno = spec["no"]
        score = item_scores[qno]
        items[qno] = score
        if spec["qtype"] == "single_choice":
            correct = spec["answer"]
            hit = item_flags.get(qno) or score >= spec["full_score"]
            if hit:
                texts[qno] = correct
            else:
                bp_no = qno.replace("客观题", "")
                texts[qno] = wrong_letter_for(paper_key, bp_no, correct, rng)
        else:
            texts[qno] = subjective_text(paper_key, qno, score, spec["full_score"], rng)
    return {"student_no": sno, "items": items, "answer_texts": texts}

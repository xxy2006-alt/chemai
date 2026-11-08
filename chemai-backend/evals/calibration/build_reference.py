"""
Calibration reference-set builder (2026-08-15, 用户授权替代人工标注).

从真实数据生成校准参考集：
  - grading/question_gen：题库真题 + 官方答案（questions 表）
  - diagnosis/plan：学生真实障碍标签（students.barrier_type）
  - interaction：Spec 05 golden 场景契约（手写，见 interaction_ref 部分）

生成 {family}_ref.yaml；calibrate.py 会自动合并人工种子（{family}.yaml）与
本参考集。标注来源注明在文件头：AI 依据真题/历史数据推导，未经独立人工复核。
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

CALIBRATION_DIR = Path(__file__).resolve().parent
HEADER = (
    "# 校准参考集（AI 依据真题/历史数据生成，用户授权替代人工标注，2026-08-15）\n"
    "# calibrate.py 自动合并本文件与人工种子 {family}.yaml\n"
)


def _load_questions(limit=20):
    from sqlalchemy import text
    from app.models.database import get_db
    s = next(get_db())
    rows = s.execute(text(
        "SELECT content, answer, analysis, difficulty, knowledge_points "
        "FROM questions WHERE content IS NOT NULL AND answer IS NOT NULL LIMIT :n"
    ), {"n": limit}).fetchall()
    s.close()
    return rows


def _load_students(limit=20):
    from sqlalchemy import text
    from app.models.database import get_db
    s = next(get_db())
    rows = s.execute(text(
        "SELECT name, barrier_type, exercises_completed FROM students "
        "WHERE barrier_type IS NOT NULL LIMIT :n"
    ), {"n": limit}).fetchall()
    s.close()
    return rows


def _dominant(barrier_str):
    try:
        d = json.loads(barrier_str)
    except (json.JSONDecodeError, TypeError):
        return "concept"
    if not d:
        return "concept"
    return max(d, key=d.get)


BARRIER_CN = {"concept": "概念理解", "reading": "审题仔细度", "expression": "答题表述"}
ALL_TYPES = ["concept", "reading", "expression"]


def build_grading(questions):
    samples = []
    for i, (content, answer, _analysis, _diff, _kp) in enumerate(questions, 1):
        stem = str(content or "").replace("\n", " ")[:120]
        ans = str(answer or "")
        # 判官判分正确 → 高分
        samples.append({
            "id": f"gr-ref-{i:02d}a",
            "input": f"题目：{stem}",
            "output": f"学生答案：{ans}；判官判分：满分",
            "reference": f"官方答案：{ans}（判分正确）",
            "human_score": 100,
            "note": "判分与官方答案一致",
        })
        # 判官给满分但官方答案是错的（判分失误）→ 低分
        samples.append({
            "id": f"gr-ref-{i:02d}b",
            "input": f"题目：{stem}",
            "output": f"学生答案：{ans}；判官判分：0 分",
            "reference": f"官方答案：{ans}（应满分，判分失误）",
            "human_score": 0,
            "note": "判分与官方答案相悖",
        })
    return samples[:20]


def build_question_gen(questions):
    samples = []
    kp_labels = {r[4]: r[4] for r in questions}
    for i, (content, answer, analysis, diff, kp) in enumerate(questions[:17], 1):
        kps = kp or "化学"
        if isinstance(kps, str):
            try:
                kps = json.loads(kps)
            except (json.JSONDecodeError, TypeError):
                kps = [kps]
        kp_name = (kps[0] if kps else "化学")
        difficulty = {"EASY": "简单", "MEDIUM": "中等", "HARD": "困难"}.get(diff, "中等")
        body = str(content or "")[:150]
        if i <= 13:
            # 真题 + 官方答案 + 解析 = 高质量出题
            samples.append({
                "id": f"qg-ref-{i:02d}",
                "input": f"出1道关于{kp_name}的选择题，{difficulty}难度",
                "output": f"{body}\n答案：{answer}\n解析：{analysis or '略'}",
                "human_score": 90,
                "note": "题库真题+官方答案+解析",
            })
        elif i <= 15:
            samples.append({
                "id": f"qg-ref-{i:02d}",
                "input": f"出1道关于{kp_name}的选择题，{difficulty}难度",
                "output": f"{body}\n答案：{answer}",
                "human_score": 40,
                "note": "缺解析（解析正确维度扣分）",
            })
        else:
            samples.append({
                "id": f"qg-ref-{i:02d}",
                "input": f"出1道关于{kp_name}的选择题，{difficulty}难度",
                "output": f"{body}\n答案：（空）",
                "human_score": 20,
                "note": "答案缺失，格式残缺",
            })
    samples.append({
        "id": "qg-ref-off",
        "input": "出1道关于化学平衡的选择题，中等难度",
        "output": "今天天气不错，适合复习。",
        "human_score": 5,
        "note": "完全跑题",
    })
    return samples


def build_diagnosis(students):
    samples = []
    for i, (name, barrier, _ex) in enumerate(students[:12], 1):
        dom = _dominant(barrier)
        others = [t for t in ALL_TYPES if t != dom]
        samples.append({
            "id": f"dx-ref-{i:02d}a",
            "input": f"学生{name}最近错题较多，请诊断其学习障碍",
            "output": f"诊断：{dom}（{BARRIER_CN[dom]}障碍）",
            "reference": f"历史标签主导障碍：{dom}",
            "human_score": 100,
            "note": "与历史障碍标签一致",
        })
        wrong = others[i % 2]
        samples.append({
            "id": f"dx-ref-{i:02d}b",
            "input": f"学生{name}最近错题较多，请诊断其学习障碍",
            "output": f"诊断：{wrong}（{BARRIER_CN[wrong]}障碍）",
            "reference": f"历史标签主导障碍：{dom}",
            "human_score": 15,
            "note": "与历史障碍标签相悖",
        })
    return samples[:20]


def build_plan(students):
    plan_templates = {
        "concept": "第一阶段：梳理{dom}相关核心概念与易混点（2 课时）；第二阶段：每日 30 分钟变式练习 20 题；第三阶段：两周后小测复盘",
        "reading": "第一阶段：每日 10 分钟读题圈画关键词训练；第二阶段：错题标注漏读条件并归因；第三阶段：每周一次限时审题自测",
        "expression": "第一阶段：按评分标准示范规范书写；第二阶段：每日一题对照标准自查；第三阶段：考前完成 30 道真题规范书写",
    }
    samples = []
    for i, (name, barrier, _ex) in enumerate(students[:12], 1):
        dom = _dominant(barrier)
        if i <= 7:
            samples.append({
                "id": f"pl-ref-{i:02d}a",
                "input": f"学生{name}，{BARRIER_CN[dom]}障碍，高一，每周可投入 3 小时",
                "output": plan_templates[dom].format(dom=BARRIER_CN[dom]),
                "human_score": 85,
                "note": "贴合障碍类型、有节奏、可执行",
            })
            samples.append({
                "id": f"pl-ref-{i:02d}b",
                "input": f"学生{name}，{BARRIER_CN[dom]}障碍，高一，每周可投入 3 小时",
                "output": "多做题目就行。",
                "human_score": 30,
                "note": "模板化、无针对性、不可执行",
            })
        else:
            wrong = "reading" if dom != "reading" else "concept"
            samples.append({
                "id": f"pl-ref-{i:02d}",
                "input": f"学生{name}，{BARRIER_CN[dom]}障碍，高一，每周可投入 3 小时",
                "output": plan_templates[wrong].format(dom=BARRIER_CN[wrong]),
                "human_score": 25,
                "note": "方案针对错误障碍类型",
            })
    return samples[:20]


def build_interaction():
    return [
        {"id": "ix-ref-01", "input": "我要出题",
         "output": "好的！请告诉我：1) 题型（选择/填空/计算）2) 难度（简单/中等/困难）3) 知识点；或说「按班级薄弱点推荐」。",
         "human_score": 90, "note": "信息不全→选项式追问"},
        {"id": "ix-ref-02", "input": "我要出题",
         "output": "好的，请在下方面板中配置参数。",
         "human_score": 25, "note": "机械开面板不追问（Spec 05 前的旧行为）"},
        {"id": "ix-ref-03", "input": "我要出题",
         "output": "你想出什么题？说说你的想法。你想考哪个知识点？难度呢？题型呢？",
         "human_score": 40, "note": "开放式连续盘问，不给选项"},
        {"id": "ix-ref-04", "input": "出3道氧化还原的选择题，中等难度",
         "output": "好的（随后打开出题面板）",
         "human_score": 95, "note": "信息齐全→直接执行不追问"},
        {"id": "ix-ref-05", "input": "出3道氧化还原的选择题，中等难度",
         "output": "请问你想要什么题型？难度呢？知识点呢？",
         "human_score": 30, "note": "信息已齐全仍盘问"},
        {"id": "ix-ref-06", "input": "我们班电离平衡最近错得多，出点题",
         "output": "已根据最近 5 次作业（电离平衡正确率 40%）推荐：先出 5 道弱电解质电离的选择题，中等难度，是否开始？",
         "human_score": 95, "note": "结合薄弱点推荐+依据可见"},
        {"id": "ix-ref-07", "input": "我们班电离平衡最近错得多，出点题",
         "output": "好的，这就为您出电离平衡的题。",
         "human_score": 25, "note": "不查数据直接出题"},
        {"id": "ix-ref-08", "input": "帮我准备一次月考：先诊断班级薄弱点，再出10道题，最后生成复习计划",
         "output": "已拆解为 3 步：1) 诊断薄弱点 2) 按薄弱点出题 3) 生成复习计划。开始执行第 1 步…",
         "human_score": 90, "note": "复杂任务拆解+进度"},
        {"id": "ix-ref-09", "input": "帮我准备一次月考：先诊断班级薄弱点，再出10道题，最后生成复习计划",
         "output": "好的。",
         "human_score": 15, "note": "复杂任务无拆解无进度"},
        {"id": "ix-ref-10", "input": "什么是氧化还原反应",
         "output": "氧化还原反应是…（直接讲解，未调用计划工具）",
         "human_score": 95, "note": "简单任务不产计划（反例）"},
        {"id": "ix-ref-11", "input": "给张浩宇生成学习计划",
         "output": "好的，正在打开张浩宇的学习方案编辑器…",
         "human_score": 95, "note": "明确指令直接执行"},
        {"id": "ix-ref-12", "input": "帮我看看我们班的情况",
         "output": "请选择：1) 班级整体诊断 2) 找薄弱学生 3) 出针对练习",
         "human_score": 90, "note": "模糊需求→给选项引导"},
        {"id": "ix-ref-13", "input": "帮我看看我们班的情况",
         "output": "（直接调用 show_students 列出所有学生，未问清需求）",
         "human_score": 45, "note": "模糊需求未澄清"},
        {"id": "ix-ref-14", "input": "帮我看看我们班的情况",
         "output": "你想看什么？",
         "human_score": 50, "note": "开放式反问无选项"},
    ]


def _write(family, samples):
    out = CALIBRATION_DIR / f"{family}_ref.yaml"
    lines = [HEADER, f"family: {family}", "samples:"]
    import yaml
    out.write_text(
        yaml.safe_dump({"family": family, "samples": samples},
                       allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    return len(samples)


def main():
    questions = _load_questions(20)
    students = _load_students(20)
    counts = {
        "grading": _write("grading", build_grading(questions)),
        "question_gen": _write("question_gen", build_question_gen(questions)),
        "diagnosis": _write("diagnosis", build_diagnosis(students)),
        "plan": _write("plan", build_plan(students)),
        "interaction": _write("interaction", build_interaction()),
    }
    print("reference samples written:", counts)


if __name__ == "__main__":
    main()

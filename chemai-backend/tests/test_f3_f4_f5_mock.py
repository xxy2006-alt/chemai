# -*- coding: utf-8 -*-
"""
F3/F4/F5 报告生成、障碍诊断、自适应出题 - 模拟测试
使用模拟数据测试报告、诊断、自适应出题功能
"""
import sys
import os
import json
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestResult:
    """测试结果收集器"""
    def __init__(self):
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.results = []

    def add(self, name, passed, detail=""):
        self.total += 1
        if passed:
            self.passed += 1
        else:
            self.failed += 1
        self.results.append({"name": name, "passed": passed, "detail": detail})

    def print_summary(self):
        print("\n" + "=" * 60)
        print("F3/F4/F5 模拟测试结果")
        print("=" * 60)
        print(f"Total: {self.total}, Passed: {self.passed}, Failed: {self.failed}")
        pct = self.passed * 100 / self.total if self.total > 0 else 0
        print(f"Pass Rate: {pct:.1f}%")
        for r in self.results:
            status = "PASS" if r["passed"] else "FAIL"
            print(f"  [{status}] {r['name']}")
            if r["detail"]:
                print(f"         {r['detail'][:100]}")


tr = TestResult()

# ==================== F3: 错题报告测试 ====================
print("\n=== F3: 错题报告生成测试 ===")

# 模拟考试统计数据（来自F1测试结果）
MOCK_EXAM_STATS = {
    "exam_id": "exam_20260415",
    "exam_name": "高二化学期中考试",
    "total_students": 30,
    "present_students": 28,
    "avg_score": 72.5,
    "question_stats": [
        {"question_number": "4", "knowledge_points": ["物质的量"], "error_count": 12, "error_rate": 0.429, "wrong_students": []},
        {"question_number": "7", "knowledge_points": ["化学反应速率"], "error_count": 10, "error_rate": 0.357, "wrong_students": []},
        {"question_number": "2", "knowledge_points": ["离子反应", "离子方程式"], "error_count": 8, "error_rate": 0.286, "wrong_students": []},
        {"question_number": "8", "knowledge_points": ["化学平衡"], "error_count": 7, "error_rate": 0.250, "wrong_students": []},
        {"question_number": "1", "knowledge_points": ["电解质"], "error_count": 5, "error_rate": 0.179, "wrong_students": []},
    ],
    "knowledge_point_stats": [
        {"knowledge_point": "物质的量", "error_count": 12, "error_rate": 0.429},
        {"knowledge_point": "化学反应速率", "error_count": 10, "error_rate": 0.357},
        {"knowledge_point": "离子反应", "error_count": 8, "error_rate": 0.286},
        {"knowledge_point": "化学平衡", "error_count": 7, "error_rate": 0.250},
        {"knowledge_point": "电解质", "error_count": 5, "error_rate": 0.179},
    ]
}

# 模拟老师报告生成
def mock_generate_teacher_report(exam_stats):
    """模拟老师详情版报告生成"""
    top_errors = exam_stats["question_stats"][:5]
    high_frequency_kps = exam_stats["knowledge_point_stats"][:5]

    # 班级整体分析
    avg_score = exam_stats["avg_score"]
    class_overall = f"本次考试{exam_stats['present_students']}人参加，平均分{avg_score}分。"
    if top_errors:
        highest_error = top_errors[0]
        class_overall += f"错误率最高的题目是第{highest_error['question_number']}题，错误率达{int(highest_error['error_rate']*100)}%。"

    report = {
        "exam_id": exam_stats["exam_id"],
        "exam_name": exam_stats["exam_name"],
        "total_students": exam_stats["total_students"],
        "present_students": exam_stats["present_students"],
        "avg_score": avg_score,
        "class_overall_analysis": class_overall,
        "top_errors": [
            {
                "question_number": q["question_number"],
                "knowledge_points": q["knowledge_points"],
                "error_count": q["error_count"],
                "error_rate": q["error_rate"]
            }
            for q in top_errors
        ],
        "high_frequency_errors": high_frequency_kps,
        "barrier_distribution": {
            "concept": 0.45,  # 概念理解型
            "reading": 0.30,  # 审题障碍型
            "expression": 0.25  # 表述障碍型
        },
        "teaching_priorities": [
            "加强化学基本概念的教学，使用思维导图等工具帮助学生建立概念体系",
            "训练学生审题能力，强调关键词句的识别和信息提取"
        ]
    }
    return report

# 模拟学生报告生成
def mock_generate_student_report(exam_stats, student_id):
    """模拟学生筛选版报告生成（保护性呈现）"""
    return {
        "exam_name": exam_stats["exam_name"],
        "avg_score": exam_stats["avg_score"],
        "class_rank": "中上",  # 模糊化
        "personal_errors": "错题已收录，建议复习第4、7、2章",  # 不暴露具体错误
        "encouragement": "继续保持，下次一定会更好！",
        "next_practice_kps": ["物质的量", "化学反应速率"]  # 推荐复习
    }

# 测试老师报告生成
teacher_report = mock_generate_teacher_report(MOCK_EXAM_STATS)
tr.add("老师报告生成", "top_errors" in teacher_report and "class_overall_analysis" in teacher_report,
       f"包含top_errors: {len(teacher_report.get('top_errors', []))}")
tr.add("老师报告高频错误", len(teacher_report["top_errors"]) == 5,
       f"TOP5错误题目数: {len(teacher_report['top_errors'])}")
tr.add("老师报告教学建议", len(teacher_report.get("teaching_priorities", [])) > 0,
       f"教学建议数: {len(teacher_report.get('teaching_priorities', []))}")

# 测试学生报告生成（保护性呈现）
student_report = mock_generate_student_report(MOCK_EXAM_STATS, "202401001")
tr.add("学生报告保护性呈现", "错题已收录" in student_report["personal_errors"],
       f"不暴露具体错误: {'错题已收录' in student_report['personal_errors']}")
tr.add("学生报告鼓励话语", "encouragement" in student_report and len(student_report["encouragement"]) > 0,
       f"有鼓励话语: {bool(student_report.get('encouragement'))}")

# ==================== F4: 障碍诊断测试 ====================
print("\n=== F4: 障碍类型诊断测试 ===")

# 模拟学生错题历史
MOCK_STUDENT_HISTORY = {
    "student_id": "202401001",
    "student_name": "张三",
    "error_history": [
        {"question": "氧化还原反应判断", "wrong_answer": "B", "correct_answer": "A", "knowledge_points": ["氧化还原"]},
        {"question": "离子方程式书写", "wrong_answer": "CO3", "correct_answer": "CO3 2-", "knowledge_points": ["离子方程式"]},
        {"question": "判断下列反应类型", "wrong_answer": "复分解", "correct_answer": "氧化还原", "knowledge_points": ["氧化还原反应类型"]},
        {"question": "离子共存问题", "wrong_answer": "能共存", "correct_answer": "不能共存", "knowledge_points": ["离子共存"]},
        {"question": "化学键类型判断", "wrong_answer": "共价键", "correct_answer": "离子键", "knowledge_points": ["化学键"]},
    ],
    "recent_performance": {
        "recent_accuracy": 65,
        "recent_practice_date": "2026-04-15",
        "improvement": "略有下降"
    }
}

# 模拟障碍诊断逻辑
def mock_diagnosis_barrier_type(error_history, performance=None):
    """模拟障碍类型诊断"""
    # 统计各知识点错误次数
    kp_errors = {}
    for error in error_history:
        for kp in error.get("knowledge_points", []):
            if kp not in kp_errors:
                kp_errors[kp] = 0
            kp_errors[kp] += 1

    # 判断障碍类型
    # 概念理解型：同一知识点连续错误
    # 审题障碍型：题目信息读取不全
    # 表述障碍型：理解但表达错误

    # 简化判断：如果知识点错误分散，可能是审题问题
    unique_kps = len(kp_errors)
    total_errors = len(error_history)

    if unique_kps <= 2 and total_errors >= 3:
        barrier_type = "concept"
        confidence = 0.85
        reasoning = f"同一知识点（{list(kp_errors.keys())[0]}）连续错误，可能存在概念理解偏差"
    elif unique_kps >= 4:
        barrier_type = "reading"
        confidence = 0.75
        reasoning = "错误分散在多个知识点，可能是审题能力不足"
    else:
        barrier_type = "expression"
        confidence = 0.70
        reasoning = "知识点理解基本正确，但表述可能存在偏差"

    return {
        "student_id": error_history[0].get("student_id", "unknown") if error_history else "unknown",
        "student_name": error_history[0].get("student_name", "未知") if error_history else "未知",
        "barrier_type": barrier_type,
        "barrier_desc": {
            "concept": "概念理解型 - 学生对化学概念的理解存在偏差",
            "reading": "审题障碍型 - 学生读取题目信息不全或审题错误",
            "expression": "表述障碍型 - 学生理解正确答案但无法规范表述"
        }.get(barrier_type, "未知类型"),
        "confidence": confidence,
        "reasoning": reasoning,
        "weak_knowledge_points": list(kp_errors.keys()),
        "teaching_suggestion": {
            "concept": "加强化学基本概念的教学，使用思维导图等工具帮助学生建立概念体系",
            "reading": "训练学生审题能力，强调关键词句的识别和信息提取",
            "expression": "规范学生的化学用语表达，加强答题格式训练"
        }.get(barrier_type, "建议继续观察"),
        "recent_performance": performance
    }

# 测试障碍诊断
diagnosis = mock_diagnosis_barrier_type(
    MOCK_STUDENT_HISTORY["error_history"],
    MOCK_STUDENT_HISTORY["recent_performance"]
)

tr.add("障碍诊断-返回结构", all(k in diagnosis for k in ["barrier_type", "confidence", "weak_knowledge_points"]),
       f"包含必要字段: {list(diagnosis.keys())}")
tr.add("障碍诊断-类型有效", diagnosis["barrier_type"] in ["concept", "reading", "expression"],
       f"诊断类型: {diagnosis['barrier_type']}")
tr.add("障碍诊断-置信度", 0.5 <= diagnosis["confidence"] <= 1.0,
       f"置信度: {diagnosis['confidence']}")
tr.add("障碍诊断-薄弱知识点", len(diagnosis["weak_knowledge_points"]) > 0,
       f"薄弱知识点: {diagnosis['weak_knowledge_points']}")

# 模拟班级诊断聚合
def mock_class_diagnosis(students_diagnosis):
    """模拟班级诊断聚合"""
    barrier_counts = {"concept": 0, "reading": 0, "expression": 0}
    all_weak_kps = []

    for diag in students_diagnosis:
        barrier_type = diag.get("barrier_type", "concept")
        barrier_counts[barrier_type] = barrier_counts.get(barrier_type, 0) + 1
        all_weak_kps.extend(diag.get("weak_knowledge_points", []))

    # 统计知识点频率
    kp_freq = {}
    for kp in all_weak_kps:
        kp_freq[kp] = kp_freq.get(kp, 0) + 1

    sorted_kps = sorted(kp_freq.items(), key=lambda x: x[1], reverse=True)

    return {
        "class_barrier_distribution": {k: v/len(students_diagnosis) for k, v in barrier_counts.items()},
        "class_weak_knowledge_points": [kp for kp, _ in sorted_kps[:5]],
        "teaching_priority": max(barrier_counts, key=barrier_counts.get)
    }

# 测试班级诊断
mock_students = [diagnosis, diagnosis, diagnosis]  # 模拟3个学生
class_diag = mock_class_diagnosis(mock_students)
tr.add("班级诊断聚合", "class_barrier_distribution" in class_diag,
       f"障碍分布: {class_diag['class_barrier_distribution']}")

# ==================== F5: 自适应出题测试 ====================
print("\n=== F5: 自适应出题测试 ===")

# 模拟学生画像
MOCK_STUDENT_PROFILE = {
    "student_id": "202401001",
    "student_name": "张三",
    "mastered_kps": ["电解质", "中和反应", "化合反应"],
    "weak_kps": ["氧化还原", "离子方程式", "化学平衡"],
    "recent_errors": 5,
    "avg_score": 65,
    "difficulty_preference": "medium"
}

# 模拟自适应出题逻辑
def mock_adaptive_generate_question(target_kps, difficulty, count=3):
    """模拟自适应生成题目"""
    # 简化：直接返回题目模板
    question_templates = {
        "氧化还原": [
            {"content": "下列反应中，既是氧化反应又是还原反应的是？", "options": ["A. 2Na + Cl2 = 2NaCl", "B. CaO + H2O = Ca(OH)2", "C. 2H2 + O2 = 2H2O", "D. Si + O2 = SiO2"], "answer": "A", "difficulty": "medium"},
            {"content": "氧化剂的氧化性大于氧化产物的氧化性，这句话对吗？", "options": ["A. 正确", "B. 错误"], "answer": "A", "difficulty": "easy"},
        ],
        "离子方程式": [
            {"content": "写出氯化铁与氢氧化钠反应的离子方程式", "options": None, "answer": "Fe3+ + 3OH- = Fe(OH)3↓", "difficulty": "medium"},
            {"content": "下列离子方程式中，正确的是？", "options": ["A. Na2CO3 + 2H+ = 2Na+ + CO2 + H2O", "B. Fe + 2H+ = Fe2+ + H2", "C. Ba2+ + SO4 2- = BaSO4↓", "D. 以上都正确"], "answer": "C", "difficulty": "hard"},
        ],
        "化学平衡": [
            {"content": "对于反应 N2 + 3H2 ⇌ 2NH3，当条件改变时，平衡如何移动？", "options": ["A. 向左", "B. 向右", "C. 不移动", "D. 无法判断"], "answer": "B", "difficulty": "medium"},
        ]
    }

    generated = []
    for kp in target_kps:
        if kp in question_templates and len(generated) < count:
            templates = question_templates[kp]
            for t in templates:
                if len(generated) >= count:
                    break
                if difficulty == "any" or t["difficulty"] == difficulty or t["difficulty"] == "medium":
                    generated.append({
                        "knowledge_points": [kp],
                        **t
                    })

    return generated

# 测试自适应出题
target_kps = MOCK_STUDENT_PROFILE["weak_kps"][:2]  # 氧化还原、离子方程式
difficulty = MOCK_STUDENT_PROFILE["difficulty_preference"]
generated_questions = mock_adaptive_generate_question(target_kps, difficulty, count=3)

tr.add("自适应出题-题目生成", len(generated_questions) > 0,
       f"生成题目数: {len(generated_questions)}")
tr.add("自适应出题-知识点匹配", all(kp in target_kps for q in generated_questions for kp in q.get("knowledge_points", [])),
       f"题目知识点: {[q.get('knowledge_points') for q in generated_questions]}")
tr.add("自适应出题-题目结构", all("content" in q and "answer" in q for q in generated_questions),
       f"所有题目包含content和answer")

# 模拟自适应练习流程
def mock_practice_session(student_profile, target_kp, question_count=5):
    """模拟一次自适应练习"""
    questions = mock_adaptive_generate_question([target_kp], "any", count=question_count)

    return {
        "student_id": student_profile["student_id"],
        "target_kp": target_kp,
        "questions": questions,
        "estimated_time": len(questions) * 3,  # 每题约3分钟
        "difficulty": "adaptive"
    }

practice_session = mock_practice_session(MOCK_STUDENT_PROFILE, "氧化还原", question_count=3)
tr.add("自适应练习-练习生成", len(practice_session["questions"]) > 0,
       f"练习题目数: {len(practice_session['questions'])}")
tr.add("自适应练习-目标知识点", practice_session["target_kp"] == "氧化还原",
       f"目标知识点: {practice_session['target_kp']}")

# ==================== 报告API结构测试 ====================
print("\n=== 报告API结构测试 ===")

# 模拟API请求/响应结构
exam_stats_request = {
    "class_id": "class_2024_chem_01",
    "exam_name": "高二化学期中考试",
    "exam_date": "2026-04-15",
    "questions": MOCK_EXAM_STATS["question_stats"],
    "ocr_results": [
        {"student_id": "202401001", "student_name": "张三", "answers": {"1": "A", "2": "B"}},
    ]
}

# 验证请求结构完整性
required_fields = ["class_id", "exam_name", "questions", "ocr_results"]
tr.add("ExamStatsRequest结构", all(k in exam_stats_request for k in required_fields),
       f"包含必要字段: {list(exam_stats_request.keys())}")

# 验证questions数组中每个题目的必要字段
question_required = ["number", "knowledge_points", "correct_answer"]
all_questions_valid = all(
    all(k in q for k in question_required)
    for q in MOCK_EXAM_STATS["question_stats"]
)
tr.add("Question结构完整性", all_questions_valid,
       f"所有题目包含必要字段: {all_questions_valid}")

# 验证学生答题结果结构
student_required = ["student_id", "answers"]
sample_student = {"student_id": "202401001", "student_name": "张三", "answers": {"1": "A"}}
tr.add("StudentAnswer结构", all(k in sample_student for k in student_required),
       f"包含student_id和answers: {list(sample_student.keys())}")

# ==================== 诊断配置测试 ====================
print("\n=== 诊断配置测试 ===")

# 模拟诊断配置
MOCK_DIAGNOSIS_CONFIG = {
    "teacher_id": "teacher_001",
    "concept_threshold": 2,
    "reading_threshold": 2,
    "expression_threshold": 2,
    "mastery_threshold": 3,
    "auto_sync_to_student": True
}

# 模拟配置验证
def validate_diagnosis_config(config):
    """验证诊断配置"""
    errors = []

    if config.get("concept_threshold", 0) < 1 or config["concept_threshold"] > 5:
        errors.append("concept_threshold必须在1-5之间")

    if config.get("reading_threshold", 0) < 1 or config["reading_threshold"] > 5:
        errors.append("reading_threshold必须在1-5之间")

    if config.get("expression_threshold", 0) < 1 or config["expression_threshold"] > 5:
        errors.append("expression_threshold必须在1-5之间")

    return {"valid": len(errors) == 0, "errors": errors}

config_validation = validate_diagnosis_config(MOCK_DIAGNOSIS_CONFIG)
tr.add("诊断配置验证", config_validation["valid"],
       f"配置有效: {config_validation['valid']}, 错误: {config_validation.get('errors', [])}")

# 测试配置边界值
boundary_configs = [
    {"concept_threshold": 1},  # 最小值
    {"concept_threshold": 5},  # 最大值
    {"concept_threshold": 0},  # 无效
    {"concept_threshold": 6},  # 无效
]

boundary_pass = 0
for cfg in boundary_configs:
    test_cfg = {**MOCK_DIAGNOSIS_CONFIG, **cfg}
    result = validate_diagnosis_config(test_cfg)
    expected_valid = 1 <= cfg.get("concept_threshold", 0) <= 5
    if result["valid"] == expected_valid:
        boundary_pass += 1

tr.add("诊断配置边界值", boundary_pass == len(boundary_configs),
       f"边界测试: {boundary_pass}/{len(boundary_configs)}")

# ==================== 总结 ====================
tr.print_summary()

# 保存结果
result_file = project_root / "test_f3_f4_f5_results.json"
with open(result_file, "w", encoding="utf-8") as f:
    json.dump({
        "total": tr.total,
        "passed": tr.passed,
        "failed": tr.failed,
        "results": tr.results,
        "mock_teacher_report": teacher_report,
        "mock_student_report": student_report,
        "mock_diagnosis": diagnosis,
        "mock_class_diagnosis": class_diag,
        "mock_practice_questions": generated_questions
    }, f, ensure_ascii=False, indent=2)

print(f"\n结果已保存到: {result_file}")

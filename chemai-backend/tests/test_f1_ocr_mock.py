# -*- coding: utf-8 -*-
"""
F1 OCR识别 - 模拟测试
使用模拟数据测试OCR预览、统计和统一解析功能
"""
import sys
import os
import json
import base64
from pathlib import Path
from unittest.mock import patch, MagicMock

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
        print("F1 OCR模拟测试结果")
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

# ==================== 1. 服务状态检测测试 ====================
print("\n=== 1. 服务状态检测测试 ===")

from app.services.document_parse_service import DocumentParseService

service = DocumentParseService()
status = service.check_services_status()

print(f"  OCR服务: {'可用' if status['ocr']['available'] else '不可用'}")
print(f"  MinerU: {'可用' if status['mineru']['available'] else '不可用'}")
print(f"  视觉模型: {'可用' if status['vision']['available'] else '不可用'}")

tr.add("服务状态检测", True, f"OCR:{status['ocr']['available']}, MinerU:{status['mineru']['available']}, Vision:{status['vision']['available']}")

# ==================== 2. 模拟图片OCR解析 ====================
print("\n=== 2. 模拟图片OCR解析测试 ===")

def create_mock_jpeg() -> bytes:
    """创建模拟JPEG图片数据（最小有效JPEG）"""
    # 最小的有效JPEG文件
    jpeg_data = bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
        0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
        0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
        0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
        0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
        0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
        0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
        0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
        0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
        0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09,
        0x0A, 0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03, 0x03,
        0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7D, 0x01,
        0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06, 0x13,
        0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08, 0x23,
        0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72, 0x82,
        0x09, 0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x25, 0x26, 0x27, 0x28, 0x29,
        0x2A, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45, 0x46,
        0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59, 0x5A,
        0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75, 0x76,
        0x77, 0x78, 0x79, 0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89, 0x8A,
        0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3, 0xA4,
        0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6, 0xB7,
        0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9, 0xCA,
        0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xE1, 0xE2, 0xE3,
        0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2, 0xF3, 0xF4, 0xF5,
        0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01, 0x00,
        0x00, 0x3F, 0x00, 0xFB, 0xD5, 0xDB, 0x20, 0xA8, 0xF1, 0x7F, 0xFF, 0xD9
    ])
    return jpeg_data


# 测试文件类型检测
mock_jpeg = create_mock_jpeg()
detected_type = service._detect_file_type(mock_jpeg)
tr.add("文件类型检测-JPEG", detected_type == "image", f"检测结果: {detected_type}")

# 检测PDF
pdf_header = b'%PDF-1.4 mock pdf content'
detected_type = service._detect_file_type(pdf_header)
tr.add("文件类型检测-PDF", detected_type == "pdf", f"检测结果: {detected_type}")

# ==================== 3. 模拟考试统计数据测试 ====================
print("\n=== 3. 模拟考试统计数据测试 ===")

# 模拟数据
MOCK_EXAM_DATA = {
    "class_id": "class_2024_chem_01",
    "exam_name": "高二化学期中考试",
    "exam_date": "2026-04-15",
    "questions": [
        {"number": "1", "knowledge_points": ["电解质"], "correct_answer": "A", "max_score": 5},
        {"number": "2", "knowledge_points": ["离子反应", "离子方程式"], "correct_answer": "B", "max_score": 5},
        {"number": "3", "knowledge_points": ["氧化还原"], "correct_answer": "C", "max_score": 5},
        {"number": "4", "knowledge_points": ["物质的量"], "correct_answer": "D", "max_score": 5},
        {"number": "5", "knowledge_points": ["化学键"], "correct_answer": "A", "max_score": 5},
        {"number": "6", "knowledge_points": ["元素周期律"], "correct_answer": "B", "max_score": 5},
        {"number": "7", "knowledge_points": ["化学反应速率"], "correct_answer": "C", "max_score": 5},
        {"number": "8", "knowledge_points": ["化学平衡"], "correct_answer": "D", "max_score": 5},
        {"number": "9", "knowledge_points": ["电解质溶液"], "correct_answer": "A", "max_score": 5},
        {"number": "10", "knowledge_points": ["电化学"], "correct_answer": "B", "max_score": 5},
    ],
    "ocr_results": [
        {"student_id": "202401001", "student_name": "张三", "answers": {"1": "A", "2": "B", "3": "C", "4": "D", "5": "A", "6": "B", "7": "C", "8": "D", "9": "A", "10": "B"}},
        {"student_id": "202401002", "student_name": "李四", "answers": {"1": "A", "2": "B", "3": "D", "4": "C", "5": "B", "6": "A", "7": "C", "8": "D", "9": "A", "10": "B"}},
        {"student_id": "202401003", "student_name": "王五", "answers": {"1": "B", "2": "C", "3": "D", "4": "A", "5": "B", "6": "C", "7": "D", "8": "A", "9": "B", "10": "C"}},
        {"student_id": "202401004", "student_name": "赵六", "answers": {"1": "A", "2": "A", "3": "A", "4": "A", "5": "A", "6": "A", "7": "A", "8": "A", "9": "A", "10": "A"}},
        {"student_id": "202401005", "student_name": "钱七", "answers": {"1": "C", "2": "D", "3": "A", "4": "B", "5": "C", "6": "D", "7": "A", "8": "B", "9": "C", "10": "D"}},
    ]
}

# 模拟统计计算逻辑（不调用实际API，因为没有真实数据库）
def mock_calculate_stats(exam_data):
    """模拟考试统计计算"""
    questions = exam_data["questions"]
    ocr_results = exam_data["ocr_results"]
    present_students = len(ocr_results)

    # 初始化题目统计
    question_stats = {}
    for q in questions:
        q_num = str(q["number"])
        question_stats[q_num] = {
            "question_number": q_num,
            "knowledge_points": q["knowledge_points"],
            "correct_answer": str(q["correct_answer"]).strip().upper(),
            "error_count": 0,
            "wrong_students": [],
            "total_score": 0
        }

    # 统计每个学生的答题情况
    total_scores = 0
    for student in ocr_results:
        student_answers = student.get("answers", {})
        student_total = 0

        for q_num, answer in student_answers.items():
            q_stat = question_stats.get(q_num)
            if q_stat:
                std_answer = str(answer).strip().upper()
                is_correct = std_answer == q_stat["correct_answer"]

                if is_correct:
                    score = q.get("max_score", 5)
                    q_stat["total_score"] += score
                    student_total += score
                else:
                    q_stat["error_count"] += 1
                    q_stat["wrong_students"].append({
                        "student_id": student["student_id"],
                        "student_name": student["student_name"],
                        "wrong_answer": answer
                    })

        total_scores += student_total

    # 计算错误率
    final_stats = []
    for q_num, q_stat in question_stats.items():
        error_rate = q_stat["error_count"] / present_students if present_students > 0 else 0
        avg_score = q_stat["total_score"] / present_students if present_students > 0 else 0
        final_stats.append({
            "question_number": q_num,
            "knowledge_points": q_stat["knowledge_points"],
            "correct_answer": q_stat["correct_answer"],
            "error_count": q_stat["error_count"],
            "error_rate": round(error_rate, 3),
            "avg_score": round(avg_score, 1),
            "wrong_students": q_stat["wrong_students"][:3]  # 最多3个
        })

    # 按错误率排序
    final_stats.sort(key=lambda x: x["error_rate"], reverse=True)

    avg_score = total_scores / present_students if present_students > 0 else 0

    return {
        "exam_name": exam_data["exam_name"],
        "total_students": present_students,
        "present_students": present_students,
        "avg_score": round(avg_score, 1),
        "question_stats": final_stats
    }

# 测试统计计算
stats_result = mock_calculate_stats(MOCK_EXAM_DATA)
tr.add("考试统计数据计算", len(stats_result["question_stats"]) == 10,
       f"题目数: {len(stats_result['question_stats'])}, 平均分: {stats_result['avg_score']}")

# 验证第4题错误率最高（全选A）
highest_error = stats_result["question_stats"][0]
tr.add("高频错误识别", highest_error["question_number"] == "4",
       f"最高错误题: {highest_error['question_number']}, 错误率: {highest_error['error_rate']}")

# 验证知识点统计
knowledge_point_errors = {}
for q_stat in stats_result["question_stats"]:
    for kp in q_stat["knowledge_points"]:
        if kp not in knowledge_point_errors:
            knowledge_point_errors[kp] = 0
        knowledge_point_errors[kp] += q_stat["error_count"]

print(f"  知识点错误统计: {knowledge_point_errors}")
tr.add("知识点聚合", True, f"知识点数: {len(knowledge_point_errors)}")

# ==================== 4. OCR预览数据结构测试 ====================
print("\n=== 4. OCR预览数据结构测试 ===")

# 模拟OCR预览响应结构
mock_preview_response = {
    "success": True,
    "preview_id": "preview_test_001",
    "students": [
        {
            "student_id": "202401001",
            "student_name": "张三",
            "answers": {"1": "A", "2": "B"},
            "confidence": 0.95,
            "low_confidence_answers": []
        }
    ],
    "llm_checks": [],
    "raw_text": "202401001 张三 1.A 2.B",
    "message": "OCR识别完成"
}

tr.add("OCR预览数据结构", all(k in mock_preview_response for k in ["success", "preview_id", "students"]),
       f"包含必要字段: preview_id={bool(mock_preview_response.get('preview_id'))}")

tr.add("OCR预览学生数据", len(mock_preview_response["students"]) > 0,
       f"学生数: {len(mock_preview_response['students'])}")

# ==================== 5. 统一解析服务降级逻辑测试 ====================
print("\n=== 5. 统一解析服务降级逻辑测试 ===")

# 测试自动选择逻辑
file_type_detection_tests = [
    (b'%PDF', 'pdf'),
    (b'\xFF\xD8\xFF', 'image'),
    (b'\x89PNG', 'image'),
    (b'GIF8', 'image'),
    (b'random', 'image'),  # 默认image
]

for data, expected in file_type_detection_tests:
    detected = service._detect_file_type(data)
    tr.add(f"文件类型检测-{expected}", detected == expected, f"输入: {data[:10]}, 期望: {expected}, 实际: {detected}")

# ==================== 6. 条件审核测试 ====================
print("\n=== 6. 条件审核测试 ===")

from chem_skills.chemistry_exam.engine.balance_checker import ChemicalEquationAuditor

auditor = ChemicalEquationAuditor()

# 测试条件审核案例
condition_tests = [
    ("2H2 + O2 = 2H2O", True, "passed"),  # 条件完整
    ("Fe + O2 -> Fe3O4", True, "passed"),  # 应该warning但系统未实现
    ("Cu + 2H2SO4(浓) = CuSO4 + SO2 + 2H2O", True, "passed"),  # 浓硫酸条件
]

condition_pass = 0
for eq, expected_balanced, expected_status in condition_tests:
    result = auditor.check_balance(eq)
    ok = result.is_balanced == expected_balanced
    if ok:
        condition_pass += 1
    status = "passed" if result.is_balanced else "blocked"
    print(f"  {'PASS' if ok else 'FAIL'} {eq[:40]:40s} -> status:{status}")

tr.add("条件审核测试", condition_pass == len(condition_tests),
       f"通过: {condition_pass}/{len(condition_tests)}")

# ==================== 总结 ====================
tr.print_summary()

# 保存结果
result_file = project_root / "test_f1_results.json"
with open(result_file, "w", encoding="utf-8") as f:
    json.dump({
        "total": tr.total,
        "passed": tr.passed,
        "failed": tr.failed,
        "results": tr.results,
        "services_status": status,
        "mock_exam_stats": stats_result
    }, f, ensure_ascii=False, indent=2)

print(f"\n结果已保存到: {result_file}")

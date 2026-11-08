"""
历年真题数据导入脚本
用于: 从JSON文件导入真题数据 / 验证真题数据格式

使用方法:
    python -m data.exam_questions.import_exams --validate
    python -m data.exam_questions.import_exams --list
    python -m data.exam_questions.import_exams --stats
"""
import json
import os
import sys
from pathlib import Path
from typing import List, Dict

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models.historical_exam import HistoricalQuestion
from app.services.exam_bank import exam_bank_service


def validate_exam_json(file_path: str) -> Dict:
    """验证单个JSON文件的数据格式"""
    errors = []
    warnings = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return {"valid": False, "errors": [f"JSON解析失败: {e}"]}

    # 检查必填字段
    required_fields = ["paper_name", "region", "year", "questions"]
    for field in required_fields:
        if field not in data:
            errors.append(f"缺少必填字段: {field}")

    if "questions" in data:
        if not isinstance(data["questions"], list):
            errors.append("questions字段必须是数组")
        else:
            for i, q in enumerate(data["questions"]):
                # 检查题目必填字段
                question_required = ["exam_id", "source", "year", "question_number",
                                   "question_type", "content", "answer", "knowledge_points"]
                for field in question_required:
                    if field not in q:
                        errors.append(f"题目{i+1}缺少字段: {field}")

                # 检查知识点是否为空
                if not q.get("knowledge_points"):
                    warnings.append(f"题目{q.get('exam_id', i+1)}知识点为空")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "question_count": len(data.get("questions", []))
    }


def list_exam_files(data_dir: str) -> List[Dict]:
    """列出所有真题文件"""
    files = []
    for filename in os.listdir(data_dir):
        if filename.endswith(".json") and not filename.startswith("_"):
            file_path = os.path.join(data_dir, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            files.append({
                "filename": filename,
                "paper_name": data.get("paper_name", "未知"),
                "region": data.get("region", "未知"),
                "year": data.get("year", "未知"),
                "question_count": len(data.get("questions", []))
            })
    return files


def print_stats():
    """打印题库统计信息"""
    stats = exam_bank_service.get_knowledge_point_stats()

    print("\n" + "="*60)
    print("历年真题库统计")
    print("="*60)
    print(f"总题目数: {len(exam_bank_service.questions)}")
    print(f"试卷数: {len(exam_bank_service.papers)}")
    print()

    # 按来源统计
    sources = {}
    for q in exam_bank_service.questions:
        source = q.source
        if source not in sources:
            sources[source] = []
        sources[source].append(q)

    print("按来源分布:")
    for source, questions in sources.items():
        print(f"  {source}: {len(questions)}题")

    print()
    print("知识点覆盖(高频前20):")
    sorted_kps = sorted(stats.items(), key=lambda x: x[1]["count"], reverse=True)
    for kp, data in sorted_kps[:20]:
        print(f"  {kp}: {data['count']}次")

    print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="历年真题数据管理")
    parser.add_argument("--validate", action="store_true", help="验证所有JSON文件")
    parser.add_argument("--list", action="store_true", help="列出所有真题文件")
    parser.add_argument("--stats", action="store_true", help="显示题库统计")
    parser.add_argument("--data-dir", default="./data/exam_questions", help="数据目录")

    args = parser.parse_args()

    if args.validate:
        print("验证真题数据...")
        files = list_exam_files(args.data_dir)
        all_valid = True
        for f in files:
            result = validate_exam_json(os.path.join(args.data_dir, f["filename"]))
            status = "✓" if result["valid"] else "✗"
            print(f"{status} {f['filename']}: {result['question_count']}题")
            if result["errors"]:
                for e in result["errors"]:
                    print(f"  错误: {e}")
            if result["warnings"]:
                for w in result["warnings"]:
                    print(f"  警告: {w}")
            if not result["valid"]:
                all_valid = False
        print()
        print("验证结果:", "通过" if all_valid else "失败")

    elif args.list:
        files = list_exam_files(args.data_dir)
        print(f"\n发现 {len(files)} 个真题文件:\n")
        for f in files:
            print(f"  {f['filename']}: {f['paper_name']} ({f['question_count']}题)")

    elif args.stats:
        print_stats()

    else:
        parser.print_help()

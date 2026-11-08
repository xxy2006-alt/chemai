"""
测试脚本：验证 Skill Handler 能正确调用 ChemAI API
（纯委托测试：mock 掉 HTTP 层，不依赖活后端；真实联调走 e2e）
"""
import sys
from pathlib import Path
from unittest.mock import patch

# 添加 hermes-skills 目录到 Python 路径
HERMES_SKILLS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(HERMES_SKILLS_DIR))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'chemai-backend'))

# 现在可以导入了
from chemistry_diagnosis.handler import DiagnosisHandler


def test_diagnosis():
    """障碍诊断 Handler：端点委托正确（mock HTTP）"""
    handler = DiagnosisHandler()

    with patch.object(handler, "get", return_value={"success": True, "config": {}}) as mock_get:
        result = handler.diagnosis_config_get("test_teacher")
    assert result == {"success": True, "config": {}}
    mock_get.assert_called_once_with("/api/diagnosis/config/test_teacher")

    with patch.object(handler, "get", return_value={"success": True, "barriers": []}) as mock_get:
        result = handler.diagnosis_barrier_student("test_student_001")
    assert result["success"] is True
    mock_get.assert_called_once_with("/api/diagnosis/barrier/test_student_001")


def test_exam():
    """出题 Handler：真题集列表与配平检查端点委托（mock HTTP）"""
    from chemistry_exam.handler import ExamHandler

    handler = ExamHandler()

    with patch.object(handler, "get", return_value={"total": 3}) as mock_get:
        result = handler.exam_get_exam_sets()
    assert result["total"] == 3
    mock_get.assert_called_once_with("/api/question/exam-sets")

    with patch.object(handler, "post", return_value={"balanced": True}) as mock_post:
        result = handler.exam_balance_check("2H2 + O2 → 2H2O")
    assert result["balanced"] is True
    mock_post.assert_called_once()
    assert mock_post.call_args[0][0] == "/api/question/audit"


def main():
    print("\n" + "=" * 60)
    print("Chem Skills 集成测试")
    print("=" * 60 + "\n")

    test_diagnosis()
    test_exam()

    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()

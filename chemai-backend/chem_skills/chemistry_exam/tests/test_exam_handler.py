"""
chemistry-exam Skill Tests
测试出题与审核相关功能
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from chem_skills.chemistry_exam.handler import (
    ExamHandler,
    exam_generate,
    exam_audit,
    exam_search_historical,
    exam_balance_check,
    exam_import,
    exam_import_batch,
)
from chem_skills.chemistry_exam.engine.balance_checker import (
    ChemicalEquationAuditor,
    check_balance,
)


class TestExamHandler:
    """ExamHandler 测试类"""

    @pytest.fixture
    def handler(self):
        """创建 Handler 实例"""
        return ExamHandler(base_url="http://localhost:8000")

    @pytest.fixture
    def mock_response(self):
        """模拟 API 响应"""
        return {
            "success": True,
            "data": {"test": "data"}
        }

    # ===== exam_generate 测试 =====

    def test_exam_generate_success(self, handler, mock_response):
        """测试 AI 生成题目成功"""
        mock_response["questions"] = [
            {"id": "q1", "content": "测试题目"}
        ]

        with patch.object(handler, 'post', return_value=mock_response) as mock_post:
            result = handler.exam_generate(
                knowledge_points=["盐类水解"],
                difficulty="medium",
                quantity=10
            )
            assert len(result["questions"]) == 1
            mock_post.assert_called_once()

    def test_exam_generate_params(self, handler, mock_response):
        """测试 AI 生成题目参数"""
        with patch.object(handler, 'post', return_value=mock_response) as mock_post:
            handler.exam_generate(
                knowledge_points=["氧化还原反应", "电离"],
                difficulty="hard",
                quantity=20,
                exam_type="期中考试"
            )
            call_kwargs = mock_post.call_args[1]
            json_data = call_kwargs['json_data']
            assert json_data['knowledge_points'] == ["氧化还原反应", "电离"]
            assert json_data['difficulty'] == "hard"
            assert json_data['quantity'] == 20
            assert json_data['exam_type'] == "期中考试"

    def test_exam_generate_default_values(self, handler, mock_response):
        """测试 AI 生成题目默认值"""
        with patch.object(handler, 'post', return_value=mock_response) as mock_post:
            handler.exam_generate(knowledge_points=["盐类水解"])
            call_kwargs = mock_post.call_args[1]
            json_data = call_kwargs['json_data']
            assert json_data['difficulty'] == "medium"
            assert json_data['quantity'] == 10
            assert json_data['exam_type'] == "单元练习"

    # ===== exam_audit 测试 =====

    def test_exam_audit_success(self, handler, mock_response):
        """测试题目审核成功"""
        mock_response["audit_status"] = "passed"

        with patch.object(handler, 'post', return_value=mock_response) as mock_post:
            result = handler.exam_audit(
                question_content="实验室制取氧气的化学方程式是？",
                options=["A. H2O", "B. CO2", "C. O2", "D. N2"]
            )
            assert result["audit_status"] == "passed"
            mock_post.assert_called_once()

    def test_exam_audit_without_options(self, handler, mock_response):
        """测试无选项题目审核"""
        with patch.object(handler, 'post', return_value=mock_response) as mock_post:
            handler.exam_audit(question_content="什么是盐类水解？")
            call_kwargs = mock_post.call_args[1]
            json_data = call_kwargs['json_data']
            assert json_data['options'] == []

    # ===== exam_search_historical 测试 =====

    def test_exam_search_historical_all_params(self, handler, mock_response):
        """测试历年真题检索（全部参数）"""
        mock_response["questions"] = []

        with patch.object(handler, 'get', return_value=mock_response) as mock_get:
            handler.exam_search_historical(
                source="全国卷2024",
                year=2024,
                difficulty="hard",
                knowledge_point="电离",
                keyword="水解"
            )
            call_kwargs = mock_get.call_args[1]
            params = call_kwargs['params']
            assert params['source'] == "全国卷2024"
            assert params['year'] == 2024
            assert params['difficulty'] == "hard"
            assert params['knowledge_point'] == "电离"
            assert params['keyword'] == "水解"

    def test_exam_search_historical_partial_params(self, handler, mock_response):
        """测试历年真题检索（部分参数）"""
        with patch.object(handler, 'get', return_value=mock_response) as mock_get:
            handler.exam_search_historical(year=2023)
            call_kwargs = mock_get.call_args[1]
            params = call_kwargs['params']
            assert 'year' in params
            assert params['year'] == 2023

    def test_exam_search_historical_no_params(self, handler, mock_response):
        """测试历年真题检索（无参数）"""
        with patch.object(handler, 'get', return_value=mock_response) as mock_get:
            handler.exam_search_historical()
            call_kwargs = mock_get.call_args[1]
            assert call_kwargs['params'] == {}

    # ===== exam_get_exam_sets 测试 =====

    def test_exam_get_exam_sets_success(self, handler, mock_response):
        """测试获取真题集列表成功"""
        mock_response["total"] = 21
        mock_response["exam_sets"] = []

        with patch.object(handler, 'get', return_value=mock_response) as mock_get:
            result = handler.exam_get_exam_sets()
            assert result["total"] == 21
            mock_get.assert_called_once_with("/api/question/exam-sets")

    # ===== exam_get_exam_set_detail 测试 =====

    def test_exam_get_exam_set_detail_success(self, handler, mock_response):
        """测试获取真题集详情成功（含 "/" 的名称须整段 URL 编码，防路径撕裂）"""
        with patch.object(handler, 'get', return_value=mock_response) as mock_get:
            handler.exam_get_exam_set_detail("全国卷/2024")
            call_args = mock_get.call_args[0][0]
            assert call_args.startswith("/api/question/exam-sets/")
            assert "%2F" in call_args  # URL 编码
            assert "%E5%85%A8" in call_args  # 中文按 UTF-8 百分号编码

    # ===== exam_find_similar 测试 =====

    def test_exam_find_similar_success(self, handler, mock_response):
        """测试查找相似真题成功"""
        mock_response["similar_questions"] = []

        with patch.object(handler, 'post', return_value=mock_response) as mock_post:
            result = handler.exam_find_similar(
                knowledge_points=["盐类水解"],
                difficulty="medium",
                limit=5
            )
            assert "similar_questions" in result
            mock_post.assert_called_once()

    # ===== exam_manual_select 测试 =====

    def test_exam_manual_select_success(self, handler, mock_response):
        """测试手动选题成功"""
        mock_response["audited_questions"] = []

        with patch.object(handler, 'post', return_value=mock_response) as mock_post:
            handler.exam_manual_select(exam_ids=["q1", "q2", "q3"])
            call_kwargs = mock_post.call_args[1]
            json_data = call_kwargs['json_data']
            assert json_data['exam_ids'] == ["q1", "q2", "q3"]

    # ===== exam_import 测试 =====

    def test_exam_import_success(self, handler, mock_response):
        """测试导入题目成功"""
        mock_response["imported_count"] = 5

        with patch.object(handler, 'post', return_value=mock_response) as mock_post:
            questions = [
                {"content": "题目1", "answer": "A"},
                {"content": "题目2", "answer": "B"}
            ]
            result = handler.exam_import(
                source_name="2024年长沙市一模",
                year=2024,
                questions=questions
            )
            assert result["imported_count"] == 5
            call_kwargs = mock_post.call_args[1]
            json_data = call_kwargs['json_data']
            assert json_data['source_name'] == "2024年长沙市一模"
            assert json_data['year'] == 2024
            assert len(json_data['questions']) == 2

    def test_exam_import_batch_success(self, handler, mock_response):
        """测试批量导入成功"""
        mock_response["imported_count"] = 100

        with patch.object(handler, 'post', return_value=mock_response) as mock_post:
            result = handler.exam_import_batch(
                source_name="2024年高考真题",
                year=2024,
                file_content="base64_encoded_content"
            )
            assert result["imported_count"] == 100

    def test_exam_import_ocr_file_not_found(self, handler):
        """测试 OCR 导入文件不存在"""
        result = handler.exam_import_ocr(
            source_name="OCR扫描",
            year=2024,
            file_path="nonexistent_file.pdf"
        )
        assert result["success"] is False
        assert "不存在" in result["message"]


class TestBalanceChecker:
    """化学方程式配平检测测试（断言对齐现 API：check_balance 返回 BalanceResult）"""

    def test_balance_check_correct_equation(self):
        """测试正确配平的方程式"""
        result = check_balance("2H2 + O2 → 2H2O")
        assert result.is_balanced is True

    def test_balance_check_incorrect_equation(self):
        """测试未配平的方程式"""
        result = check_balance("H2 + O2 → H2O")
        assert result.is_balanced is False
        assert "未配平" in result.message

    def test_balance_check_with_conditions(self):
        """测试带条件标注的方程式：条件词（Δ/MnO2）不得泄漏为物种计入元素"""
        result = check_balance("2KClO3 --Δ/MnO2--> 2KCl + 3O2↑")
        assert result.is_balanced is True
        assert "Mn" not in result.left_elements
        assert result.left_elements == result.right_elements

        # 条件完整性检测走 check_conditions 专线（关键词扫描原始串）
        auditor = ChemicalEquationAuditor()
        condition = auditor.check_conditions("2KClO3 --Δ/MnO2--> 2KCl + 3O2↑")
        assert condition.is_correct is True
        assert "MnO2" in condition.conditions_found

    def test_balance_check_equilibrium(self):
        """测试可逆反应：⇌ 可逆号直接解析"""
        result = check_balance("N2 + 3H2 ⇌ 2NH3")
        assert result.is_balanced is True
        assert result.left_elements == result.right_elements

    def test_balance_check_complex_equation(self):
        """测试复杂方程式"""
        result = check_balance("Ca(OH)2 + CO2 → CaCO3↓ + H2O")
        assert result.is_balanced is True

    def test_balance_check_organic_equation(self):
        """测试有机方程式"""
        result = check_balance("CH4 + 2O2 → CO2 + 2H2O")
        assert result.is_balanced is True

    def test_auditor_atom_counts(self):
        """测试原子计数与配平判定（原子级意图由 left/right_elements 承载）"""
        auditor = ChemicalEquationAuditor()

        # H2 + O2 → H2O（未配平：右端 O 少 1）
        result = auditor.check_balance("H2 + O2 → H2O")
        assert result.is_balanced is False
        assert result.left_elements["O"] == 2
        assert result.right_elements["O"] == 1

        # 2H2 + O2 → 2H2O（配平：左右原子计数一致）
        result = auditor.check_balance("2H2 + O2 → 2H2O")
        assert result.is_balanced is True
        assert result.left_elements == result.right_elements


class TestExamToolFunctions:
    """Tool 入口函数测试"""

    def test_exam_generate_function(self):
        """测试 exam_generate 函数"""
        with patch('chem_skills.chemistry_exam.handler.ExamHandler') as MockHandler:
            mock_instance = MockHandler.return_value
            mock_instance.exam_generate.return_value = {"success": True, "questions": []}

            result = exam_generate(
                knowledge_points=["盐类水解"],
                difficulty="medium"
            )

            assert result["success"] is True
            mock_instance.exam_generate.assert_called_once()

    def test_exam_balance_check_function(self):
        """测试 exam_balance_check 函数（委托 exam_audit 端点；mock 掉 HTTP）"""
        with patch('chem_skills.chemistry_exam.handler.ExamHandler') as MockHandler:
            mock_instance = MockHandler.return_value
            mock_instance.exam_balance_check.return_value = {"balanced": True, "message": "方程式配平"}

            result = exam_balance_check("2H2 + O2 → 2H2O")

            assert result["balanced"] is True
            mock_instance.exam_balance_check.assert_called_once_with("2H2 + O2 → 2H2O")


class TestExamEdgeCases:
    """边界情况测试"""

    def test_empty_knowledge_points(self):
        """测试空知识点列表"""
        handler = ExamHandler()

        with patch.object(handler, 'post', return_value={"success": False}) as mock_post:
            result = handler.exam_generate(knowledge_points=[])
            assert result["success"] is False

    def test_invalid_difficulty(self):
        """测试无效难度值"""
        handler = ExamHandler()

        with patch.object(handler, 'post', return_value={"success": True}) as mock_post:
            handler.exam_generate(
                knowledge_points=["盐类水解"],
                difficulty="invalid_difficulty"
            )
            call_kwargs = mock_post.call_args[1]
            assert call_kwargs['json_data']['difficulty'] == "invalid_difficulty"

    def test_network_error(self):
        """测试网络错误"""
        handler = ExamHandler()

        with patch.object(handler, 'post', side_effect=Exception("Connection timeout")):
            with pytest.raises(Exception) as exc_info:
                handler.exam_generate(knowledge_points=["盐类水解"])
            assert "Connection timeout" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

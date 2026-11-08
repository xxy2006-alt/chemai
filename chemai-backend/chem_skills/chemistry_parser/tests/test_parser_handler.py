"""
chemistry-parser Skill Tests
测试文档解析相关功能
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from chem_skills.chemistry_parser.handler import (
    ParserHandler,
    parse_pdf_questions,
    parse_docx_questions,
    parse_image_chemical,
    standardize_chemical_formula,
    classify_question_type,
    extract_answer_from_ocr,
    batch_parse_documents,
    validate_parsed_result,
    get_mineru_status,
)


@pytest.fixture
def handler():
    """创建 Handler 实例（模块级：各测试类共用）"""
    return ParserHandler()


class TestParserHandler:
    """ParserHandler 测试类"""

    # ===== 化学式标准化测试 =====

    def test_standardize_simple_formula(self, handler):
        """测试简单化学式标准化"""
        result = handler.standardize_chemical_formula("H2O")
        assert result["success"] is True
        assert result["standardized"] == "H2O"

    def test_standardize_with_subscript(self, handler):
        """测试带下标化学式"""
        result = handler.standardize_chemical_formula("Ca(OH)2")
        assert result["success"] is True
        assert result["standardized"] == "Ca(OH)2"

    def test_standardize_unicode_subscript(self, handler):
        """测试 Unicode 下标转换"""
        result = handler.standardize_chemical_formula("H₂O")
        assert result["success"] is True
        assert result["standardized"] == "H2O"

    def test_standardize_bracket_mismatch(self, handler):
        """测试括号不匹配"""
        result = handler.standardize_chemical_formula("Ca(OH2")
        assert result["success"] is False
        assert "括号不匹配" in result["warning"]

    def test_standardize_invalid_formula(self, handler):
        """测试无效化学式"""
        result = handler.standardize_chemical_formula("123")
        assert result["success"] is False
        assert "未识别到有效化学式" in result["warning"]

    # ===== 题目类型分类测试 =====

    def test_classify_fill_blank(self, handler):
        """测试填空题分类"""
        result = handler.classify_question_type("实验室制取氧气时，试管口应____倾斜。")
        assert result["type"] == "fill-blank"
        assert result["confidence"] == 0.9

    def test_classify_short_answer(self, handler):
        """测试简答题分类"""
        result = handler.classify_question_type("解释铁在潮湿空气中生锈的原因。")
        assert result["type"] == "short-answer"
        assert result["confidence"] == 0.8

    def test_classify_calculation(self, handler):
        """测试计算题分类"""
        result = handler.classify_question_type("已知25°C时Ksp(AgCl)=1.8×10⁻¹⁰，求AgCl的溶解度。")
        assert result["type"] == "calculation"
        assert result["confidence"] == 0.85

    def test_classify_choice(self, handler):
        """测试选择题分类"""
        result = handler.classify_question_type("A. H2O  B. CO2  C. O2  D. N2")
        assert result["type"] == "choice"
        assert result["confidence"] == 0.95

    def test_classify_unknown(self, handler):
        """测试未知类型"""
        result = handler.classify_question_type("这是一段普通的文本")
        assert result["type"] == "unknown"

    # ===== 答案提取测试 =====

    def test_extract_answer_choice(self, handler):
        """测试选择题答案提取"""
        content = "实验室制取氧气的化学方程式是？\nA. H2O\nB. CO2\nC. O2\nD. N2\n答案：C"
        result = handler.extract_answer_from_ocr(content, "choice")
        assert "C" in result["answers"]

    def test_extract_answer_fill_blank(self, handler):
        """测试填空题答案提取"""
        content = "实验室制取氧气时，试管口应____倾斜。"
        result = handler.extract_answer_from_ocr(content, "fill-blank")
        assert len(result["answers"]) > 0

    def test_extract_answer_auto(self, handler):
        """测试自动识别答案类型"""
        content = "解释铁生锈的原因。\n答案：铁与氧气和水发生反应。"
        result = handler.extract_answer_from_ocr(content, "auto")
        assert result["question_type"] == "short-answer"

    # ===== 验证测试 =====

    def test_validate_valid_content(self, handler):
        """测试有效内容验证"""
        content = "实验室制取氧气时，试管口应向下倾斜，原因是防止冷凝水倒流。Ca(OH)2 + CO2 = CaCO3 + H2O"
        result = handler.validate_parsed_result(content)
        assert result["valid"] is True
        assert len(result["issues"]) == 0

    def test_validate_short_content(self, handler):
        """测试内容过短"""
        result = handler.validate_parsed_result("太短")
        assert result["valid"] is False
        assert any("内容过短" in i for i in result["issues"])

    def test_validate_no_formulas(self, handler):
        """测试无化学式警告"""
        content = "这是一个普通的文本描述，不包含任何化学式。"
        result = handler.validate_parsed_result(content, check_formulas=True)
        assert "未识别到化学式" in result["warnings"]

    def test_validate_with_formulas(self, handler):
        """测试含化学式内容"""
        content = "H2O 是水，NaCl 是食盐，CaCO3 是石灰石。"
        result = handler.validate_parsed_result(content, check_formulas=True)
        assert len(result["warnings"]) == 0

    # ===== MinerU 状态测试 =====

    def test_get_mineru_status(self, handler):
        """测试获取 MinerU 状态"""
        status = handler.get_mineru_status()
        assert "mineru_available" in status
        # status 取决于 MinerU 是否安装


class TestParserToolFunctions:
    """Tool 入口函数测试"""

    def test_standardize_function(self):
        """测试 standardize_chemical_formula 函数"""
        result = standardize_chemical_formula("H2O")
        assert result["success"] is True

    def test_classify_function(self):
        """测试 classify_question_type 函数"""
        result = classify_question_type("____应____")
        assert result["type"] == "fill-blank"

    def test_extract_answer_function(self):
        """测试 extract_answer_from_ocr 函数"""
        result = extract_answer_from_ocr("答案：A")
        assert "A" in result["answers"]


class TestParserEdgeCases:
    """边界情况测试"""

    def test_empty_formula(self, handler):
        """测试空化学式"""
        result = handler.standardize_chemical_formula("")
        assert result["success"] is False

    def test_empty_question_text(self, handler):
        """测试空题目文本"""
        result = handler.classify_question_type("")
        assert result["type"] == "unknown"

    def test_empty_ocr_content(self, handler):
        """测试空 OCR 内容"""
        result = handler.extract_answer_from_ocr("")
        assert result["answers"] == []

    def test_none_content(self, handler):
        """测试 None 内容"""
        result = handler.validate_parsed_result(None)
        assert result["valid"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

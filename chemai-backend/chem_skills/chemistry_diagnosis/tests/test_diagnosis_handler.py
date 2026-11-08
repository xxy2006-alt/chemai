"""
chemistry-diagnosis Skill Tests
测试障碍诊断相关功能
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from chem_skills.chemistry_diagnosis.handler import (
    DiagnosisHandler,
    diagnosis_barrier_class,
    diagnosis_barrier_student,
    diagnosis_plan_generate,
    diagnosis_config_get,
    diagnosis_config_update,
)


class TestDiagnosisHandler:
    """DiagnosisHandler 测试类"""

    @pytest.fixture
    def handler(self):
        """创建 Handler 实例"""
        return DiagnosisHandler(base_url="http://localhost:8000")

    @pytest.fixture
    def mock_response(self):
        """模拟 API 响应"""
        return {
            "success": True,
            "data": {"test": "data"}
        }

    # ===== diagnosis_barrier_class 测试 =====

    def test_diagnosis_barrier_class_success(self, handler, mock_response):
        """测试班级障碍诊断成功"""
        with patch.object(handler, 'get', return_value=mock_response) as mock_get:
            result = handler.diagnosis_barrier_class("class_001", "exam_001")
            assert result == mock_response
            mock_get.assert_called_once_with("/api/diagnosis/barrier/class_001/exam_001")

    def test_diagnosis_barrier_class_params(self, handler, mock_response):
        """测试班级障碍诊断参数"""
        with patch.object(handler, 'get', return_value=mock_response) as mock_get:
            handler.diagnosis_barrier_class("class_001", "exam_001")
            call_args = mock_get.call_args
            assert "class_001" in call_args[0][0]
            assert "exam_001" in call_args[0][0]

    # ===== diagnosis_barrier_student 测试 =====

    def test_diagnosis_barrier_student_success(self, handler, mock_response):
        """测试学生障碍详情查询成功"""
        with patch.object(handler, 'get', return_value=mock_response) as mock_get:
            result = handler.diagnosis_barrier_student("student_001")
            assert result == mock_response
            mock_get.assert_called_once_with("/api/diagnosis/barrier/student_001")

    def test_diagnosis_barrier_student_empty_id(self, handler):
        """测试空学生ID"""
        with pytest.raises(Exception):
            handler.diagnosis_barrier_student("")

    # ===== diagnosis_plan_generate 测试 =====

    def test_diagnosis_plan_generate_success(self, handler, mock_response):
        """测试学习计划生成成功"""
        mock_response["plan_id"] = "plan_001"

        with patch.object(handler, 'post', return_value=mock_response) as mock_post:
            result = handler.diagnosis_plan_generate(
                student_id="student_001",
                barrier_type="concept",
                weak_knowledge_points=["盐类水解", "电离"]
            )
            assert result == mock_response
            mock_post.assert_called_once()

    def test_diagnosis_plan_generate_params(self, handler, mock_response):
        """测试学习计划生成参数"""
        with patch.object(handler, 'post', return_value=mock_response) as mock_post:
            handler.diagnosis_plan_generate(
                student_id="student_001",
                barrier_type="reading",
                weak_knowledge_points=["氧化还原反应"],
                recent_performance={"score": 75}
            )
            call_kwargs = mock_post.call_args[1]
            json_data = call_kwargs['json_data']
            assert json_data['student_id'] == "student_001"
            assert json_data['barrier_type'] == "reading"
            assert json_data['weak_knowledge_points'] == ["氧化还原反应"]
            assert json_data['recent_performance'] == {"score": 75}

    def test_diagnosis_plan_generate_all_barrier_types(self, handler, mock_response):
        """测试所有障碍类型"""
        barrier_types = ["concept", "reading", "expression"]

        with patch.object(handler, 'post', return_value=mock_response) as mock_post:
            for barrier_type in barrier_types:
                handler.diagnosis_plan_generate(
                    student_id="student_001",
                    barrier_type=barrier_type,
                    weak_knowledge_points=["测试知识点"]
                )
                call_kwargs = mock_post.call_args[1]
                assert call_kwargs['json_data']['barrier_type'] == barrier_type

    # ===== diagnosis_config 测试 =====

    def test_diagnosis_config_get_success(self, handler, mock_response):
        """测试获取配置成功"""
        with patch.object(handler, 'get', return_value=mock_response) as mock_get:
            result = handler.diagnosis_config_get("teacher_001")
            assert result == mock_response
            mock_get.assert_called_once_with("/api/diagnosis/config/teacher_001")

    def test_diagnosis_config_update_success(self, handler, mock_response):
        """测试更新配置成功"""
        with patch.object(handler, 'put', return_value=mock_response) as mock_put:
            result = handler.diagnosis_config_update(
                teacher_id="teacher_001",
                concept_threshold=4,
                reading_threshold=3,
                expression_threshold=2
            )
            assert result == mock_response
            call_kwargs = mock_put.call_args[1]
            json_data = call_kwargs['json_data']
            assert json_data['concept_threshold'] == 4
            assert json_data['reading_threshold'] == 3
            assert json_data['expression_threshold'] == 2

    def test_diagnosis_config_update_defaults(self, handler, mock_response):
        """测试更新配置默认值"""
        with patch.object(handler, 'put', return_value=mock_response) as mock_put:
            handler.diagnosis_config_update(teacher_id="teacher_001")
            call_kwargs = mock_put.call_args[1]
            json_data = call_kwargs['json_data']
            assert json_data['concept_threshold'] == 3
            assert json_data['reading_threshold'] == 2
            assert json_data['expression_threshold'] == 3
            assert json_data['mastery_threshold'] == 3

    # ===== diagnosis_plan_apply 测试 =====

    def test_diagnosis_plan_apply_success(self, handler, mock_response):
        """测试应用学习计划成功"""
        with patch.object(handler, 'post', return_value=mock_response) as mock_post:
            plan_data = {"plan_id": "plan_001", "tasks": []}
            result = handler.diagnosis_plan_apply("student_001", plan_data)
            assert result == mock_response
            mock_post.assert_called_once()

    # ===== diagnosis_plan_send_parent 测试 =====

    def test_diagnosis_plan_send_parent_success(self, handler, mock_response):
        """测试发送学习计划给家长成功"""
        with patch.object(handler, 'post', return_value=mock_response) as mock_post:
            result = handler.diagnosis_plan_send_parent("student_001")
            assert result == mock_response
            mock_post.assert_called_once()


class TestDiagnosisToolFunctions:
    """Tool 入口函数测试"""

    def test_diagnosis_barrier_class_function(self):
        """测试 diagnosis_barrier_class 函数"""
        with patch('chem_skills.chemistry_diagnosis.handler.DiagnosisHandler') as MockHandler:
            mock_instance = MockHandler.return_value
            mock_instance.diagnosis_barrier_class.return_value = {"success": True}

            result = diagnosis_barrier_class("class_001", "exam_001")

            mock_instance.diagnosis_barrier_class.assert_called_once_with("class_001", "exam_001")
            assert result["success"] is True

    def test_diagnosis_plan_generate_function(self):
        """测试 diagnosis_plan_generate 函数"""
        with patch('chem_skills.chemistry_diagnosis.handler.DiagnosisHandler') as MockHandler:
            mock_instance = MockHandler.return_value
            mock_instance.diagnosis_plan_generate.return_value = {"success": True, "plan_id": "plan_001"}

            result = diagnosis_plan_generate(
                student_id="student_001",
                barrier_type="concept",
                weak_knowledge_points=["盐类水解"]
            )

            assert result["success"] is True
            assert result["plan_id"] == "plan_001"


class TestDiagnosisEdgeCases:
    """边界情况测试"""

    def test_network_error_handling(self):
        """测试网络错误处理"""
        handler = DiagnosisHandler(base_url="http://localhost:8000")

        with patch.object(handler, 'get', side_effect=Exception("Network error")):
            with pytest.raises(Exception) as exc_info:
                handler.diagnosis_barrier_class("class_001", "exam_001")
            assert "Network error" in str(exc_info.value)

    def test_invalid_response_handling(self):
        """测试无效响应处理"""
        handler = DiagnosisHandler(base_url="http://localhost:8000")

        with patch.object(handler, 'get', return_value={"success": False, "error": "Invalid"}):
            result = handler.diagnosis_config_get("teacher_001")
            assert result["success"] is False
            assert "error" in result

    def test_empty_knowledge_points(self):
        """测试空知识点列表"""
        handler = DiagnosisHandler()

        with patch.object(handler, 'post', return_value={"success": True}) as mock_post:
            handler.diagnosis_plan_generate(
                student_id="student_001",
                barrier_type="concept",
                weak_knowledge_points=[]
            )
            call_kwargs = mock_post.call_args[1]
            assert call_kwargs['json_data']['weak_knowledge_points'] == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

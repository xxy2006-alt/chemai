"""
chemistry-diagnosis Skill Handler
障碍诊断 Skill 的 Tool 实现，调用 ChemAI FastAPI 后端
"""
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from chem_skills._templates.base_handler import BaseSkillHandler  # noqa: E402


class DiagnosisHandler(BaseSkillHandler):
    """障碍诊断 Skill Handler"""

    # ==================== 障碍诊断 ====================

    def diagnosis_barrier_class(
        self, class_id: str, exam_record_id: str
    ) -> Dict[str, Any]:
        """
        对班级所有学生进行障碍类型诊断

        Args:
            class_id: 班级ID
            exam_record_id: 考试记录ID

        Returns:
            BarrierDiagnosisResponse: 包含每个学生的诊断结果和班级分布
        """
        return self.get(
            f"/api/diagnosis/barrier/{class_id}/{exam_record_id}"
        )

    def diagnosis_barrier_student(self, student_id: str) -> Dict[str, Any]:
        """
        获取单个学生的障碍类型详情

        Args:
            student_id: 学生ID

        Returns:
            StudentDiagnosis: 学生诊断详情
        """
        return self.get(f"/api/diagnosis/barrier/{student_id}")

    # ==================== 学习计划 ====================

    def diagnosis_plan_generate(
        self,
        student_id: str,
        barrier_type: str,
        weak_knowledge_points: List[str],
        recent_performance: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        为学生生成个性化学习计划

        Args:
            student_id: 学生ID
            barrier_type: 障碍类型 (concept/reading/expression)
            weak_knowledge_points: 薄弱知识点列表
            recent_performance: 近期表现数据（可选）

        Returns:
            LearningPlanResponse: 生成的学习计划
        """
        return self.post(
            "/api/diagnosis/learning-plan/generate",
            json_data={
                "student_id": student_id,
                "barrier_type": barrier_type,
                "weak_knowledge_points": weak_knowledge_points,
                "recent_performance": recent_performance or {},
            },
        )

    def diagnosis_plan_apply(
        self, student_id: str, plan_data: Dict
    ) -> Dict[str, Any]:
        """
        将生成的学习计划应用到学生

        Args:
            student_id: 学生ID
            plan_data: 学习计划数据

        Returns:
            操作结果
        """
        return self.post(
            f"/api/diagnosis/learning-plan/apply/{student_id}",
            json_data=plan_data,
        )

    def diagnosis_plan_send_parent(
        self, student_id: str, plan_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        发送学生学习计划给家长

        Args:
            student_id: 学生ID
            plan_data: 学习计划数据（可选）

        Returns:
            发送结果
        """
        return self.post(
            f"/api/diagnosis/learning-plan/send-to-parent/{student_id}",
            json_data=plan_data or {},
        )

    # ==================== 配置管理 ====================

    def diagnosis_config_get(self, teacher_id: str) -> Dict[str, Any]:
        """
        获取老师的障碍诊断配置

        Args:
            teacher_id: 教师ID

        Returns:
            BarrierConfigResponse: 诊断配置
        """
        return self.get(f"/api/diagnosis/config/{teacher_id}")

    def diagnosis_config_update(
        self,
        teacher_id: str,
        concept_threshold: int = 3,
        reading_threshold: int = 2,
        expression_threshold: int = 3,
        mastery_threshold: int = 3,
        auto_sync_to_student: bool = False,
    ) -> Dict[str, Any]:
        """
        更新老师的障碍诊断配置

        Args:
            teacher_id: 教师ID
            concept_threshold: 概念理解型触发阈值 (1-5)
            reading_threshold: 审题障碍型触发阈值 (1-5)
            expression_threshold: 表述障碍型触发阈值 (1-5)
            mastery_threshold: 掌握标准阈值 (1-5)
            auto_sync_to_student: 是否自动同步到学生端

        Returns:
            BarrierConfigResponse: 更新后的配置
        """
        return self.put(
            f"/api/diagnosis/config/{teacher_id}",
            json_data={
                "concept_threshold": concept_threshold,
                "reading_threshold": reading_threshold,
                "expression_threshold": expression_threshold,
                "mastery_threshold": mastery_threshold,
                "auto_sync_to_student": auto_sync_to_student,
            },
        )


# ==================== Tool 入口函数 ====================
# ChemAI Agent 调用入口


def diagnosis_barrier_class(class_id: str, exam_record_id: str) -> Dict:
    """Tool: 对班级所有学生进行障碍类型诊断"""
    handler = DiagnosisHandler()
    return handler.diagnosis_barrier_class(class_id, exam_record_id)


def diagnosis_barrier_student(student_id: str) -> Dict:
    """Tool: 获取单个学生的障碍类型详情"""
    handler = DiagnosisHandler()
    return handler.diagnosis_barrier_student(student_id)


def diagnosis_plan_generate(
    student_id: str,
    barrier_type: str,
    weak_knowledge_points: List[str],
    recent_performance: Optional[Dict] = None,
) -> Dict:
    """Tool: 为学生生成个性化学习计划"""
    handler = DiagnosisHandler()
    return handler.diagnosis_plan_generate(
        student_id, barrier_type, weak_knowledge_points, recent_performance
    )


def diagnosis_plan_apply(student_id: str, plan_data: Dict) -> Dict:
    """Tool: 将学习计划应用到学生"""
    handler = DiagnosisHandler()
    return handler.diagnosis_plan_apply(student_id, plan_data)


def diagnosis_plan_send_parent(
    student_id: str, plan_data: Optional[Dict] = None
) -> Dict:
    """Tool: 发送学习计划给家长"""
    handler = DiagnosisHandler()
    return handler.diagnosis_plan_send_parent(student_id, plan_data)


def diagnosis_config_get(teacher_id: str) -> Dict:
    """Tool: 获取诊断配置"""
    handler = DiagnosisHandler()
    return handler.diagnosis_config_get(teacher_id)


def diagnosis_config_update(
    teacher_id: str,
    concept_threshold: int = 3,
    reading_threshold: int = 2,
    expression_threshold: int = 3,
    mastery_threshold: int = 3,
    auto_sync_to_student: bool = False,
) -> Dict:
    """Tool: 更新诊断配置"""
    handler = DiagnosisHandler()
    return handler.diagnosis_config_update(
        teacher_id,
        concept_threshold,
        reading_threshold,
        expression_threshold,
        mastery_threshold,
        auto_sync_to_student,
    )


# ==================== 主入口 ====================

if __name__ == "__main__":
    def test():
        handler = DiagnosisHandler()
        result = handler.diagnosis_config_get("test_teacher")
        print(result)

    test()

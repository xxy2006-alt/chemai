"""
chemistry-diagnosis Skill 数据模型
定义 Tool 输入输出数据结构
"""
from pydantic import BaseModel
from typing import List, Optional, Dict


class StudentDiagnosis(BaseModel):
    """学生障碍诊断结果"""
    student_id: str
    student_name: str
    barrier_type: Dict[str, float]  # {concept: 0.3, reading: 0.5, expression: 0.2}
    dominant_barrier: str
    weak_knowledge_points: List[str]
    recommended_intervention: str
    last_updated: str


class BarrierDiagnosisResponse(BaseModel):
    """障碍诊断响应"""
    class_id: str
    exam_record_id: str
    students: List[StudentDiagnosis]
    class_barrier_distribution: Dict[str, int]
    avg_mastery: float


class BarrierConfigRequest(BaseModel):
    """障碍诊断配置请求"""
    concept_threshold: int = 3
    reading_threshold: int = 2
    expression_threshold: int = 3
    mastery_threshold: int = 3
    auto_sync_to_student: bool = False


class LearningPlanRequest(BaseModel):
    """生成学习计划请求"""
    student_id: str
    barrier_type: str
    weak_knowledge_points: List[str]
    recent_performance: Optional[Dict] = None


class LearningPlanResponse(BaseModel):
    """学习计划响应"""
    student_id: str
    student_name: str
    plan: Dict
    generated_at: str


class BarrierConfigResponse(BaseModel):
    """障碍诊断配置响应"""
    teacher_id: str
    concept_threshold: int
    reading_threshold: int
    expression_threshold: int
    mastery_threshold: int
    auto_sync_to_student: bool

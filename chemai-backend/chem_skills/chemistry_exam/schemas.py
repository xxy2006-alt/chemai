"""
chemistry-exam Skill 数据模型
定义 Tool 输入输出数据结构
"""
from pydantic import BaseModel
from typing import List, Optional, Literal


class QuestionGenerateRequest(BaseModel):
    """AI出题请求"""
    exam_type: str = "单元练习"
    knowledge_points: List[str]
    difficulty: Literal["easy", "medium", "hard", "competition"] = "medium"
    quantity: int = 10


class AuditResult(BaseModel):
    """单个审核结果"""
    dimension: str
    status: Literal["passed", "warning", "blocked"]
    message: str
    detail: Optional[str] = None


class AuditReport(BaseModel):
    """四维安全审核报告"""
    question_id: str
    content: str
    options: Optional[List[str]] = None
    answer: str
    knowledge_points: List[str]
    difficulty: str
    coefficient_audit: AuditResult
    condition_audit: AuditResult
    product_audit: AuditResult
    structure_audit: AuditResult
    overall_status: Literal["passed", "warning", "blocked"]
    trap_hints: List[str] = []
    historical_matches: List[dict] = []
    is_from_rag: bool = False
    source_question_id: Optional[str] = None
    source_question_preview: Optional[str] = None
    similarity: Optional[float] = None
    match_method: Optional[Literal["vector", "simple"]] = None


class QuestionGenerateResponse(BaseModel):
    """AI出题响应"""
    success: bool
    questions: List[AuditReport]
    generate_time_ms: int
    total_cost: float


class HistoricalQuestion(BaseModel):
    """历年真题"""
    exam_id: str
    source: str
    year: int
    question_number: str
    content: str
    options: Optional[List[str]] = None
    answer: str
    knowledge_points: List[str]
    difficulty: str
    discrimination: float


class SimilarQuestionRequest(BaseModel):
    """查找相似题目请求"""
    knowledge_points: List[str]
    difficulty: str = "medium"
    limit: int = 5


class TeacherImportRequest(BaseModel):
    """老师导入题目请求"""
    source_name: str
    region: str = "老师导入"
    year: int
    questions: List[dict]

"""
chemistry-improvement Data Models
自改进系统数据模型
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum


class RejectionReason(Enum):
    """拒绝原因枚举"""
    EQUATION_IMBALANCE = "equation_imbalance"
    WRONG_KNOWLEDGE_POINT = "wrong_knowledge_point"
    DIFFICULTY_MISMATCH = "difficulty_mismatch"
    CONTENT_INCORRECT = "content_incorrect"
    OFF_TOPIC = "off_topic"
    OPTIONS_AMBIGUOUS = "options_ambiguous"
    OTHER = "other"


class ReviewStatus(Enum):
    """审核状态"""
    APPROVED = "approved"
    MODIFIED = "modified"
    REJECTED = "rejected"


@dataclass
class QuestionQualityMetrics:
    """题目质量指标"""
    question_id: str
    knowledge_points: List[str]
    difficulty: str

    # 审核阶段
    review_status: str  # approved / modified / rejected
    rejection_reasons: List[str] = field(default_factory=list)
    teacher_modifications: Optional[str] = None

    # 作答阶段
    total_attempts: int = 0
    correct_count: int = 0
    accuracy_rate: float = 0.0

    # 学习效果
    avg_pre_score: float = 0.0
    avg_post_score: float = 0.0
    learning_lift: float = 0.0

    # 元数据
    generated_at: datetime = field(default_factory=datetime.now)
    first_used_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None


@dataclass
class StrategyMetrics:
    """策略质量指标"""
    strategy_id: str
    strategy_type: str  # prompt_template / difficulty_model / kp_combination

    # 应用统计
    times_applied: int = 0
    approval_rate: float = 0.0
    avg_learning_lift: float = 0.0

    # 趋势
    recent_approval_rate: float = 0.0
    trend: str = "stable"  # improving / declining / stable

    # 置信度
    confidence: float = 0.0
    sample_size: int = 0


@dataclass
class LearningInsight:
    """学习洞察"""
    insight_id: str
    category: str  # difficulty / kp_combination / question_style / etc
    title: str
    description: str
    evidence: Dict
    confidence: float  # 置信度 0-1
    recommended_action: str
    auto_applied: bool = False
    teacher_approved: Optional[bool] = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class PromptVersion:
    """Prompt 版本"""
    version_id: str
    prompt_type: str  # question_generation / question_audit / etc
    content: str
    change_reason: str
    change_source: str  # manual / auto_improvement
    created_by: str  # teacher_id / "auto_agent"
    metrics_at_change: Dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class KPCombinationMetrics:
    """知识点组合指标"""
    kp_combination: tuple  # 排序的知识点的元组
    times_used: int = 0
    avg_learning_lift: float = 0.0
    approval_rate: float = 0.0
    student_satisfaction: float = 0.0
    effectiveness_score: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "kp_combination": list(self.kp_combination),
            "times_used": self.times_used,
            "avg_learning_lift": self.avg_learning_lift,
            "approval_rate": self.approval_rate,
            "student_satisfaction": self.student_satisfaction,
            "effectiveness_score": self.effectiveness_score
        }


@dataclass
class StrategyAdjustment:
    """策略调整"""
    adjustment_id: str
    strategy_type: str
    adjustment_type: str
    old_value: any
    new_value: any
    trigger_reason: str
    applied_at: datetime = field(default_factory=datetime.now)
    applied_by: str = "auto_agent"
    approved_by: Optional[str] = None
    status: str = "pending"  # pending / applied / rejected


@dataclass
class AnalysisResult:
    """分析结果"""
    analysis_type: str
    insights: List[LearningInsight]
    metrics_summary: Dict
    recommended_actions: List[str]

"""
复习任务模型
基于艾宾浩斯遗忘曲线的间隔重复复习
"""

from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.models.database import Base


class ReviewTask(Base):
    """复习任务表"""
    __tablename__ = "review_tasks"

    task_id = Column(String(64), primary_key=True)
    student_id = Column(String(64), ForeignKey("students.student_id"), nullable=False)
    question_id = Column(String(64), ForeignKey("questions.question_id"), nullable=False)

    # 艾宾浩斯复习节点
    # 0=首次学习, 1=1天后, 2=3天后, 3=7天后, 4=14天后, 5=30天后
    review_level = Column(Integer, default=0)

    # 复习状态
    status = Column(String(32), default="pending")  # pending/done/overdue

    # 首次学习时间
    first_review_at = Column(DateTime, nullable=True)

    # 下次复习时间
    next_review_at = Column(DateTime, nullable=True)

    # 实际完成时间
    completed_at = Column(DateTime, nullable=True)

    # 连续正确次数
    consecutive_correct = Column(Integer, default=0)

    # 连续错误次数
    consecutive_errors = Column(Integer, default=0)

    # 复习历史（JSON数组）
    review_history = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    student = relationship("Student")
    question = relationship("Question")


# 艾宾浩斯复习节点天数
SPIRAL_REVIEW_DAYS = {
    0: 1,    # 第0次复习后，下次1天
    1: 3,    # 第1次复习后，下次3天
    2: 7,    # 第2次复习后，下次7天
    3: 14,   # 第3次复习后，下次14天
    4: 30,   # 第4次复习后，下次30天
    5: None  # 第5次复习后，认为已掌握，不再安排
}


def calculate_next_review_date(current_level: int) -> datetime:
    """根据当前复习级别计算下次复习日期"""
    days = SPIRAL_REVIEW_DAYS.get(current_level)
    if days is None:
        return None  # 已掌握
    from datetime import timedelta
    return datetime.utcnow() + timedelta(days=days)

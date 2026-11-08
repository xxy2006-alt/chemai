"""
预警日志模型
记录学生学情异常预警
"""

from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from app.models.database import Base


class WarningLog(Base):
    """预警日志表"""
    __tablename__ = "warning_logs"

    warning_id = Column(String(64), primary_key=True)
    student_id = Column(String(64), ForeignKey("students.student_id"), nullable=False)

    # 预警类型
    warning_type = Column(String(32), nullable=False)
    # no_login: 连续未登录
    # score_drop: 成绩下滑
    # high_error_rate: 错题率过高
    # new_barrier: 新障碍类型出现

    # 预警级别
    level = Column(String(32), default="info")  # info/warning/critical

    # 预警内容
    title = Column(String(256), nullable=False)
    content = Column(Text, nullable=True)

    # 预警数据（JSON）
    data = Column(JSON, nullable=True)

    # 处理状态
    status = Column(String(32), default="pending")  # pending/processed/ignored

    # 处理信息
    processed_by = Column(String(64), nullable=True)
    processed_at = Column(DateTime, nullable=True)
    processed_note = Column(Text, nullable=True)

    # 通知状态
    notified_teacher = Column(Boolean, default=False)
    notified_parent = Column(Boolean, default=False)
    notified_student = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    student = relationship("Student")


# 预警类型名称映射
WARNING_TYPE_NAMES = {
    "no_login": "连续未登录",
    "score_drop": "成绩下滑",
    "high_error_rate": "错题率过高",
    "new_barrier": "新障碍出现"
}

# 预警级别名称映射
WARNING_LEVEL_NAMES = {
    "info": "提示",
    "warning": "警告",
    "critical": "紧急"
}

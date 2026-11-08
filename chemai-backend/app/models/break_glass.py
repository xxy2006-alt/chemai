"""break-glass 提权会话 —— ADR-0011。

`super_admin` 的默认数据范围是**空集**；跨校排查要走临时提权：限时、留痕、用完即掉。
一张表记录每次提权，`expires_at` 到点自动失效（读的时候判，不需要定时任务）。

为什么不是「超管常驻跨校」：常驻权限一旦泄露，最坏情况是全平台数据泄露且事后无法
界定范围；低频的跨校需求用限时窗口就够（ADR-0011）。
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text

from app.models.database import Base


class BreakGlassSession(Base):
    __tablename__ = "break_glass_sessions"

    session_id = Column(String(64), primary_key=True)
    user_id = Column(String(64), nullable=False, index=True)
    reason = Column(Text, nullable=False)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    # 提前结束时写这里；到点自然失效的不写（靠 expires_at 判）
    ended_at = Column(DateTime, nullable=True)

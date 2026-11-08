"""break-glass 提权判定 —— ADR-0011。

`RequestScope` 与提权端点共用这里的「有没有生效中的提权」判定，避免两处各写一套。

**判定在读的时候做**（`expires_at` 到点即失效），不需要定时任务清理 ——
服务重启、时钟跳过都不会让权限残留。
"""
from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.break_glass import BreakGlassSession

# 单次提权的时长上限（分钟）。低频排查用，不该开着过夜。
DEFAULT_MINUTES = 15
MAX_MINUTES = 60


def active_session(db: Session, user_id: str, now: Optional[datetime] = None) -> Optional[BreakGlassSession]:
    """该用户当前生效中的提权会话；没有则 None。

    生效 = 未提前结束 且 未过期。取**最新一条**（同一人可以多次提权）。
    """
    if not db or not user_id:
        return None
    now = now or datetime.utcnow()
    return (
        db.query(BreakGlassSession)
        .filter(
            BreakGlassSession.user_id == user_id,
            BreakGlassSession.ended_at.is_(None),
            BreakGlassSession.expires_at > now,
        )
        .order_by(BreakGlassSession.started_at.desc())
        .first()
    )


def start_session(db: Session, user_id: str, reason: str, minutes: int = DEFAULT_MINUTES) -> BreakGlassSession:
    """开启一次提权。时长夹在 [1, MAX_MINUTES] —— 超上限不报错，直接截断。"""
    minutes = max(1, min(int(minutes or DEFAULT_MINUTES), MAX_MINUTES))
    now = datetime.utcnow()
    session = BreakGlassSession(
        session_id=f"bg_{uuid4().hex[:16]}",
        user_id=user_id,
        reason=(reason or "").strip(),
        started_at=now,
        expires_at=now + timedelta(minutes=minutes),
    )
    db.add(session)
    db.commit()
    return session


def end_session(db: Session, session: BreakGlassSession) -> None:
    """提前结束。到点自然失效的不需要调这个。"""
    session.ended_at = datetime.utcnow()
    db.commit()

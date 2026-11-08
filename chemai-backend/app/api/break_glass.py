"""break-glass 提权端点 —— ADR-0011。

`super_admin` 的跨校访问**不是常驻权限**：默认数据范围为空，需要排查时在这里开一次
限时提权，用完即掉，全程留审计。

- `POST /api/break-glass`        开启（要写明理由；时长夹在 1~60 分钟）
- `GET  /api/break-glass/active` 查当前生效中的提权
- `DELETE /api/break-glass`      提前结束

审计写在 `operation_logs`：`action="break_glass_start" / "break_glass_end"`，
`detail` 里带理由与到期时间 —— 「谁在什么时候、为什么、开了多久」都查得到。
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.middleware.auth import PermissionChecker
from app.middleware.break_glass import (
    MAX_MINUTES, active_session, end_session, start_session,
)
from app.models.database import OperationLog, get_db

router = APIRouter()


class BreakGlassRequest(BaseModel):
    reason: str
    minutes: int = 15


def _audit(db: Session, user_id: str, action: str, session, ip: Optional[str] = None) -> None:
    """把提权写进操作日志。**审计失败不能让提权本身失败** —— 但也不能静默：
    这条流水是 ADR-0011 里「全程留痕」的落点，所以失败要冒出来（由调用方决定）。
    """
    db.add(OperationLog(
        user_id=user_id,
        action=action,
        target_type="break_glass",
        target_id=session.session_id,
        detail={
            "reason": session.reason,
            "started_at": session.started_at.isoformat(),
            "expires_at": session.expires_at.isoformat(),
            "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        },
        ip_address=ip,
    ))
    db.commit()


def _serialize(s) -> dict:
    return {
        "session_id": s.session_id,
        "user_id": s.user_id,
        "reason": s.reason,
        "started_at": s.started_at.isoformat(),
        "expires_at": s.expires_at.isoformat(),
        "ended_at": s.ended_at.isoformat() if s.ended_at else None,
        "remaining_seconds": max(0, int((s.expires_at - datetime.utcnow()).total_seconds())),
    }


@router.post("")
async def create_break_glass(
    request: BreakGlassRequest,
    http_request: Request,
    current_user: dict = Depends(PermissionChecker("break_glass", "create")),
    db: Session = Depends(get_db),
):
    """开启一次限时提权。**必须写明理由** —— 没理由的提权事后等于没留痕。"""
    reason = (request.reason or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="必须填写提权理由")
    if request.minutes > MAX_MINUTES:
        raise HTTPException(status_code=400, detail=f"单次提权最长 {MAX_MINUTES} 分钟")

    existing = active_session(db, current_user["user_id"])
    if existing:
        # 不叠开：同一时刻只保留一条生效中的提权，免得「还开着哪一条」说不清
        return {"success": True, "message": "已有生效中的提权", "session": _serialize(existing)}

    session = start_session(db, current_user["user_id"], reason, request.minutes)
    _audit(db, current_user["user_id"], "break_glass_start", session,
           http_request.client.host if http_request.client else None)
    return {"success": True, "session": _serialize(session)}


@router.get("/active")
async def get_active_break_glass(
    current_user: dict = Depends(PermissionChecker("break_glass", "read")),
    db: Session = Depends(get_db),
):
    """当前生效中的提权（没有则 `session: null`）。用于验证「到点自动失效」。"""
    session = active_session(db, current_user["user_id"])
    return {"success": True, "session": _serialize(session) if session else None}


@router.delete("")
async def revoke_break_glass(
    http_request: Request,
    current_user: dict = Depends(PermissionChecker("break_glass", "delete")),
    db: Session = Depends(get_db),
):
    """提前结束提权 —— 用完即掉，不等它自己过期。"""
    session = active_session(db, current_user["user_id"])
    if not session:
        return {"success": True, "message": "当前没有生效中的提权", "session": None}

    end_session(db, session)
    _audit(db, current_user["user_id"], "break_glass_end", session,
           http_request.client.host if http_request.client else None)
    return {"success": True, "session": _serialize(session)}

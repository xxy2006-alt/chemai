"""
P0-1: 通知服务 API
提供三端消息推送、通知管理功能
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.database import get_db, Student, Parent, ParentNotification
from app.services.notification_service import notification_service
from app.api.parent import get_current_parent_id
from app.middleware.auth import PermissionChecker
from app.middleware.scope import RequestScope, ScopeGuard

router = APIRouter()


class NotificationSendRequest(BaseModel):
    """发送通知请求"""
    type: str  # daily_report/weekly_report/score_alert/warning/reminder
    title: str
    content: str
    target_type: str  # student/parent
    target_ids: Optional[List[str]] = None  # 收件人ID列表；必填（本端点不做全量广播）
    priority: str = "normal"  # normal/high/immediate
    channel: str = "in_app"  # in_app/sms/email/telegram
    idempotency_key: Optional[str] = None  # 同一事件重复投递只落一条


class NotificationResponse(BaseModel):
    """通知响应"""
    notification_id: str
    success: bool
    message: str
    sent_count: int = 0
    failed_count: int = 0


class NotificationRecord(BaseModel):
    """通知记录"""
    notification_id: str
    type: str
    title: str
    content: str
    target_type: str
    target_count: int
    sent_count: int
    failed_count: int
    status: str
    created_at: str
    sent_at: Optional[str] = None


@router.post("/send")
async def send_notification(
    request: NotificationSendRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(PermissionChecker("notification", "create")),
):
    """发送通知给指定用户群体（统一分发入口：站内收件箱 + 可选外发网关）"""
    role_map = {"student": "student", "parent": "parent"}
    role = role_map.get(request.target_type)
    if not role:
        raise HTTPException(status_code=400, detail=f"不支持的 target_type: {request.target_type}")
    if not request.target_ids:
        # 不收件人 = 空操作，不能回 200 让调用方以为已发送（本端点不做全量广播）
        raise HTTPException(status_code=400, detail="target_ids 不能为空")

    # 收件人必须落在调用者数据范围内（否则任课教师可给外校学生落任意通知）
    scope = RequestScope.from_user(current_user, db)
    parent_student = {}
    if role == "student":
        allowed = {rid for rid in request.target_ids if scope.allows_student(rid)}
    else:
        visible_students = scope.student_ids()
        from app.models.database import StudentParentBinding
        rows = db.query(StudentParentBinding.parent_id, StudentParentBinding.student_id).filter(
            StudentParentBinding.student_id.in_(visible_students),
            StudentParentBinding.status == "active",
        ).all() if visible_students else []
        for pid, sid in rows:
            parent_student.setdefault(pid, sid)
        allowed = set(parent_student)
    denied = [rid for rid in request.target_ids if rid not in allowed]
    if denied:
        raise HTTPException(status_code=403, detail=f"无权向这些收件人发送通知: {denied}")

    sent = 0
    for rid in request.target_ids:
        recipient = {"role": role, "id": rid}
        if role == "parent":
            # 家长通知必须挂到具体学生（student_id 是 NOT NULL 外键）
            recipient["student_id"] = parent_student[rid]
        out = notification_service.dispatch(
            recipient=recipient,
            event={"type": request.type, "title": request.title, "content": request.content},
            idempotency_key=request.idempotency_key,
        )
        sent += 0 if out.get("duplicate") else 1
    return {"success": True, "sent_count": sent, "failed_count": 0,
            "message": f"已分发给 {sent} 位收件人"}


@router.post("/send-to-student/{student_id}")
async def send_to_student(
    student_id: str,
    notification_type: str,
    title: str,
    content: str,
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("notification", "create")),
    _scope: None = Depends(ScopeGuard("student_id", kind="student")),
):
    """发送通知给单个学生（站内收件箱）"""
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    out = notification_service.dispatch(
        recipient={"role": "student", "id": student_id},
        event={"type": notification_type, "title": title, "content": content},
    )
    return {"success": True, "notification_id": out["notification_id"],
            "sent_count": 0 if out.get("duplicate") else 1}


@router.post("/send-to-parent/{student_id}")
async def send_to_parent(
    student_id: str,
    notification_type: str,
    title: str,
    content: str,
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("notification", "create")),
    _scope: None = Depends(ScopeGuard("student_id", kind="student")),
):
    """发送通知给学生家长（自动查找该学生绑定的全部家长）"""
    from app.models.database import StudentParentBinding

    bindings = db.query(StudentParentBinding).filter(
        StudentParentBinding.student_id == student_id,
        StudentParentBinding.status == "active",
    ).all()
    if not bindings:
        return {"success": False, "message": "该学生未绑定家长", "sent_count": 0}

    sent = 0
    for b in bindings:
        out = notification_service.dispatch(
            recipient={"role": "parent", "id": b.parent_id, "student_id": student_id},
            event={"type": notification_type, "title": title, "content": content},
        )
        sent += 0 if out.get("duplicate") else 1
    return {"success": True, "sent_count": sent}


@router.post("/send-to-class/{class_id}")
async def send_to_class(
    class_id: str,
    notification_type: str,
    title: str,
    content: str,
    target: str = "students",  # students/parents
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("notification", "create")),
    _scope: None = Depends(ScopeGuard("class_id", kind="class")),
):
    """发送通知给整个班级（students → 学生收件箱；parents → 各生绑定的家长）"""
    from app.models.database import StudentParentBinding

    students = db.query(Student).filter(Student.class_id == class_id).all()
    if not students:
        return {"success": False, "message": "班级无学生", "sent_count": 0}

    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    sent = 0
    if target == "parents":
        seen = set()
        for st in students:
            for b in db.query(StudentParentBinding).filter(
                StudentParentBinding.student_id == st.student_id,
                StudentParentBinding.status == "active",
            ).all():
                if b.parent_id in seen:
                    continue
                seen.add(b.parent_id)
                out = notification_service.dispatch(
                    recipient={"role": "parent", "id": b.parent_id, "student_id": st.student_id},
                    event={"type": notification_type, "title": title, "content": content},
                )
                sent += 0 if out.get("duplicate") else 1
    else:
        for st in students:
            out = notification_service.dispatch(
                recipient={"role": "student", "id": st.student_id},
                event={"type": notification_type, "title": title, "content": content},
                idempotency_key=f"class_{class_id}_{stamp}_{notification_type}",
            )
            sent += 0 if out.get("duplicate") else 1
    return {"success": True, "sent_count": sent, "message": f"已分发 {sent} 条通知"}


@router.get("/history")
async def get_notification_history(
    target_type: Optional[str] = None,
    notification_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("notification", "read")),
):
    """
    获取通知发送历史
    """
    # TODO: 从数据库查询通知历史
    # 目前返回空列表占位
    return {
        "success": True,
        "total": 0,
        "offset": offset,
        "limit": limit,
        "notifications": []
    }


@router.get("/student/{student_id}/notifications")
async def get_student_notifications(
    student_id: str,
    unread_only: bool = False,
    limit: int = 20,
    db: Session = Depends(get_db),
    # allow_self：学生读自己的通知（ADR-0008 本人角色不走矩阵），
    # 由 ScopeGuard 收窄到「本人」；员工角色仍要 notification:read。
    _perm: None = Depends(PermissionChecker("notification", "read", allow_self=True)),
    _scope: None = Depends(ScopeGuard("student_id", kind="student")),
):
    """
    获取学生的通知列表（Student Inbox）
    """
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    # 学生收件箱（ADR-0013）：Notification Dispatch 的应用内 adapter 落库于此，
    # 学习计划发送等业务事件经 service 写入（幂等键在 notification_id 上）
    # 合并说明：查询下沉到 service（其返回形状与原先这段内联代码一致：
    # 无 payload、sent_at 为 "%Y-%m-%d %H:%M"）。
    notifications = notification_service.student_notifications(
        student_id, unread_only=unread_only, limit=limit, db=db)
    unread_count = notification_service.unread_count(student_id, db=db)

    return {
        "success": True,
        "student_id": student_id,
        "total": len(notifications),
        "unread_count": unread_count,
        "notifications": notifications,
    }


@router.post("/student/{student_id}/read")
async def mark_student_notifications_read(
    student_id: str,
    notification_ids: Optional[List[str]] = Body(None, embed=True),
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("notification", "update", allow_self=True)),
    _scope: None = Depends(ScopeGuard("student_id", kind="student")),
):
    """标记学生通知已读（本人；notification_ids 为空 = 全部）"""
    updated = notification_service.mark_read(student_id, notification_ids, db=db)
    return {"success": True, "student_id": student_id, "marked": updated}


@router.get("/parent/{parent_id}/notifications")
async def get_parent_notifications(
    parent_id: str,
    unread_only: bool = False,
    limit: int = 20,
    db: Session = Depends(get_db),
    token_parent_id: str = Depends(get_current_parent_id),
):
    """
    获取家长的通知列表
    校验 token 中的家长身份，禁止通过路径伪造他人 parent_id
    """
    if token_parent_id != parent_id:
        raise HTTPException(status_code=403, detail="无权查看该家长的通知")

    parent = db.query(Parent).filter(Parent.parent_id == parent_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail="家长不存在")

    query = db.query(ParentNotification).filter(ParentNotification.parent_id == parent_id)
    if unread_only:
        query = query.filter(ParentNotification.is_read.is_(False))
    notifications = query.order_by(ParentNotification.created_at.desc()).limit(limit).all()

    result = []
    for n in notifications:
        student = db.query(Student).filter(Student.student_id == n.student_id).first()
        result.append({
            "notification_id": n.notification_id,
            "student_id": n.student_id,
            "student_name": student.name if student else "未知",
            "type": n.type,
            "title": n.title,
            "content": n.content,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat() if n.created_at else "",
        })

    unread_count = db.query(ParentNotification).filter(
        ParentNotification.parent_id == parent_id,
        ParentNotification.is_read.is_(False)
    ).count()

    return {
        "success": True,
        "parent_id": parent_id,
        "total": len(result),
        "unread_count": unread_count,
        "notifications": result,
    }


@router.put("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    user_id: str,
    user_type: str,  # student/parent
    db: Session = Depends(get_db),
    current_user: dict = Depends(PermissionChecker("notification", "update", allow_self=True)),
):
    """标记通知为已读（本人通知；员工需 notification:update 且不得改他人）"""
    # 本人角色只许动自己的：token 身份即 user_id（ADR-0008 身份即范围）
    if current_user["role"] in ("student", "parent") and current_user["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="只能标记自己的通知")
    if user_type not in ("student", "parent"):
        raise HTTPException(status_code=400, detail="user_type 须为 student/parent")

    # 员工同样按数据范围收窄：user_id 是调用方自报的，不能整个交出去
    if current_user["role"] not in ("student", "parent"):
        scope = RequestScope.from_user(current_user, db)
        if user_type == "parent":
            from app.models.database import StudentParentBinding
            visible_students = scope.student_ids()
            allowed = bool(visible_students) and db.query(StudentParentBinding).filter(
                StudentParentBinding.parent_id == user_id,
                StudentParentBinding.student_id.in_(visible_students),
                StudentParentBinding.status == "active",
            ).first() is not None
        else:
            allowed = scope.allows_student(user_id)
        if not allowed:
            # 404 而非 403：不向调用者泄漏「该通知存在但不在你的范围内」
            raise HTTPException(status_code=404, detail="通知不存在")

    out = notification_service.mark_single_read(notification_id, user_id, user_type, db)
    if not out["ok"]:
        # 404 而非 403：不向调用者泄漏「该通知存在但属于别人」
        raise HTTPException(status_code=404, detail="通知不存在")
    return {"success": True, "notification_id": notification_id, "message": "已标记为已读"}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("notification", "delete")),
):
    """
    删除通知
    """
    # TODO: 从数据库删除通知
    return {
        "success": True,
        "notification_id": notification_id,
        "message": "通知已删除"
    }


@router.get("/channels")
async def get_available_channels(
    _perm: None = Depends(PermissionChecker("notification", "read")),
):
    """
    获取可用的通知渠道
    """
    return {
        "success": True,
        "channels": [
            {"id": "in_app", "name": "端内通知", "enabled": True},
            {"id": "telegram", "name": "Telegram", "enabled": True},
            {"id": "email", "name": "邮件", "enabled": False},
            {"id": "sms", "name": "短信", "enabled": False}
        ]
    }


@router.post("/test-telegram")
async def test_telegram_channel(
    chat_id: str,
    message: str = "ChemAI测试消息",
    _perm: None = Depends(PermissionChecker("notification", "create")),
):
    """
    测试Telegram渠道
    """
    result = notification_service.send_telegram(chat_id, message)
    return result


@router.post("/subscribe")
async def subscribe_notification_channel(
    user_id: str,
    user_type: str,
    channel: str,
    channel_id: str,  # telegram_chat_id / email / phone
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("notification", "update")),
):
    """
    订阅通知渠道（如绑定Telegram机器人）
    """
    # TODO: 保存订阅信息到数据库
    return {
        "success": True,
        "message": f"已成功订阅{channel}通知",
        "user_id": user_id,
        "channel": channel,
        "channel_id": channel_id
    }


@router.delete("/unsubscribe")
async def unsubscribe_notification_channel(
    user_id: str,
    user_type: str,
    channel: str,
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("notification", "update")),
):
    """
    取消订阅通知渠道
    """
    # TODO: 从数据库删除订阅信息
    return {
        "success": True,
        "message": f"已取消{channel}通知订阅"
    }

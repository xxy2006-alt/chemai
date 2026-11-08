"""
通知服务
处理APP内通知（家长端消息、学生端消息）
"""

import hashlib
import logging
from datetime import datetime
from typing import Optional
from app.models.database import (
    Student, StudentParentBinding, ParentNotification, StudentNotification,
    get_db
)

logger = logging.getLogger(__name__)


def _dedup_notification_id(prefix: str, idempotency_key: str, parent_id: str) -> str:
    """由幂等键派生确定性通知 ID（≤64 字符），同一事件重复投递得到同一 ID。"""
    digest = hashlib.sha1(f"{idempotency_key}:{parent_id}".encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def _batch_notification_id(db, prefix: str, idempotency_key, parent_id: str, fallback_id: str):
    """批处理通知的幂等 ID 解析：幂等键命中已存在通知返回 None（跳过），否则返回待写入 ID。"""
    if idempotency_key is None:
        return fallback_id
    notification_id = _dedup_notification_id(prefix, idempotency_key, parent_id)
    exists = db.query(ParentNotification).filter(
        ParentNotification.notification_id == notification_id
    ).first()
    return None if exists is not None else notification_id


class NotificationService:
    """通知服务类"""

    @staticmethod
    def dispatch(recipient: dict, event: dict, idempotency_key: Optional[str] = None,
                 db=None) -> dict:
        """统一分发入口：业务事件 → 收件人站内收件箱（默认动作）+ 可选外发网关。

        recipient: {"role": "student"|"parent", "id": ...}
        event:     {"type": assignment|grading|weekly|warning, "title", "content"?, "payload"?}
        幂等：提供 idempotency_key 时同一事件重复投递只落一条（至少一次投递契约）。
        db: 调用方会话（路由传入；省略时自开，供 service 间调用）。
        """
        role = recipient.get("role")
        rid = recipient.get("id")
        etype = event.get("type", "notice")
        title = event.get("title", "")
        content = event.get("content")

        db_gen = None if db is not None else get_db()
        db = db if db is not None else next(db_gen)
        try:
            duplicate = False
            if idempotency_key is not None:
                # 幂等键是「事件×收件人」复合——广播给全班时同一事件键对每人各存一份。
                # 先按完整复合键派生 ID：整体截断会把「:收件人」切掉，两个收件人撞成一条
                composite = f"{idempotency_key}:{rid}"
                digest = hashlib.sha1(composite.encode("utf-8")).hexdigest()[:12]
                notification_id = f"sn_{digest}"
                dup_model = ParentNotification if role == "parent" else StudentNotification
                duplicate = db.query(dup_model).filter(
                    dup_model.notification_id == notification_id).first() is not None
            else:
                import uuid
                notification_id = f"sn_{rid}_{uuid.uuid4().hex[:8]}"  # 无键显式发送：允许重复，ID 防撞

            external = False
            if not duplicate:
                # 网关外发在去重判定之后：重放事件不重复外发
                from app.core.config import settings
                if getattr(settings, "NOTIFY_EXTERNAL_GATEWAYS", False):
                    try:
                        external = _gateway_send(event, recipient)
                    except Exception as e:  # 外发失败不阻断站内落库
                        logger.warning("notification gateway send failed: %s", e)

                if role == "parent":
                    db.add(ParentNotification(
                        notification_id=notification_id,
                        parent_id=rid,
                        student_id=recipient.get("student_id", ""),
                        type=etype,
                        title=title[:256],
                        content=content,
                        is_read=False,
                        sent_at=datetime.utcnow(),
                    ))
                else:
                    # 幂等靠上面的派生 notification_id（唯一索引），不写幂等键列 ——
                    # 表结构与真实库一致：id/notification_id/student_id/type/title/
                    # content/is_read/sent_at（合并说明，2026-09-14）
                    db.add(StudentNotification(
                        notification_id=notification_id,
                        student_id=rid,
                        type=etype,
                        title=title[:256],
                        content=content,
                        is_read=False,
                        sent_at=datetime.utcnow(),
                    ))
                db.commit()
            return {"notification_id": notification_id, "channel": "in_app",
                    "external": external, "duplicate": duplicate}
        finally:
            if db_gen is not None:
                db.close()

    @staticmethod
    def student_notifications(student_id: str, unread_only: bool = False, limit: int = 20,
                              db=None) -> list:
        """学生收件箱列表（本人）。"""
        db_gen = None if db is not None else get_db()
        db = db if db is not None else next(db_gen)
        try:
            q = db.query(StudentNotification).filter(
                StudentNotification.student_id == student_id)
            if unread_only:
                q = q.filter(StudentNotification.is_read.is_(False))
            rows = q.order_by(StudentNotification.sent_at.desc()).limit(limit).all()
            return [
                {
                    "notification_id": n.notification_id,
                    "type": n.type,
                    "title": n.title,
                    "content": n.content,
                    "is_read": n.is_read,
                    "sent_at": n.sent_at.strftime("%Y-%m-%d %H:%M") if n.sent_at else "",
                }
                for n in rows
            ]
        finally:
            if db_gen is not None:
                db.close()

    @staticmethod
    def unread_count(student_id: str, db=None) -> int:
        """未读数（badge 数据源）。"""
        db_gen = None if db is not None else get_db()
        db = db if db is not None else next(db_gen)
        try:
            return db.query(StudentNotification).filter(
                StudentNotification.student_id == student_id,
                StudentNotification.is_read.is_(False),
            ).count()
        finally:
            if db_gen is not None:
                db.close()

    @staticmethod
    def mark_read(student_id: str, notification_ids: Optional[list] = None, db=None) -> int:
        """标记已读（本人）；notification_ids 为空 = 全部。返回标记条数。"""
        db_gen = None if db is not None else get_db()
        db = db if db is not None else next(db_gen)
        try:
            q = db.query(StudentNotification).filter(
                StudentNotification.student_id == student_id,
                StudentNotification.is_read.is_(False),
            )
            if notification_ids:
                q = q.filter(StudentNotification.notification_id.in_(notification_ids))
            updated = q.update(
                {StudentNotification.is_read: True},
                synchronize_session=False,
            )
            db.commit()
            return updated
        finally:
            if db_gen is not None:
                db.close()

    @staticmethod
    def mark_single_read(notification_id: str, user_id: str, user_type: str, db) -> dict:
        """标记单条通知已读（本人校验在此；员工需具备 notification:update 权限）。

        Returns: {"ok": bool, "status": 200|404}；404 语义 = 通知不存在或不属于本人
        （不向调用者泄漏归属）。
        """
        if user_type == "parent":
            row = db.query(ParentNotification).filter(
                ParentNotification.notification_id == notification_id,
                ParentNotification.parent_id == user_id,
            ).first()
            if not row:
                return {"ok": False, "status": 404}
            row.is_read = True
            db.commit()
            return {"ok": True, "status": 200}

        from app.models.database import StudentNotification
        row = db.query(StudentNotification).filter(
            StudentNotification.notification_id == notification_id,
            StudentNotification.student_id == user_id,
        ).first()
        if not row:
            return {"ok": False, "status": 404}
        row.is_read = True
        row.read_at = datetime.utcnow()
        db.commit()
        return {"ok": True, "status": 200}

    @staticmethod
    def send_to_parent(
        parent_id: str,
        student_id: str,
        notification_type: str,
        title: str,
        content: Optional[str] = None,
        idempotency_key: Optional[str] = None
    ) -> str:
        """
        发送通知到家长端
        返回通知ID

        提供 idempotency_key 时按确定性 ID 去重：同一事件重复投递返回已存在通知 ID，不重复插入。
        """
        if idempotency_key is not None:
            notification_id = _dedup_notification_id(notification_type, idempotency_key, parent_id)
        else:
            notification_id = f"notif_{parent_id}_{student_id}_{int(datetime.utcnow().timestamp())}"

        db_gen = get_db()
        db = next(db_gen)
        try:
            if idempotency_key is not None:
                existing = db.query(ParentNotification).filter(
                    ParentNotification.notification_id == notification_id
                ).first()
                if existing is not None:
                    return existing.notification_id

            notification = ParentNotification(
                notification_id=notification_id,
                parent_id=parent_id,
                student_id=student_id,
                type=notification_type,
                title=title,
                content=content,
                is_read=False,
                sent_at=datetime.utcnow()
            )
            db.add(notification)
            db.commit()
        finally:
            db.close()

        return notification_id

    @staticmethod
    def send_to_student(
        student_id: str,
        notification_type: str,
        title: str,
        content: Optional[str] = None,
        idempotency_key: Optional[str] = None
    ) -> Optional[str]:
        """
        发送通知到学生端（写入 StudentNotification，与家长端对称）
        返回通知 ID；学生不存在返回 None。
        提供 idempotency_key 时按确定性 ID 去重：同一事件重复投递返回已存在通知 ID，不重复插入。
        """
        db_gen = get_db()
        db = next(db_gen)
        try:
            student = db.query(Student).filter(Student.student_id == student_id).first()
            if not student:
                return None

            if idempotency_key is not None:
                digest = hashlib.sha1(f"{idempotency_key}:{student_id}".encode("utf-8")).hexdigest()[:12]
                notification_id = f"snt_{notification_type}_{digest}"
                existing = db.query(StudentNotification).filter(
                    StudentNotification.notification_id == notification_id
                ).first()
                if existing is not None:
                    return existing.notification_id
            else:
                notification_id = f"snt_{student_id}_{int(datetime.utcnow().timestamp() * 1000)}"

            notification = StudentNotification(
                notification_id=notification_id,
                student_id=student_id,
                type=notification_type,
                title=title,
                content=content,
                is_read=False,
                sent_at=datetime.utcnow()
            )
            db.add(notification)
            db.commit()
        finally:
            db.close()

        return notification_id

    @staticmethod
    def send_practice_notification(student_id: str, practice_name: str, idempotency_key: Optional[str] = None) -> int:
        """
        发送练习通知给家长的绑定家长
        返回发送数量
        """
        db_gen = get_db()
        db = next(db_gen)
        sent_count = 0

        try:
            # 获取学生信息
            student = db.query(Student).filter(Student.student_id == student_id).first()
            if not student:
                return 0

            # 获取绑定家长
            bindings = db.query(StudentParentBinding).filter(
                StudentParentBinding.student_id == student_id,
                StudentParentBinding.status == "active"
            ).all()

            for binding in bindings:
                notification_id = _batch_notification_id(
                    db, "prac", idempotency_key, binding.parent_id,
                    f"prac_{student_id}_{binding.parent_id}_{int(datetime.utcnow().timestamp())}",
                )
                if notification_id is None:
                    continue

                notification = ParentNotification(
                    notification_id=notification_id,
                    parent_id=binding.parent_id,
                    student_id=student_id,
                    type="daily_report",
                    title=f"📝 {student.name} 今日练习已推送",
                    content=f"{practice_name}，请督促孩子完成",
                    is_read=False,
                    sent_at=datetime.utcnow()
                )
                db.add(notification)
                sent_count += 1

            db.commit()
        finally:
            db.close()

        return sent_count

    @staticmethod
    def send_weekly_report_notification(student_id: str, idempotency_key: Optional[str] = None) -> int:
        """
        发送周报通知给家长的绑定家长
        返回发送数量
        """
        db_gen = get_db()
        db = next(db_gen)
        sent_count = 0

        try:
            student = db.query(Student).filter(Student.student_id == student_id).first()
            if not student:
                return 0

            bindings = db.query(StudentParentBinding).filter(
                StudentParentBinding.student_id == student_id,
                StudentParentBinding.status == "active"
            ).all()

            # 无显式事件键时按「周」派生：同一周重放去重，下一周是新事件
            period = idempotency_key or f"week_{datetime.utcnow().strftime('%G-W%V')}"
            for binding in bindings:
                out = NotificationService.dispatch(
                    recipient={"role": "parent", "id": binding.parent_id, "student_id": student_id},
                    event={"type": "weekly_report", "title": f"📊 {student.name} 本周学习周报已生成",
                           "content": "点击查看详细周报"},
                    idempotency_key=f"{period}_{student_id}_{binding.parent_id}",
                    db=db,
                )
                sent_count += 0 if out.get("duplicate") else 1

            db.commit()
        finally:
            db.close()

        return sent_count

    @staticmethod
    def send_warning_notification(
        student_id: str,
        warning_type: str,
        message: str,
        idempotency_key: Optional[str] = None
    ) -> int:
        """
        发送预警通知给家长的绑定家长
        warning_type: 'no_login' / 'score_drop' / 'high_error_rate'
        """
        db_gen = get_db()
        db = next(db_gen)
        sent_count = 0

        try:
            student = db.query(Student).filter(Student.student_id == student_id).first()
            if not student:
                return 0

            bindings = db.query(StudentParentBinding).filter(
                StudentParentBinding.student_id == student_id,
                StudentParentBinding.status == "active"
            ).all()

            type_names = {
                'no_login': '📅 连续未学习提醒',
                'score_drop': '📉 成绩下滑预警',
                'high_error_rate': '⚠️ 错题率过高提醒'
            }

            title = type_names.get(warning_type, '⚠️ 学习提醒')

            for binding in bindings:
                notification_id = _batch_notification_id(
                    db, "warn", idempotency_key, binding.parent_id,
                    f"warn_{warning_type}_{student_id}_{binding.parent_id}_{int(datetime.utcnow().timestamp())}",
                )
                if notification_id is None:
                    continue

                notification = ParentNotification(
                    notification_id=notification_id,
                    parent_id=binding.parent_id,
                    student_id=student_id,
                    type="score_alert",
                    title=f"{title} - {student.name}",
                    content=message,
                    is_read=False,
                    sent_at=datetime.utcnow()
                )
                db.add(notification)
                sent_count += 1

            db.commit()
        finally:
            db.close()

        return sent_count


# 全局实例
notification_service = NotificationService()


def _gateway_send(event: dict, recipient: dict) -> bool:
    """外发 adapter（seam，测试注入点）：经 chemistry_notification 的网关外发。

    由配置 NOTIFY_EXTERNAL_GATEWAYS 控制（默认关——仅站内）。开启后也只在**收件人自带
    per-收件人投递配置**（recipient.chat_id）时外发：没有配置就静默降级为仅站内，
    绝不把学生学业数据广播到共享频道（notification-dispatch spec「外部网关保守禁用」）。
    全局 TELEGRAM_BOT_TOKEN 只是机器人凭据，TELEGRAM_CHAT_ID 不作广播目的地。
    凭据/网关缺失或失败仅记日志降级，绝不阻断站内落库（dispatch 调用方语义）。
    """
    try:
        import os

        from app.core.config import settings
        from chem_skills.chemistry_notification.handler import TelegramGateway

        chat_id = (recipient or {}).get("chat_id") or ""
        if not chat_id:
            logger.info("external gateway enabled but recipient %s has no delivery route; "
                        "in-app only: %s", (recipient or {}).get("id"), event.get("type"))
            return False

        token = getattr(settings, "TELEGRAM_BOT_TOKEN", "") or os.getenv("TELEGRAM_BOT_TOKEN", "")
        if not token:
            logger.info("external gateway enabled but bot credential not configured; skip: %s",
                        event.get("type"))
            return False

        text = " ".join(part for part in (event.get("title", ""), event.get("content") or "") if part)
        result = TelegramGateway(bot_token=token).send(chat_id=chat_id, text=text)
        if not getattr(result, "success", False):
            logger.warning("gateway send failed: %s", getattr(result, "error", "?"))
            return False
        return True
    except Exception as e:
        logger.warning("external gateway send error: %s", e)
        return False


def send_practice_notification(student_id: str, practice_name: str) -> int:
    """便捷函数"""
    return notification_service.send_practice_notification(student_id, practice_name)


def send_weekly_report_notification(student_id: str) -> int:
    """便捷函数"""
    return notification_service.send_weekly_report_notification(student_id)


def send_warning_notification(student_id: str, warning_type: str, message: str) -> int:
    """便捷函数"""
    return notification_service.send_warning_notification(student_id, warning_type, message)


def send_student_notification(
    student_id: str,
    notification_type: str,
    title: str,
    content: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> Optional[str]:
    """便捷函数：学生端通知"""
    return notification_service.send_to_student(
        student_id, notification_type, title, content, idempotency_key
    )

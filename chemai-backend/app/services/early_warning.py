"""
实时学情预警服务
检测学生学情异常并触发预警
"""

from datetime import datetime
from typing import List, Optional
from app.models.database import (
    Student, StudentAnswer, ExamRecord, StudentParentBinding, get_db, RecordType
)
from app.models.warning_log import WarningLog
from app.services.notification_service import notification_service


class EarlyWarningService:
    """学情预警服务"""

    # 预警阈值
    NO_LOGIN_DAYS = 3  # 连续3天未登录
    SCORE_DROP_THRESHOLD = 0.1  # 成绩下滑超过10%
    HIGH_ERROR_RATE_THRESHOLD = 0.5  # 错题率超过50%

    def check_all_warnings(self, class_ids=None):
        """检查学生预警情况（class_ids 给定时只查这些班级，供 HTTP 入口按调用者范围收窄）。

        class_ids 为 None = 全量（调度器周期作业）；空集 = 什么都看不到，直接返回空。
        """
        db_gen = get_db()
        db = next(db_gen)

        try:
            query = db.query(Student).filter(Student.status == "approved")
            if class_ids is not None:
                if not class_ids:
                    return []
                query = query.filter(Student.class_id.in_(list(class_ids)))
            students = query.all()
            warnings_created = []

            for student in students:
                # 检查连续未登录预警
                login_warning = self.check_no_login_warning(db, student)
                if login_warning:
                    warnings_created.append(login_warning)

                # 检查成绩下滑预警
                score_warning = self.check_score_drop_warning(db, student)
                if score_warning:
                    warnings_created.append(score_warning)

                # 检查错题率过高预警
                error_warning = self.check_high_error_rate_warning(db, student)
                if error_warning:
                    warnings_created.append(error_warning)

            return warnings_created
        finally:
            db.close()

    def check_no_login_warning(self, db, student) -> Optional[WarningLog]:
        """检查连续未登录预警"""
        if not student.last_exercise_at:
            # 从未登录过，检查创建时间
            days_since_creation = (datetime.utcnow() - student.created_at).days
            if days_since_creation >= self.NO_LOGIN_DAYS:
                return self._create_warning(
                    db, student,
                    warning_type="no_login",
                    level="warning",
                    title=f"{student.name} 已连续{days_since_creation}天未学习",
                    content="学生最后学习时间: 从未登录",
                    data={"days": days_since_creation}
                )
            return None

        days_since_login = (datetime.utcnow() - student.last_exercise_at).days
        if days_since_login >= self.NO_LOGIN_DAYS:
            return self._create_warning(
                db, student,
                warning_type="no_login",
                level="warning",
                title=f"{student.name} 已连续{days_since_login}天未学习",
                content=f"学生最后学习时间: {student.last_exercise_at.strftime('%Y-%m-%d')}",
                data={"days": days_since_login}
            )

        return None

    def check_score_drop_warning(self, db, student) -> Optional[WarningLog]:
        """检查成绩下滑预警"""
        # 获取学生最近的两次考试成绩
        exam_records = db.query(ExamRecord).filter(
            ExamRecord.class_id == student.class_id,
            ExamRecord.type == RecordType.EXAM,
            ExamRecord.avg_score.isnot(None)
        ).order_by(ExamRecord.exam_date.desc()).limit(2).all()

        if len(exam_records) < 2:
            return None

        latest_score = exam_records[0].avg_score
        previous_score = exam_records[1].avg_score

        if previous_score == 0:
            return None

        drop_rate = (previous_score - latest_score) / previous_score

        if drop_rate >= self.SCORE_DROP_THRESHOLD:
            return self._create_warning(
                db, student,
                warning_type="score_drop",
                level="warning" if drop_rate < 0.2 else "critical",
                title=f"{student.name} 成绩下滑 {int(drop_rate * 100)}%",
                content=f"上次成绩: {previous_score:.1f}, 本次成绩: {latest_score:.1f}",
                data={
                    "previous_score": previous_score,
                    "latest_score": latest_score,
                    "drop_rate": drop_rate
                }
            )

        return None

    def check_high_error_rate_warning(self, db, student) -> Optional[WarningLog]:
        """检查错题率过高预警"""
        # 获取学生最近的练习/考试成绩
        recent_record = db.query(ExamRecord).filter(
            ExamRecord.class_id == student.class_id
        ).order_by(ExamRecord.exam_date.desc()).first()

        if not recent_record:
            return None

        # 该学生自己的最新作答记录（练习已改为每生一份，不能复用班级最新记录）
        own_latest = db.query(ExamRecord).join(
            StudentAnswer, StudentAnswer.exam_record_id == ExamRecord.record_id
        ).filter(
            ExamRecord.class_id == student.class_id,
            StudentAnswer.student_id == student.student_id,
        ).order_by(ExamRecord.exam_date.desc()).first()

        if own_latest is None:
            return None

        answers = db.query(StudentAnswer).filter(
            StudentAnswer.student_id == student.student_id,
            StudentAnswer.exam_record_id == own_latest.record_id
        ).all()

        if len(answers) == 0:
            return None

        error_count = sum(1 for a in answers if not a.is_correct)
        error_rate = error_count / len(answers)

        if error_rate >= self.HIGH_ERROR_RATE_THRESHOLD:
            return self._create_warning(
                db, student,
                warning_type="high_error_rate",
                level="info" if error_rate < 0.7 else "warning",
                title=f"{student.name} 错题率过高 ({int(error_rate * 100)}%)",
                content=f"共{len(answers)}题，错{error_count}题",
                data={
                    "total_questions": len(answers),
                    "error_count": error_count,
                    "error_rate": error_rate
                }
            )

        return None

    def _create_warning(
        self,
        db,
        student,
        warning_type: str,
        level: str,
        title: str,
        content: str,
        data: dict
    ) -> WarningLog:
        """创建预警日志"""
        # 检查是否已有相同类型的未处理预警
        existing = db.query(WarningLog).filter(
            WarningLog.student_id == student.student_id,
            WarningLog.warning_type == warning_type,
            WarningLog.status == "pending"
        ).first()

        if existing:
            return existing

        warning_id = f"warn_{warning_type}_{student.student_id}_{int(datetime.utcnow().timestamp())}"

        warning = WarningLog(
            warning_id=warning_id,
            student_id=student.student_id,
            warning_type=warning_type,
            level=level,
            title=title,
            content=content,
            data=data,
            status="pending"
        )

        db.add(warning)
        db.commit()

        # 学生端通知（与预警日志对称；幂等键=预警日志ID）
        try:
            from app.services.notification_service import notification_service
            notification_service.send_to_student(
                student.student_id,
                "warning",
                title,
                content,
                idempotency_key=f"warnlog_{warning.warning_id}",
            )
        except Exception:
            pass  # 通知失败不阻断预警主流程

        # 发送通知
        self._send_warning_notifications(db, student, warning)

        return warning

    def _send_warning_notifications(self, db, student, warning: WarningLog):
        """发送预警通知"""
        # 通知家长
        bindings = db.query(StudentParentBinding).filter(
            StudentParentBinding.student_id == student.student_id,
            StudentParentBinding.status == "active"
        ).all()

        for binding in bindings:
            notification_service.send_warning_notification(
                student_id=student.student_id,
                warning_type=warning.warning_type,
                message=warning.content
            )

    def get_pending_warnings(self, db, class_id: Optional[str] = None,
                             class_ids=None) -> List[WarningLog]:
        """获取待处理预警列表。

        class_ids：调用者可触达的班级集合（第二层范围）——空集表示什么都不给，
        不能退化成「返回全库待处理预警」。
        """
        query = db.query(WarningLog).filter(WarningLog.status == "pending")

        if class_id:
            query = query.join(Student).filter(Student.class_id == class_id)
        elif class_ids is not None:
            if not class_ids:
                return []
            query = query.join(Student).filter(Student.class_id.in_(class_ids))

        return query.order_by(WarningLog.created_at.desc()).all()

    def get_warnings_by_student(self, db, student_id: str) -> List[WarningLog]:
        """获取指定学生的预警历史"""
        return db.query(WarningLog).filter(
            WarningLog.student_id == student_id
        ).order_by(WarningLog.created_at.desc()).all()

    def process_warning(
        self,
        db,
        warning_id: str,
        processed_by: str,
        note: Optional[str] = None,
        action: str = "processed"
    ):
        """处理预警"""
        warning = db.query(WarningLog).filter(WarningLog.warning_id == warning_id).first()
        if not warning:
            return None

        warning.status = action  # processed/ignored
        warning.processed_by = processed_by
        warning.processed_at = datetime.utcnow()
        if note:
            warning.processed_note = note

        db.commit()
        return warning


# 全局实例
ews = EarlyWarningService()


def check_all_warnings(class_ids=None):
    """便捷函数（class_ids=None 为全量：调度器周期作业走这条）"""
    return ews.check_all_warnings(class_ids)


def get_pending_warnings(class_id: Optional[str] = None, class_ids=None, db=None):
    """获取待处理预警（db 给定时用调用方会话——端点单会话，测试可注入）。"""
    if db is not None:
        return ews.get_pending_warnings(db, class_id, class_ids)
    db_gen = get_db()
    db = next(db_gen)
    try:
        return ews.get_pending_warnings(db, class_id, class_ids)
    finally:
        db.close()


def process_warning(warning_id: str, processed_by: str, note: Optional[str] = None):
    """处理预警"""
    db_gen = get_db()
    db = next(db_gen)
    try:
        return ews.process_warning(db, warning_id, processed_by, note)
    finally:
        db.close()

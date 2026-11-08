"""
每日练习自动推送任务
根据艾宾浩斯遗忘曲线为每个学生推送个性化的每日练习

落点契约（openspec/school-data-initialization）：
- 每次推送为每位学生创建独立的练习记录（ExamRecord, type=PRACTICE）
- 练习题目必须落实体 Question 行并挂到该练习记录（record_id）下
- 学生完成作答经 /api/practice/submit 落 student_answers
- 推送同时落学生端通知（StudentNotification）与家长端通知（ParentNotification，幂等）
"""

import json
from datetime import datetime

from sqlalchemy import func

from app.models.database import (
    Student, StudentParentBinding, ParentNotification,
    ExamRecord, Question, StudentAnswer, QuestionSource, AuditStatus,
    get_db, RecordType
)
from app.models.review_task import ReviewTask
from app.services.notification_service import notification_service

DAILY_QUESTION_COUNT = 5


def _pick_weak_knowledge_points(db, student):
    """从学生错题中统计薄弱知识点（真实错题历史），无错题时回退默认组合"""
    wrong_rows = (
        db.query(Question.knowledge_points)
        .join(StudentAnswer, StudentAnswer.question_id == Question.question_id)
        .filter(StudentAnswer.student_id == student.student_id)
        .filter(StudentAnswer.is_correct.is_(False))
        .order_by(StudentAnswer.answered_at.desc())
        .limit(30)
        .all()
    )
    counter = {}
    for (kps_json,) in wrong_rows:
        kps = kps_json if isinstance(kps_json, list) else (
            json.loads(kps_json) if isinstance(kps_json, str) and kps_json else []
        )
        for kp in kps or []:
            counter[kp] = counter.get(kp, 0) + 1
    if counter:
        ranked = sorted(counter.items(), key=lambda x: -x[1])
        return [kp for kp, _ in ranked[:3]]
    return ["氧化还原反应", "物质的量", "离子反应"]


def _select_practice_questions(db, weak_kps, count=DAILY_QUESTION_COUNT):
    """选题：优先薄弱知识点（优先选近期未被用过的），不足时从题库随机补齐"""
    picked, seen = [], set()
    for kp in weak_kps:
        rows = (
            db.query(Question)
            .filter(Question.knowledge_points.like(f'%"{kp}"%'))
            .order_by(func.random())
            .limit(count)
            .all()
        )
        for q in rows:
            if q.question_id not in seen:
                picked.append(q)
                seen.add(q.question_id)
        if len(picked) >= count:
            return picked[:count]
    fallback = (
        db.query(Question)
        .order_by(func.random())
        .limit(count * 2)
        .all()
    )
    for q in fallback:
        if q.question_id not in seen:
            picked.append(q)
            seen.add(q.question_id)
        if len(picked) >= count:
            break
    return picked[:count]


def create_daily_practice(db, student, day=None):
    """
    为学生创建每日练习：独立练习记录 + 实体题目 + 学生端通知。

    day 缺省为今天；补录历史练习时传入当日日期。
    幂等：同一学生同一天已有练习（含已完成）则直接返回已有记录。
    返回创建（或已存在）的练习记录，无题可组时返回 None。
    """
    today = day or datetime.utcnow().date()
    day_start = datetime.combine(today, datetime.min.time())

    existing = db.query(ExamRecord).filter(
        ExamRecord.record_id.like(f"daily_{student.student_id}_%"),
        ExamRecord.exam_date >= day_start,
    ).first()
    if existing:
        return existing

    weak_kps = _pick_weak_knowledge_points(db, student)
    questions = _select_practice_questions(db, weak_kps)
    if not questions:
        return None

    practice_id = f"daily_{student.student_id}_{today.strftime('%Y%m%d')}"
    practice = ExamRecord(
        record_id=practice_id,
        class_id=student.class_id,
        type=RecordType.PRACTICE,
        name=f"每日练习 {today.strftime('%Y-%m-%d')}",
        question_stats={
            "knowledge_points": weak_kps,
            "question_count": len(questions),
            "target_barrier": _dominant_barrier(student.barrier_type),
        },
        exam_date=datetime.combine(today, datetime.max.time()),
        total_students=1,
        present_students=0,
        source=QuestionSource.DAILY_PRACTICE,
    )
    db.add(practice)

    # 题目挂到练习记录：引用题库原题（复制题干为练习实例，保持原考试的题目归属不被改写）
    for i, q in enumerate(questions):
        instance_id = f"{practice_id}_q{i + 1:02d}"
        if not db.query(Question).filter(Question.question_id == instance_id).first():
            db.add(Question(
                question_id=instance_id,
                record_id=practice_id,
                content=q.content,
                options=q.options,
                answer=q.answer,
                analysis=q.analysis,
                knowledge_points=q.knowledge_points,
                probe_dimension=q.probe_dimension,
                difficulty=q.difficulty,
                source=QuestionSource.DAILY_PRACTICE,
                audit_status=AuditStatus.PASSED,
            ))
    db.commit()

    # 学生端通知（幂等键=练习记录ID）
    notification_service.send_to_student(
        student.student_id,
        "practice",
        f"📝 今日练习已推送（{weak_kps[0]}等 {len(questions)} 题）",
        content="完成今日练习，巩固薄弱知识点",
        idempotency_key=practice_id,
    )
    return practice


def _dominant_barrier(barrier_type):
    """获取主要障碍类型名称"""
    if isinstance(barrier_type, dict) and barrier_type:
        dominant = max(barrier_type, key=barrier_type.get)
        return {
            "concept": "概念理解型",
            "reading": "审题障碍型",
            "expression": "表述障碍型",
        }.get(dominant, "概念理解型")
    return "概念理解型"


def daily_practice_job():
    """
    每日8点执行：
    1. 为每个学生生成/推送今日练习任务（实体题目+独立记录）
    2. 学生端通知 + 家长端通知（幂等）
    3. 检查复习到期情况，发送复习提醒
    """
    db_gen = get_db()
    db = next(db_gen)

    try:
        students = db.query(Student).filter(Student.status == "approved").all()

        pushed_count = 0
        review_reminder_count = 0

        for student in students:
            practice = create_daily_practice(db, student)

            if practice:
                # 更新学生的最近练习时间
                student.last_exercise_at = datetime.utcnow()
                db.commit()
                pushed_count += 1

            # 家长端通知（幂等键=练习记录ID；无练习不推送）
            bindings = db.query(StudentParentBinding).filter(
                StudentParentBinding.student_id == student.student_id,
                StudentParentBinding.status == "active"
            ).all()

            for binding in bindings:
                if practice:
                    daily_nid = _parent_notification_id("daily", practice.record_id, binding.parent_id)
                    exists = db.query(ParentNotification).filter(
                        ParentNotification.notification_id == daily_nid
                    ).first()
                    if exists is None:
                        db.add(ParentNotification(
                            notification_id=daily_nid,
                            parent_id=binding.parent_id,
                            student_id=student.student_id,
                            type="daily_report",
                            title=f"📝 {student.name} 今日练习已推送",
                            content="练习知识点：{}，请督促孩子完成".format(
                                practice.question_stats.get('knowledge_points', [])[:2]),
                            is_read=False,
                            sent_at=datetime.utcnow()
                        ))
                        pushed_count += 1

                # 检查复习到期情况
                due_reviews = db.query(ReviewTask).filter(
                    ReviewTask.student_id == student.student_id,
                    ReviewTask.status.in_(["pending", "overdue"]),
                    ReviewTask.next_review_at <= datetime.utcnow()
                ).count()

                if due_reviews > 0:
                    reminder_key = f"review_{student.student_id}_{datetime.utcnow().date():%Y%m%d}"
                    reminder_nid = _parent_notification_id("review", reminder_key, binding.parent_id)
                    exists = db.query(ParentNotification).filter(
                        ParentNotification.notification_id == reminder_nid
                    ).first()
                    if exists is None:
                        db.add(ParentNotification(
                            notification_id=reminder_nid,
                            parent_id=binding.parent_id,
                            student_id=student.student_id,
                            type="reminder",
                            title=f"📚 {student.name} 有 {due_reviews} 道错题待复习",
                            content="请督促孩子完成复习任务",
                            is_read=False,
                            sent_at=datetime.utcnow()
                        ))
                        review_reminder_count += 1

        db.commit()
        print(f"[每日练习] 推送 {pushed_count} 份练习，复习提醒 {review_reminder_count} 条")

    finally:
        db.close()


def _parent_notification_id(prefix: str, idempotency_key: str, parent_id: str) -> str:
    """与 NotificationService 同规则的确定性通知 ID（家长端批处理去重用）"""
    import hashlib
    digest = hashlib.sha1(f"{idempotency_key}:{parent_id}".encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


if __name__ == "__main__":
    daily_practice_job()

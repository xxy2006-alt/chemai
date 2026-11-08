"""考试生命周期状态机（exam-lifecycle，P4）。

六态 + cancelled（CONTEXT.md 承诺做实）；迁移合法表驱动、时间戳留痕。
FINALIZE_FRIENDLY：→completed 额外放行 published/in_progress（发布后无人作答
直接收卷的现实路径）；draft →completed 仍拒绝（未发布何谈收卷）。
"""
from datetime import datetime

from app.models.database import ExamRecord, ExamStatus, RecordType

_TIMESTAMP_FIELDS = {
    "published": "published_at",
    "in_progress": "started_at",
    "grading": "grading_at",
    "completed": "completed_at",
    "cancelled": "cancelled_at",
}

_LEGAL = {
    "draft": {"published", "cancelled"},
    "published": {"in_progress", "grading", "completed", "cancelled"},
    "in_progress": {"grading", "completed", "cancelled"},
    "grading": {"completed", "cancelled"},
    "completed": {"archived"},
    "archived": set(),
    "cancelled": set(),
}


def _status_of(record: ExamRecord) -> str:
    """当前状态名；None（存量未回填）按 draft 处理。"""
    if record.status is None:
        return "draft"
    return record.status.value if hasattr(record.status, "value") else str(record.status)


def can_transition(record: ExamRecord, to_status: str) -> bool:
    """只判合法性、不改状态：写侧在落库（统计/作答）之前先问一次，避免先写后拒。"""
    current = _status_of(record)
    if to_status == current:
        return True
    if to_status not in _LEGAL.get(current, set()):
        return False
    if to_status == "completed" and current == "draft":
        return False  # 与 _LEGAL 冗余，双保险
    return True


def transition(db, record: ExamRecord, to_status: str) -> bool:
    """把考试记录迁移到目标状态；非法迁移返回 False（不抛，调用方决定语义）。"""
    if not can_transition(record, to_status):
        return False
    if _status_of(record) == to_status:
        return True

    record.status = ExamStatus(to_status)
    field = _TIMESTAMP_FIELDS.get(to_status)
    if field:
        setattr(record, field, datetime.utcnow())
    return True  # 事务边界归调用方（ADR-0012）——不内嵌 commit


def status_of(record: ExamRecord) -> str:
    """公开读侧：当前状态名（None 存量按 draft）。"""
    return _status_of(record)


def mark_started(db, record: ExamRecord) -> None:
    """开考握手：published → in_progress（学生首次取题时调用，幂等）。"""
    if _status_of(record) == "published":
        transition(db, record, "in_progress")


def mark_grading(db, record: ExamRecord) -> None:
    """判卷中心握手：首份考试结果落库 → grading（幂等）。"""
    if _status_of(record) in ("published", "in_progress"):
        transition(db, record, "grading")


def mark_completed_on_finalize(db, record: ExamRecord) -> bool:
    """finalize 握手：grading（或已发布/进行中的收卷）→ completed。"""
    return transition(db, record, "completed")


def exam_already_submitted(db, exam_record_id: str, student_id: str) -> bool:
    """EXAM 提交一次性守卫：该生在该考试已有作答即视为已提交。"""
    from app.models.database import StudentAnswer
    return db.query(StudentAnswer).filter(
        StudentAnswer.exam_record_id == exam_record_id,
        StudentAnswer.student_id == student_id,
    ).count() > 0


def backfill_statuses(db) -> int:
    """存量回填：无 status 的记录按 question_stats.published 推导（考试），
    练习/作业记 draft（生命周期仅对考试有意义，练习保持 None 亦可——这里统一
    置 draft 以便状态列非空可查）。返回回填行数。
    """
    rows = db.query(ExamRecord).filter(ExamRecord.status.is_(None)).all()
    n = 0
    for r in rows:
        stats = r.question_stats if isinstance(r.question_stats, dict) else {}
        if r.type == RecordType.EXAM and stats.get("published"):
            r.status = ExamStatus.PUBLISHED
            r.published_at = r.published_at or datetime.utcnow()
        else:
            r.status = ExamStatus.DRAFT
        n += 1
    if n:
        db.commit()
    return n

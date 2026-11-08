"""后台作业处理器（handler 面）——「作业调度边界」的消费侧。

这里的函数是幂等、同步、可脱离队列单独测试的；Celery task 只是它们的薄包装。
"""
import re
import json as _json
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.database import (
    Student, ExamRecord, StudentAnswer, Question, BarrierType, get_db,
)


def _diagnose_barrier_answers(db: Session, wrong_answers, source_id: str = "") -> dict:
    """对一批错答跑 LLM 障碍判定并重算相关学生的 barrier 分布（幂等聚合）。

    exam 场景与学生场景（chat 作答无 exam 归属）共用的核心。
    source_id: 本次诊断的来源标识（考试/练习记录 id），用于学生端通知的幂等键。
    """
    from app.services.llm_service import llm_service
    import concurrent.futures

    analyzed, failed = 0, 0
    barrier_dist = {"concept": 0, "reading": 0, "expression": 0}
    updated_students = set()

    def diagnose_single(ans):
        nonlocal analyzed, failed
        question = db.query(Question).filter(
            Question.question_id == ans.question_id
        ).first()
        if question is None:
            return

        q_content = question.content or ""
        correct = question.answer or ""
        student_ans = ans.student_answer or ""

        result = llm_service.diagnose_barrier_type(
            student_error_history=[{
                "question": q_content[:300],
                "wrong_answer": student_ans,
                "correct_answer": correct,
            }],
            question_content=q_content[:500],
            student_answer=student_ans,
            correct_answer=correct,
        )

        if result.get("success"):
            content = result.get("content", "{}")
            _json_match = re.search(r'\{[\s\S]*\}', content)
            if _json_match:
                try:
                    data = _json.loads(_json_match.group())
                    bt = data.get("barrier_type", "concept")
                    if bt in ("concept", "reading", "expression"):
                        ans.barrier_type = getattr(BarrierType, bt.upper(), BarrierType.CONCEPT)
                        analyzed += 1
                except _json.JSONDecodeError:
                    failed += 1
            else:
                failed += 1
        else:
            failed += 1

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        list(executor.map(lambda a: diagnose_single(a), wrong_answers))

    db.commit()

    for ans in wrong_answers:
        if ans.barrier_type and ans.student_id:
            updated_students.add(ans.student_id)
            bt = ans.barrier_type.value
            barrier_dist[bt] = barrier_dist.get(bt, 0) + 1

    for sid in updated_students:
        student = db.query(Student).filter(Student.student_id == sid).first()
        if student:
            all_answers = db.query(StudentAnswer).filter(
                StudentAnswer.student_id == sid,
                StudentAnswer.is_correct.is_(False),
                StudentAnswer.barrier_type.isnot(None),
            ).all()
            counts = {"concept": 0, "reading": 0, "expression": 0}
            for a in all_answers:
                if a.barrier_type:
                    counts[a.barrier_type.value] = counts.get(a.barrier_type.value, 0) + 1
            total = sum(counts.values()) or 1
            student.barrier_type = {k: round(v / total, 2) for k, v in counts.items()}
            student.barrier_last_updated = datetime.utcnow()
            for bt in ("concept", "reading", "expression"):
                if bt not in student.barrier_type:
                    student.barrier_type[bt] = 0.0
            # 诊断完成 → 学生端通知（幂等键=来源+学生）
            # （barrier_last_updated 上面已经赋过，这里不再重复）
            # 合并说明：原写死 `diag_{exam_record_id}_{sid}`，但 exam_record_id 不在本函数
            # 作用域内（exam 与学生场景共用）。改成由调用方透传 source_id；没有来源
            # （chat 作答触发的诊断）时按天去重。
            _notify_key = (f"diag_{source_id}_{sid}" if source_id
                           else f"diag_{sid}_{datetime.utcnow():%Y%m%d}")
            try:
                from app.services.notification_service import notification_service
                notification_service.send_to_student(
                    sid,
                    "diagnosis",
                    "🧠 学习诊断已更新",
                    content="本次练习的错因分析完成，已更新你的学习画像与薄弱点",
                    idempotency_key=_notify_key,
                )
            except Exception:
                pass  # 通知失败不阻断诊断主流程

    db.commit()

    return {"analyzed_count": analyzed, "failed_count": failed,
            "barrier_distribution": barrier_dist}


def diagnose_student_recent(db: Session, student_id: str, source: str = None) -> dict:
    """学生级诊断（P5 对话回流）：该生最近的错答（含 chat 等无 exam 归属作答）。

    source: 可选来源过滤（online/ocr/manual/chat/training）——读侧按来源
    聚合/排除的能力预留（如教学上决定对话作答不参与诊断时切到 source 参数）。
    """
    from app.models.database import AnswerSource
    from app.services.grading_center import effective_conditions
    wrong = db.query(StudentAnswer).filter(
        StudentAnswer.student_id == student_id,
        StudentAnswer.is_correct.is_(False),
        effective_conditions(),
    )
    if source:
        wrong = wrong.filter(StudentAnswer.source == AnswerSource(source))
    wrong = wrong.order_by(
        StudentAnswer.barrier_type.is_(None).desc(),  # 未诊断优先
        StudentAnswer.answered_at.desc(),
    ).limit(10).all()
    if not wrong:
        return {"student_id": student_id, "analyzed_count": 0, "failed_count": 0,
                "barrier_distribution": {"concept": 0, "reading": 0, "expression": 0}}
    out = _diagnose_barrier_answers(db, wrong)
    out["student_id"] = student_id
    return out


def scan_semantic_pending(db: Session, exam_record_id: str = None) -> dict:
    """扫描待语义判定的主观题作答（PENDING_SEMANTIC），判定后覆盖落定。

    Celery 作业与 APScheduler 周期作业共用；判定失败保留标记下轮重扫（ADR-0013）。
    """
    from sqlalchemy import and_, or_

    from app.services.grading_center import PENDING_REASON, judge_semantic
    from app.models.database import Question

    q = db.query(StudentAnswer).filter(
        StudentAnswer.grade_reason == PENDING_REASON,
    )
    if exam_record_id:
        q = q.filter(StudentAnswer.exam_record_id == exam_record_id)
    # 不可判的行（既没随行答案键、题目也没标准答案）不进扫描窗口：窗口是 LIMIT 50 且
    # 按 rowid 稳定排序，攒够 50 条不可判行就会把窗口占满，新落的主观题永远轮不到
    q = q.outerjoin(Question, Question.question_id == StudentAnswer.question_id).filter(
        or_(StudentAnswer.answer_key.isnot(None),
            and_(Question.answer.isnot(None), Question.answer != ""))
    )
    pending = q.order_by(StudentAnswer.answered_at).limit(50).all()
    if not pending:
        return {"scanned": 0, "judged": 0}

    by_id = {}
    for ans in pending:
        if ans.question_id not in by_id:
            qrow = db.query(Question).filter(
                Question.question_id == ans.question_id).first()
            by_id[ans.question_id] = qrow

    unresolved, meta = [], []
    for ans in pending:
        qrow = by_id.get(ans.question_id)
        # 优先用落行时真正用的答案键（老师粘贴 > 题库）：拿题库草稿重判会给出伪定论
        correct = (ans.answer_key or "").strip() or ((qrow.answer or "").strip() if qrow else "")
        if not correct:
            continue
        unresolved.append({
            "question_id": ans.question_id,
            "student_answer": ans.student_answer or "",
            "correct_answer": correct,
            "is_correct": False, "reason": "", "needs_semantic": True,
        })
        meta.append(ans)

    judge_semantic(unresolved)
    judged = 0
    touched = set()
    for ans, q in zip(meta, unresolved):
        if q.get("needs_semantic") or q.get("judge_failed"):
            continue  # 判定失败：保留 PENDING 标记下轮重扫
        ans.is_correct = bool(q["is_correct"])
        ans.grade_reason = (q["reason"] or "")[:256] or None
        judged += 1
        if ans.exam_record_id:
            touched.add((ans.exam_record_id, ans.student_id))
    db.commit()

    # 判定落定后：逐生补「判卷完成」通知（幂等键与同步落库共用，重放不重复）+ 诊断
    from app.services.grading_center import notify_graded
    for exam_record_id_, _sid in touched:
        notify_graded(db, _sid, exam_record_id_)
    db.commit()
    for exam_record_id_, _sid in touched:
        diagnose_exam(db, exam_record_id_)  # 同模块函数，调用时已定义
    return {"scanned": len(pending), "judged": judged}


def handle_semantic_scan(exam_record_id: str = None) -> dict:
    """扫描作业入口：自开会话（幂等，可被队列/调度器重复触发）。"""
    db_gen = get_db()
    db = next(db_gen)
    try:
        return scan_semantic_pending(db, exam_record_id)
    finally:
        db.close()


def handle_diagnosis_student(student_id: str) -> dict:
    """学生级诊断作业入口：自开会话（幂等，可被队列重复投递）。"""
    db_gen = get_db()
    db = next(db_gen)
    try:
        return diagnose_student_recent(db, student_id)
    finally:
        db.close()


def diagnose_exam(db: Session, exam_record_id: str) -> dict:
    """对一场考试的错误答案运行 LLM 障碍诊断，并重算 Student.barrier_type。

    幂等：重复执行只重算聚合（不增量），不产生重复副作用。
    返回 dict：{exam_id, analyzed_count, failed_count, barrier_distribution, error?}
    """
    exam_record = db.query(ExamRecord).filter(
        ExamRecord.record_id == exam_record_id
    ).first()
    if exam_record is None:
        return {
            "exam_id": exam_record_id, "analyzed_count": 0, "failed_count": 0,
            "barrier_distribution": {"concept": 0, "reading": 0, "expression": 0},
            "error": "exam_not_found",
        }

    from app.services.grading_center import effective_conditions
    wrong_answers = db.query(StudentAnswer).filter(
        StudentAnswer.exam_record_id == exam_record_id,
        StudentAnswer.is_correct.is_(False),
        effective_conditions(),
    ).order_by(
        StudentAnswer.barrier_type.is_(None).desc()  # 未诊断的优先
    ).limit(10).all()  # 最多分析10个

    if not wrong_answers:
        return {
            "exam_id": exam_record_id, "analyzed_count": 0, "failed_count": 0,
            "barrier_distribution": {"concept": 0, "reading": 0, "expression": 0},
        }

    out = _diagnose_barrier_answers(db, wrong_answers, source_id=exam_record_id)
    return {
        "exam_id": exam_record_id,
        "analyzed_count": out["analyzed_count"],
        "failed_count": out["failed_count"],
        "barrier_distribution": out["barrier_distribution"],
    }


def handle_diagnosis(exam_record_id: str) -> dict:
    """诊断作业入口：自开会话并运行诊断（幂等，可被队列重复投递）。"""
    db_gen = get_db()
    db = next(db_gen)
    try:
        return diagnose_exam(db, exam_record_id)
    finally:
        db.close()



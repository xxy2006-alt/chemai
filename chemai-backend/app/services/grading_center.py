"""判卷中心（Grading Center）— 一切作答经同一判卷、落库、纠偏路径。

来源无关的 interface（ADR-0012：业务逻辑住 service，HTTP 与 Agent 工具均为 adapter）：
- grade(entries, key)          分层判定：归一化精确匹配 + 非选择题批量语义判定（≤1 次调用）
- judge_semantic(unresolved)   后台作业用：对未决主观题补语义判定
- save(...)                    单点写 StudentAnswer；练习即生效并触发诊断，考试由确认路径触发
- save_batch(...)              答题卡批量确认保存（判卷中心页 / Agent 共用）
- override(...)                教师改判，改判以该记录为单位重触发诊断
- finalize(...)                真实统计（均分/分布/参与），替换 exam finalize 占位

内核（归一化/化学式标准化/批量语义判定）承继自原 llm_grading，见 ADR-0004/0005。
"""
import logging
from dataclasses import dataclass, field
from typing import Optional, Set

logger = logging.getLogger(__name__)

# 作答来源合法值（字符串形态，适配 JSON 入参）
_VALID_SOURCES = {"online", "ocr", "manual", "chat", "training"}


@dataclass(frozen=True)
class CallerScope:
    """判卷写/读的调用者范围（adapter 解析身份后传入，service 只做判定）。

    - caller_id / school_wide：OCR 答题卡批次的归属（上传者本人；校级管理员限本校教师）；
    - class_ids：可触达班级，用于考试归属校验（考试 class_id ∈ class_ids）；
    - school_id / db：校级管理员判定批次归属时要查上传者所属学校。

    学生/家长/身份缺失一律空集 → 任何批次、任何考试都不放行（fail-closed）。
    """

    caller_id: str = ""
    class_ids: Set[str] = field(default_factory=set)
    school_wide: bool = False
    school_id: Optional[str] = None
    db: object = None

    @classmethod
    def from_user(cls, db, user: dict) -> "CallerScope":
        """HTTP / Agent 共用构造：user = {"user_id","role","school_id"}（来自 token）。"""
        from app.middleware.scope import RequestScope, STAFF_ROLES

        user = user or {}
        role = user.get("role") or ""
        if role not in STAFF_ROLES:
            return cls()
        return cls(
            caller_id=user.get("user_id") or "",
            class_ids=set(RequestScope.from_user(user, db).class_ids()),
            school_wide=role in ("admin", "academic_admin"),
            school_id=user.get("school_id"),
            db=db,
        )

    @classmethod
    def from_user_id(cls, db, user_id: str) -> "CallerScope":
        """按 token 身份（user_id）反查账户构造——Agent 工具用。"""
        from app.middleware.scope import resolve_identity

        return cls.from_user(db, resolve_identity(db, user_id))

    def visible_batch_owners(self) -> list:
        """可读批次的归属人集合（空集 = 一条都不给，fail-closed）。

        本人总是在内；校级管理员再加本校教师（查不到学校 / 非本校教师一律不在内）。
        """
        owners = [self.caller_id] if self.caller_id else []
        if self.school_wide:
            from app.models.database import Teacher

            if not (self.db and self.school_id):
                return []
            owners += [
                r[0] for r in self.db.query(Teacher.teacher_id).filter(
                    Teacher.school_id == self.school_id,
                ).all() if r[0]
            ]
        return owners

    def allows_batch(self, owner_id: Optional[str]) -> bool:
        """OCR 批次归属：本人上传，或校级管理员的本校教师上传。"""
        if not owner_id:
            return False
        if owner_id == self.caller_id:
            return True
        if not self.school_wide:
            return False
        from app.models.database import Teacher

        if not (self.db and self.school_id):
            return False
        return self.db.query(Teacher.teacher_id).filter(
            Teacher.teacher_id == owner_id, Teacher.school_id == self.school_id,
        ).first() is not None

    def allows_exam_class(self, class_id: Optional[str]) -> bool:
        return bool(class_id) and class_id in self.class_ids


# ═══════════════════ 判定 ═══════════════════

def grade(entries: list, key: list, semantic: bool = True, judge=None) -> dict:
    """对一批来源无关的作答执行分层判定。

    Args:
        entries: [{"question_id": str, "answer": str}] 学生作答
        key:     [{"question_id": str, "answer": str}] 答案键
        semantic: False 时主观题不判（needs_semantic 标记返回），交由后台作业
        judge:   语义判定器注入（测试用）；默认批量 LLM 判定

    Returns: {"questions": [...], "correct_count", "total", "pending_semantic"}
        每项 question: {"question_id", "student_answer", "correct_answer",
                        "is_correct", "reason", "needs_semantic"(仅未决时)}
    """
    key_map = {k.get("question_id"): {"answer": k.get("answer") or "",
                                      "choice": k.get("choice")} for k in (key or [])}

    graded, unresolved = [], []
    for e in (entries or []):
        qid = e.get("question_id")
        student_ans = str(e.get("answer") or "")
        kmeta = key_map.get(qid, {})
        correct = kmeta.get("answer", "") if isinstance(kmeta, dict) else kmeta
        q = {
            "question_id": qid,
            "student_answer": student_ans,
            "correct_answer": correct,
            "is_correct": False,
            "reason": "",
        }
        if not correct:
            q["reason"] = NO_KEY_REASON
        elif _compare_answers(student_ans, correct):
            q["is_correct"] = True
            q["reason"] = "归一化精确匹配"
        else:
            # 题型路由：优先答案键显式标记，无元数据回退双边形态启发式
            # （废除单边 _is_choice(学生作答)——Be/HF 等短化学式会被误判为选择题）
            key_choice = kmeta.get("choice") if isinstance(kmeta, dict) else None
            if key_choice is None:
                key_choice = _is_choice(student_ans) and _is_choice(correct)
            if key_choice:
                q["reason"] = "与标准答案不一致"
            else:
                q["needs_semantic"] = True
                unresolved.append(q)
        graded.append(q)

    if unresolved and semantic:
        (judge or _semantic_judge_batch)(unresolved)
        for q in unresolved:
            # 只有真拿到判定才清未决标记；判定失败保留待判定语义（ADR-0013 判定不丢失），
            # 否则一次 LLM 抖动会被下游固化成永久错判
            if q.get("judge_failed"):
                continue
            q.pop("needs_semantic", None)

    return {
        "questions": graded,
        "correct_count": sum(1 for g in graded if g["is_correct"]),
        "total": len(graded),
        "pending_semantic": sum(1 for g in graded if g.get("needs_semantic")),
    }


def judge_semantic(unresolved: list, judge=None) -> None:
    """后台作业入口：对未决主观题补语义判定（原地补全 is_correct/reason）。"""
    (judge or _semantic_judge_batch)(unresolved or [])


# ═══════════════════ 落库 ═══════════════════

def save(db, graded_questions: list, student_id: str, exam_record_id, source: str,
         trigger_diagnosis: bool = True, idempotency_prefix: str = "",
         upsert: bool = False) -> dict:
    """单点写学生作答记录（一切来源共用）。

    - 幂等：answer_id 确定性派生（{prefix|ans}_{student}_{record|free}_{question}），
      重放跳过不重复写；无记录归属的多次独立练习（训练/对话）用 idempotency_prefix
      按会话隔离（如 train_{session} / chat_{session}）。
    - 生效策略：PRACTICE 记录保存即触发诊断作业；EXAM 由确认路径触发；
      无记录归属（chat/training）只落库不诊断。同步/异步两段提交时，
      先行段传 trigger_diagnosis=False，由收尾段（判定齐全后）触发一次。
    """
    from app.models.database import StudentAnswer, Question, ExamRecord, AnswerSource

    source_val = _check_source(source)
    saved, skipped_dup, question_missing = 0, 0, 0

    record_type = None
    if exam_record_id:
        record = db.query(ExamRecord).filter(ExamRecord.record_id == exam_record_id).first()
        if record:
            record_type = record.type.value if hasattr(record.type, "value") else record.type

    for q in (graded_questions or []):
        qid = q.get("question_id")
        if not qid:
            question_missing += 1
            continue
        if not db.query(Question).filter(Question.question_id == qid).first():
            question_missing += 1
            continue
        prefix = idempotency_prefix or "ans"
        answer_id = f"{prefix}_{student_id}_{exam_record_id or 'free'}_{qid}"
        existing = db.query(StudentAnswer).filter(
            StudentAnswer.answer_id == answer_id).first()
        new_answer = str(q.get("student_answer") or "")[:256]
        if existing is not None:
            if upsert and existing.student_answer != new_answer:
                # 练习重做：不同作答覆盖旧判定（作业重放同值走 skip 分支）
                existing.student_answer = new_answer
                existing.is_correct = bool(q.get("is_correct"))
                existing.grade_reason = (q.get("reason") or "")[:256] or None
                saved += 1
            else:
                skipped_dup += 1
            continue
        db.add(StudentAnswer(
            answer_id=answer_id,
            student_id=student_id,
            question_id=qid,
            exam_record_id=exam_record_id,
            student_answer=str(q.get("student_answer") or "")[:256],
            is_correct=bool(q.get("is_correct")),
            grade_reason=(q.get("reason") or "")[:256] or None,
            answer_key=(str(q.get("correct_answer") or "")[:256] or None),
            source=AnswerSource(source_val),
            confirmed=(record_type != "exam"),  # 成绩确认门：考试作答待教师确认
        ))
        saved += 1

    db.commit()

    diagnosis = "未触发"
    if saved and trigger_diagnosis and record_type == "practice":
        diagnosis = _enqueue_diagnosis(exam_record_id)
        notify_graded(db, student_id, exam_record_id)

    if saved and trigger_diagnosis and source_val == "chat":
        # 对话作答回流：学生级诊断（chat 无 exam 归属，走学生维度聚合）
        _enqueue_student_diagnosis(student_id)

    if saved and record_type == "exam":
        # 判卷中心握手：首份考试结果 → grading 态（P4 生命周期）
        try:
            from app.services import exam_lifecycle
            record = db.query(ExamRecord).filter(
                ExamRecord.record_id == exam_record_id).first()
            if record is not None:
                exam_lifecycle.mark_grading(db, record)
        except Exception as e:
            logger.warning("grading handshake failed for %s: %s", exam_record_id, e)

    return {
        "saved": saved,
        "skipped_duplicate": skipped_dup,
        "question_missing": question_missing,
        "record_type": record_type,
        "diagnosis": diagnosis,
    }


def save_batch(db, batch_id: str, exam_id: str, source: str = "ocr", *,
               scope: CallerScope) -> dict:
    """答题卡批量确认保存：该批次全部已批改任务写入作答记录（幂等）。

    scope 必传：考试写入目标按其班级范围校验，答题卡批次按上传者归属校验。
    """
    from app.models.database import StudentAnswer, Student, ExamRecord, Question, AnswerSource
    from app.models.ocr_task import OCRTask

    if not exam_id:
        return {"error": "缺少 exam_id：保存批改结果必须关联一场真实考试"}
    exam = db.query(ExamRecord).filter(ExamRecord.record_id == exam_id).first()
    if not exam:
        return {"error": f"考试记录不存在：{exam_id}，请先导入试卷创建考试"}
    if not scope.allows_exam_class(exam.class_id):
        return {"error": "无权保存到该考试：不在你的班级范围内", "denied": True}

    # 归属校验看该批**全部**任务：按「有批改结果」过滤后再查，空集会把别人的批放进来
    batch_tasks = db.query(OCRTask).filter(OCRTask.batch_id == batch_id).all()
    if any(not scope.allows_batch(t.teacher_id) for t in batch_tasks):
        return {"error": "无权保存该答题卡批次：不是你的批次", "denied": True}
    tasks = [t for t in batch_tasks if t.grading_result]

    saved, skipped_no_student, skipped_dup, question_missing = 0, 0, 0, 0
    details = []
    for task in tasks:
        sid = task.student_id
        if not sid or not task.grading_result:
            skipped_no_student += 1
            details.append({"task_id": task.task_id, "status": "跳过", "reason": "缺少学号或批改结果"})
            continue
        student = db.query(Student).filter(Student.student_id == sid).first()
        if not student or (student.class_id or "") != (exam.class_id or ""):
            # 认出的学号必须落在这场考试的班级里：别班的卷子混进来会污染本场统计与通知
            skipped_no_student += 1
            details.append({
                "task_id": task.task_id, "student_id": sid,
                "status": "跳过", "reason": "学生不存在或不属于本场考试的班级，学号与 roster 不匹配",
            })
            continue

        task_inserted = 0
        for q in task.grading_result.get("questions", []):
            qid = f"{exam_id}_{q['q_number']}"
            if not db.query(Question).filter(Question.question_id == qid).first():
                question_missing += 1
                details.append({
                    "task_id": task.task_id, "question_id": qid,
                    "status": "跳过", "reason": "题目不存在",
                })
                continue
            # 幂等键按 (考试, 学生, 题目) 派生：同一张卡重传（新 task_id）不会写第二行
            answer_id = f"ocr_{sid}_{exam_id}_{q['q_number']}"
            if db.query(StudentAnswer).filter(StudentAnswer.answer_id == answer_id).first():
                skipped_dup += 1
                continue
            db.add(StudentAnswer(
                answer_id=answer_id,
                student_id=sid,
                question_id=qid,
                exam_record_id=exam_id,
                student_answer=str(q.get("student_answer") or "")[:256],
                is_correct=bool(q.get("is_correct")),
                grade_reason=(q.get("reason") or "")[:256] or None,
                # 批改用的是老师粘贴的答案键（优先级高于题库），随行持久化供扫描重判对齐
                answer_key=(str(q.get("correct_answer") or "")[:256] or None),
                source=AnswerSource(source),
                confirmed=True,  # OCR 批保存即教师确认产物
            ))
            task_inserted += 1
        if task_inserted:
            # 只有真写入了作答才算「已确认」——否则匹配不上 roster 的卡会从待确认队列消失
            task.confirmed = True
            student.exercises_completed = (student.exercises_completed or 0) + task_inserted
            saved += 1
            details.append({"task_id": task.task_id, "student_id": sid, "status": "已保存"})
        else:
            details.append({
                "task_id": task.task_id, "student_id": sid,
                "status": "跳过", "reason": "无新增答题记录（均为重复或题目缺失）",
            })
    db.commit()

    diagnosis = "未触发"
    if saved:
        diagnosis = _enqueue_diagnosis(exam_id)
        for d in details:
            if d.get("status") == "已保存" and d.get("student_id"):
                notify_graded(db, d["student_id"], exam_id)

    return {
        "message": f"已保存 {saved}/{len(tasks)} 位学生的答题记录",
        "saved": saved,
        "total": len(tasks),
        "skipped_no_student": skipped_no_student,
        "skipped_duplicate": skipped_dup,
        "question_missing": question_missing,
        "diagnosis": diagnosis,
        "details": details,
    }


# ═══════════════════ 纠偏与统计 ═══════════════════

def override(db, answer_id: str, is_correct: bool, reason: str, teacher_id: str) -> dict:
    """教师改判：更新判定与理由，并以该作答所属记录为单位重触发诊断。"""
    from app.models.database import StudentAnswer

    row = db.query(StudentAnswer).filter(StudentAnswer.answer_id == answer_id).first()
    if not row:
        return {"updated": False, "error": f"作答记录不存在：{answer_id}"}

    row.is_correct = bool(is_correct)
    row.grade_reason = f"教师改判（{teacher_id}）：{reason}"[:256]
    db.commit()

    diagnosis = "未触发"
    if row.exam_record_id:
        diagnosis = _enqueue_diagnosis(row.exam_record_id)
    return {"updated": True, "answer_id": answer_id, "diagnosis": diagnosis}


PENDING_REASON = "PENDING_SEMANTIC"
# 无标准答案 = 未判（不是答错）：照写会把「没批的题」算进成绩与学情
NO_KEY_REASON = "缺少标准答案（未判）"
# 判定未落地（待语义判定/缺标准答案）——统计与读侧的唯一「未判」口径
UNJUDGED_REASONS = (PENDING_REASON, NO_KEY_REASON)


def is_unjudged(reason) -> bool:
    """该理由是否属于「未判定」：不算答错、不进生效行、不计入任何统计。"""
    return reason in UNJUDGED_REASONS


def effective_conditions():
    """生效行过滤（确认门 + 未判排除）——诊断/finalize/错题本/统计共用。"""
    from sqlalchemy import and_, or_
    from app.models.database import StudentAnswer
    return and_(
        StudentAnswer.confirmed.isnot(False),
        or_(StudentAnswer.grade_reason.is_(None),
            StudentAnswer.grade_reason.notin_(list(UNJUDGED_REASONS))),
    )


def is_effective(answer) -> bool:
    """单行生效判定（与 effective_conditions() 同口径）——读侧逐行展示用。"""
    if answer is None:
        return False
    if answer.confirmed is False:
        return False
    return answer.grade_reason not in UNJUDGED_REASONS


def confirm(db, exam_record_id: str) -> dict:
    """教师确认：该考试全部未确认作答翻转为生效，触发一次诊断并通知学生。"""
    from app.models.database import ExamRecord, StudentAnswer
    from app.services import exam_lifecycle

    record = db.query(ExamRecord).filter(ExamRecord.record_id == exam_record_id).first()
    if not record:
        return {"error": f"考试记录不存在：{exam_record_id}"}
    # 终态考试不再确认成绩：翻成生效会把迟到/已作废的作答并进诊断与错题本
    if exam_lifecycle.status_of(record) in ("cancelled", "archived"):
        return {"error": f"考试已{exam_lifecycle.status_of(record)}，不能再确认成绩",
                "denied": True}
    students = [
        r[0] for r in db.query(StudentAnswer.student_id).filter(
            StudentAnswer.exam_record_id == exam_record_id,
            StudentAnswer.confirmed.is_(False),
        ).distinct().all()
    ]
    updated = db.query(StudentAnswer).filter(
        StudentAnswer.exam_record_id == exam_record_id,
        StudentAnswer.confirmed.is_(False),
    ).update({StudentAnswer.confirmed: True}, synchronize_session=False)
    db.commit()
    diagnosis = "未触发"
    if updated:
        diagnosis = _enqueue_diagnosis(exam_record_id)
        for student_id in students:
            notify_graded(db, student_id, exam_record_id)   # 幂等键与落库/扫描共用
    return {"confirmed": updated, "diagnosis": diagnosis}


def finalize(db, exam_record_id: str) -> dict:
    """真实统计：平均正确率/参与人数（exam finalize 端点调用，写入 ExamRecord 统计列）。"""
    from app.models.database import StudentAnswer, ExamRecord

    record = db.query(ExamRecord).filter(ExamRecord.record_id == exam_record_id).first()
    if not record:
        return {"error": f"考试记录不存在：{exam_record_id}"}

    # 先确认后统计：带着未确认作答 finalize 会把平均分/参与人数固化成占位值，
    # 之后 confirm() 只翻确认标记不重算，统计就永久停在 0
    unconfirmed = db.query(StudentAnswer).filter(
        StudentAnswer.exam_record_id == exam_record_id,
        StudentAnswer.confirmed.is_(False),
    ).count()
    if unconfirmed:
        return {"error": f"还有 {unconfirmed} 条作答待教师确认，请先确认成绩再统计"}

    # 已确认但未判定（PENDING_SEMANTIC）的作答同样不进统计：OCR 批保存即 confirmed=True，
    # 老师的自然顺序 save→finalize 会把这些题漏在分母外，判定落定后没有任何路径重算
    unjudged = db.query(StudentAnswer).filter(
        StudentAnswer.exam_record_id == exam_record_id,
        StudentAnswer.grade_reason == PENDING_REASON,
    ).count()
    if unjudged:
        return {"error": f"还有 {unjudged} 条主观题作答判定中，请等判定落定后再统计"}

    rows = db.query(StudentAnswer).filter(
        StudentAnswer.exam_record_id == exam_record_id,
        effective_conditions(),
    ).all()
    students = {r.student_id for r in rows}
    answered = len(rows)
    correct = sum(1 for r in rows if r.is_correct)
    accuracy = round(correct / answered, 4) if answered else 0.0

    # 逐生分布（design Interface：均分/分布/参与）
    per_student = {}
    for r in rows:
        c, t = per_student.get(r.student_id, (0, 0))
        per_student[r.student_id] = (c + (1 if r.is_correct else 0), t + 1)
    distribution = [
        {"student_id": sid, "correct": c, "total": t,
         "accuracy": round(c / t, 4) if t else 0.0}
        for sid, (c, t) in sorted(per_student.items())
    ]

    record.avg_score = accuracy * 100
    record.present_students = len(students)
    db.commit()

    return {
        "exam_record_id": exam_record_id,
        "present_students": len(students),
        "total_students": record.total_students or len(students),
        "answered_count": answered,
        "correct_count": correct,
        "accuracy": accuracy,
        "avg_score": accuracy * 100,
        "distribution": distribution,
    }


def grade_ocr_batch(db, batch_id: str, parsed_answers: list = None, exam_id: str = "",
                    *, scope: CallerScope) -> list:
    """批改一个已完成识别的答题卡批次：判分并把 grading_result 写回任务（供确认保存）。

    Agent 工具 grade_answer_sheets 与 HTTP /grading/grade 的共用编排（ADR-0012）。
    scope 必传：批次归属与（用作答案源的）考试班级都按调用者范围校验。
    """
    from app.models.database import ExamRecord
    from app.models.ocr_task import OCRTask
    from app.services.llm_grading import grade_batch_answers

    # 同上：先按全量任务验归属，再按识别完成过滤（否则别批「没有已完成任务」时漏过闸）
    batch_tasks = db.query(OCRTask).filter(OCRTask.batch_id == batch_id).all()
    if any(not scope.allows_batch(t.teacher_id) for t in batch_tasks):
        return [{"error": "无权批改该答题卡批次：不是你的批次", "denied": True}]
    tasks = [t for t in batch_tasks if t.status == "done"]
    if not tasks:
        return []
    if exam_id:
        exam = db.query(ExamRecord).filter(ExamRecord.record_id == exam_id).first()
        if exam is None:
            return [{"error": f"考试记录不存在：{exam_id}"}]
        if not scope.allows_exam_class(exam.class_id):
            return [{"error": "无权用该考试的答案批改：不在你的班级范围内", "denied": True}]

    results = grade_batch_answers(
        tasks, correct_answers=parsed_answers, exam_id=exam_id or None, db=db,
    )
    grades_by_task = {r["task_id"]: r for r in results}
    for task in tasks:
        if task.task_id in grades_by_task:
            task.grading_result = grades_by_task[task.task_id]
    db.commit()
    return results


def grading_queue(db, scope: CallerScope, batch_id: str = "", exam_id: str = "") -> dict:
    """待判/待确认队列：判卷中心页与 Agent 查询工具共用的读侧。

    注意：主观题语义判定的「判定制中」数量暂不可见（Celery 队列态无落表，
    待 P3 通知/作业表落地后补），本读侧覆盖答题卡待确认、待确认成绩与已保存量。
    scope 必传（identity 由 adapter 从 token 解析）：答题卡批按上传者归属，
    待确认考试按班级范围；空范围读不到任何东西（fail-closed）。
    """
    from app.models.database import ExamRecord, StudentAnswer
    from app.models.ocr_task import OCRTask

    out = {"pending_confirm": [], "unconfirmed_exams": [], "recent_saved": 0}

    # 待确认：已批改未确认的答题卡批
    q = db.query(OCRTask).filter(
        OCRTask.grading_result.isnot(None), OCRTask.confirmed.isnot(True),
    )
    if batch_id:
        q = q.filter(OCRTask.batch_id == batch_id)
    # 归属过滤：空集合（无身份 / 校级但查不到学校）匹配零行，不退化成人人可见
    q = q.filter(OCRTask.teacher_id.in_(scope.visible_batch_owners()))
    batches = {}
    for t in q.all():
        batches.setdefault(t.batch_id, {"batch_id": t.batch_id, "tasks": 0, "exam_id": None})
        batches[t.batch_id]["tasks"] += 1
    out["pending_confirm"] = list(batches.values())

    # 待确认成绩：考试作答落库时 confirmed=False（成绩确认门），教师须看得见、确认得掉
    uq = (
        db.query(StudentAnswer.exam_record_id, StudentAnswer.student_id,
                 ExamRecord.name, ExamRecord.class_id)
        .join(ExamRecord, ExamRecord.record_id == StudentAnswer.exam_record_id)
        .filter(StudentAnswer.confirmed.is_(False))
    )
    if exam_id:
        uq = uq.filter(StudentAnswer.exam_record_id == exam_id)
    uq = uq.filter(ExamRecord.class_id.in_(list(scope.class_ids)))  # 空集 → 空结果（fail-closed）
    exams = {}
    for rid, sid, name, class_id in uq.all():
        e = exams.setdefault(rid, {
            "exam_record_id": rid, "name": name or "", "class_id": class_id or "",
            "answers": 0, "students": set(),
        })
        e["answers"] += 1
        e["students"].add(sid)
    out["unconfirmed_exams"] = [
        {**v, "student_count": len(v["students"])} for _, v in sorted(exams.items())
    ]
    for v in out["unconfirmed_exams"]:
        v.pop("students", None)

    # 已保存作答量（按考试汇总）——同一道闸：范围外的考试一律 0，不做计数探针
    if exam_id:
        exam = db.query(ExamRecord).filter(ExamRecord.record_id == exam_id).first()
        if exam is not None and scope.allows_exam_class(exam.class_id):
            out["recent_saved"] = db.query(StudentAnswer).filter(
                StudentAnswer.exam_record_id == exam_id
            ).count()
    return out


# ═══════════════════ 内部（判定内核承继自 llm_grading）═══════════════════

def _check_source(source: str) -> str:
    s = (source or "online").lower()
    if s not in _VALID_SOURCES:
        raise ValueError(f"非法作答来源: {source}（合法值：{_VALID_SOURCES}）")
    return s


def notify_graded(db, student_id: str, exam_record_id: str) -> None:
    """判卷落库事件挂钩：通知学生成绩已出（失败不阻断判卷主流程）。

    幂等键为「判卷完成×考试」，重复触发（落库 / 扫描作业判定收尾）只落一条。
    """
    try:
        from app.services.notification_service import notification_service
        notification_service.dispatch(
            recipient={"role": "student", "id": student_id},
            event={"type": "grading", "title": "判卷完成",
                   "content": "本次作答已判定完成，可查看结果",
                   "payload": {"exam_record_id": exam_record_id}},
            idempotency_key=f"graded_{exam_record_id}",
            db=db,
        )
    except Exception as e:
        logger.warning("grading notify failed for %s/%s: %s", student_id, exam_record_id, e)


def pending_row(graded_q: dict) -> dict:
    """判定未落地的条目 → 待判定行（落 PENDING_REASON，由扫描作业重判，不固化结论）。"""
    if not graded_q.get("needs_semantic"):
        return graded_q
    row = dict(graded_q)
    row["is_correct"] = False
    row["reason"] = PENDING_REASON
    return row


def capture_chat_answer(db, tool_name: str, problem: str, student_input: str,
                        expected_answer: str, student_id: str):
    """对话作答回流（P5）：分步导学作答的判定与落库。

    条件：学生身份 + 预期答案齐备（调用方校验）；题目 get-or-create 为 chat
    引用题（record_id 空）；幂等键含作答内容摘要——同输入重放单条、换答案
    重做为新记录。返回判定 dict 或 None（未捕获）。
    """
    import hashlib

    from app.models.database import Question, Difficulty, QuestionSource, AuditStatus

    if not (expected_answer or "").strip() or not student_id:
        return None
    try:
        ref = f"chat_{hashlib.sha1(problem.encode('utf-8')).hexdigest()[:16]}"
        question = db.query(Question).filter(Question.question_id == ref).first()
        if not question:
            question = Question(
                question_id=ref, record_id=None, content=problem[:2000],
                options=None, answer=expected_answer, analysis="",
                knowledge_points=[], difficulty=Difficulty.MEDIUM,
                source=QuestionSource.MANUAL_SELECTED,
                audit_status=AuditStatus.PASSED)
            db.add(question)
            try:
                db.commit()
            except Exception:  # 并发首答同题：主键冲突即复用已有行
                db.rollback()
                question = db.query(Question).filter(
                    Question.question_id == ref).first()
                if question is None:
                    return None

        graded = grade(
            [{"question_id": ref, "answer": student_input}],
            [{"question_id": ref, "answer": expected_answer, "choice": False}],
            semantic=True,
        )
        prefix = f"chat_{tool_name}_{hashlib.sha1(student_input.encode('utf-8')).hexdigest()[:8]}"
        rows = [pending_row(q) for q in graded["questions"]]
        out = save(db, rows, student_id, None, "chat",
                   idempotency_prefix=prefix)
        if not out.get("saved"):
            return None
        q = graded["questions"][0]
        if q.get("needs_semantic"):
            # 判定没落地：不能告诉学生「判错了」，行已落待判定交后台重判
            return {"is_correct": None, "pending": True,
                    "reason": "待判定：判定服务暂不可用，稍后自动重判"}
        return {"is_correct": q["is_correct"], "reason": q["reason"]}
    except Exception as e:
        logger.warning("chat capture failed for %s/%s: %s", student_id, tool_name, e)
        return None


DEBOUNCE_SECONDS = 300


def _enqueue_student_diagnosis(student_id: str) -> str:
    """学生级诊断作业（chat 等无 exam 归属作答的聚合入口）——5 分钟去抖。

    判定落库不受去抖影响；窗口内重复捕获只保留一次诊断入队（外部声音 #5）。
    """
    from datetime import datetime as _dt, timedelta
    try:
        from app.models.database import Student, get_db
        db_gen = get_db()
        db = next(db_gen)
        try:
            student = db.query(Student).filter(Student.student_id == student_id).first()
            now = _dt.utcnow()
            if student is None:
                return "未触发"
            last = student.diagnosis_requested_at
            if last and (now - last) < timedelta(seconds=DEBOUNCE_SECONDS):
                return "去抖跳过"
            student.diagnosis_requested_at = now
            db.commit()
        finally:
            db.close()
        from app.jobs import enqueue_job
        enqueue_job("diagnosis_student", {"student_id": student_id})
        return "已触发"
    except Exception as e:
        logger.warning("student diagnosis enqueue failed for %s: %s", student_id, e)
        return f"触发失败: {e}"


def _enqueue_diagnosis(exam_record_id: str) -> str:
    try:
        from app.jobs import enqueue_job
        enqueue_job("diagnosis", {"exam_record_id": exam_record_id})
        return "已触发"
    except Exception as e:  # 诊断失败不阻断保存（与既有行为一致）
        logger.warning("grading_center: diagnosis enqueue failed for %s: %s", exam_record_id, e)
        return f"触发失败: {e}"


# ── Layer-1 归一化（承继 llm_grading，OCR/线上共用）──

def normalized_match(student_ans: str, correct_ans: str) -> bool:
    """公开判卷入口：归一化精确匹配（大小写/空白/化学式形态归一）。"""
    return _compare_answers(student_ans, correct_ans)


def _compare_answers(student_ans: str, correct_ans: str) -> bool:
    if not student_ans or not correct_ans:
        return False
    return _normalize_text(student_ans) == _normalize_text(correct_ans)


_SUB_SCRIPT_MAP = str.maketrans("₀₁₂₃₄₅₆₇₈₉⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻", "01234567890123456789+-")


def _normalize_text(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    try:
        from chem_skills.chemistry_parser.engine.latex_standardizer import standardize_latex_chemical
        text = standardize_latex_chemical(text)
    except Exception:  # standardization is best-effort
        pass
    return "".join(text.upper().translate(_SUB_SCRIPT_MAP).replace("_", "").replace("^", "").split())


def _is_choice(answer: str) -> bool:
    a = (answer or "").strip().upper()
    return bool(a) and len(a) <= 4 and all(ch in "ABCDEFGH" for ch in a)


def answer_key_choice(answer: str, options) -> bool:
    """答案键的题型元数据：有选项且答案是字母选项 → 选择题（其余走语义判定）。

    题库/线上/训练 adapter 手里都有 Question.options，用这个口径喂给 grade()；
    元数据缺失（如老师粘贴的答题卡标准答案）时才回退双边形态启发式。
    """
    return bool(options) and _is_choice(answer)


# ── Layer-2 批量语义判定（承继 llm_grading，≤1 次 LLM 调用）──

def _semantic_judge_batch(unresolved: list) -> None:
    import json

    if not unresolved:
        return
    from app.services.llm_service import llm_service

    # 条目序号是判定结果的引用键：同一道题在同一批次里可以出现多次
    # （整场考试的主观题逐生各一条），按题号引用会让后写覆盖前写、集体判错
    pairs = [
        {
            "i": i,
            "q": q["question_id"],
            "correct": q["correct_answer"],
            "student": q["student_answer"],
        }
        for i, q in enumerate(unresolved)
    ]
    prompt = (
        "你是化学阅卷助手。判断每题学生的答案与标准答案是否语义等价。\n"
        "化学方程式、离子式、计算步骤允许书写形式不同（系数、格式、箭头、上下标），"
        "只要化学意义等价即判对。\n"
        "键盘输入或 OCR 识别会产生 0/O、l/I 混淆（如 H2SO4 被写成 H2S04），"
        "这类纯形式差异不计错。\n"
        f"题目：{json.dumps(pairs, ensure_ascii=False)}\n"
        '只输出 JSON 数组，每项形如 {"i": 条目序号, "equivalent": true/false, "reason": "一句话"}'
    )
    resp = llm_service.generate_text(prompt, temperature=0.0, max_tokens=1200, provider="mimo")
    if not resp.get("success"):
        resp = llm_service.generate_text(prompt, temperature=0.0, max_tokens=1200, provider="auto")
    by_index, by_ref = _parse_judgments(resp.get("content", "")) if resp.get("success") else ({}, {})
    if not by_index and not by_ref:
        logger.warning("grading_center: LLM 语义判定失败，未决题按不一致处理: %s", resp.get("error"))

    seen_qids = {}
    for q in unresolved:
        seen_qids[q["question_id"]] = seen_qids.get(q["question_id"], 0) + 1

    for i, q in enumerate(unresolved):
        j = by_index.get(i)
        if j is None:
            j = by_index.get(str(i))
        if j is None and seen_qids.get(q["question_id"]) == 1:
            # 没回传序号的响应（OCR 卡的历史契约）按题号引用，且仅当题号在批次内唯一
            ref = q["question_id"]
            j = by_ref.get(ref)
            if j is None and isinstance(ref, str) and ref.isdigit():
                j = by_ref.get(int(ref))
        verdict = _strict_bool(j.get("equivalent")) if j is not None else None
        if verdict is not None:
            q["is_correct"] = verdict
            q["reason"] = f"LLM 语义判定：{j.get('reason', '')}"
            q.pop("needs_semantic", None)   # 判定完成 = 不再未决
        else:
            # 判定失败不落库固化——作业侧滤掉，重试时重新判定
            # （含 equivalent 不是布尔的情况："false" 这种字符串不能当真值）
            q["judge_failed"] = True
            q["reason"] = "LLM 判定失败，待重试"


def _strict_bool(value):
    """严格布尔解析：认不出值就返回 None（调用方按判定失败处理，不猜）。"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("true", "yes"):
            return True
        if v in ("false", "no"):
            return False
    elif isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    return None


def _parse_judgments(content: str) -> tuple:
    """解析 LLM 判定数组 → (按条目序号, 按题号引用)。

    两种引用键必须分家：OCR 答题卡用整型题号（1/2/…）当 question_id，
    与条目序号同型，混在一个字典里会把第 0 条的判定套到题号 1 上。
    """
    import re
    import json

    if not content:
        return {}, {}
    text = re.sub(r"^```(?:json)?\s*", "", content.strip())
    text = re.sub(r"\s*```$", "", text).strip()
    data = None
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        m = re.search(r"\[.*\]", text, re.S)
        if m:
            try:
                data = json.loads(m.group(0))
            except (ValueError, TypeError):
                pass
    if not isinstance(data, list):
        return {}, {}
    by_index, by_ref = {}, {}
    for item in data:
        if not isinstance(item, dict):
            continue
        if item.get("i") is not None:
            by_index[item["i"]] = item
        elif item.get("q") is not None:
            by_ref[item["q"]] = item
    return by_index, by_ref

"""
F5: 自适应出题推荐引擎 API
基于PRD v1.0完整版功能规格
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.middleware.auth import PermissionChecker
from app.middleware.scope import RequestScope, ScopeGuard, require_student

from app.models.database import (
    Student, Question, StudentAnswer, ExamRecord,
    get_db, RecordType
)

router = APIRouter()


class PracticeTask(BaseModel):
    """练习任务"""
    practice_id: str
    student_id: str
    student_name: str
    knowledge_points: List[str]
    target_barrier: str  # 目标障碍类型
    question_count: int
    difficulty: str  # AI判断为"稍微超出当前水平"
    deadline: str
    status: str  # pending/completed/overdue
    title: str = ""  # 考试/练习标题（学生端区分展示）
    type: str = "practice"  # exam/practice


class PracticeQuestion(BaseModel):
    """练习题目"""
    question_id: str
    content: str
    options: Optional[List[str]] = None
    estimated_time: int  # 预计用时(分钟)


class StudentPracticeResponse(BaseModel):
    """学生练习响应"""
    practice_id: str
    student_id: str
    knowledge_points: List[str]
    questions: List[PracticeQuestion]
    total_questions: int
    estimated_time: int


class PracticeSubmitRequest(BaseModel):
    """提交练习请求"""
    practice_id: str
    student_id: str
    answers: List[dict]  # [{question_id, answer}]


class PracticeResult(BaseModel):
    """练习结果"""
    practice_id: str
    student_id: str
    correct_count: int
    total_count: int
    accuracy: float
    difficulty_appropriate: bool  # 学生反馈"不太难也不太简单"
    barrier_change: Optional[dict]  # 障碍类型变化
    pending_semantic: int = 0  # 待语义判定的主观题数（异步判定中）


class PracticeAssignRequest(BaseModel):
    """布置练习请求"""
    class_id: str
    knowledge_points: List[str]
    target_barrier: Optional[str] = None  # 概念理解/审题障碍/表述障碍
    question_count: int = 10
    deadline: Optional[str] = None


def _extract_student_answer(ans: dict, question) -> str:
    """从提交项里取学生作答并归一化为大写。

    兼容两代客户端：新版 m/practice.html 发 answer=选项字母；旧版
    （缓存的桌面端页面）发 student_answer=选项下标，仅在选择题且
    下标落在选项范围内时映射为字母，避免吞掉填空题的数字作答。
    """
    raw = str(ans.get("answer") or ans.get("student_answer") or "").strip()
    options = question.options if isinstance(question.options, list) else None
    if options and raw.isdigit() and int(raw) < len(options):
        raw = chr(ord("A") + int(raw))
    return raw.upper()


@router.post("/assign")
async def assign_practice(request: PracticeAssignRequest, db: Session = Depends(get_db),
    current_user: dict = Depends(PermissionChecker("practice", "create")),
):
    """
    布置自适应练习（HTTP adapter —— 业务在 assignment_service，ADR-0012）
    为每个学生根据障碍类型 + 最近发展区 + 薄弱知识点 生成个性化练习（四维机器闸）；
    >5 人自动转后台批次（凭返回的 batch_id 查进度）
    """
    # class_id 在请求体里（ScopeGuard 只看路径参数），就地校验范围
    if not RequestScope.from_user(current_user, db).allows_class(request.class_id):
        raise HTTPException(status_code=403, detail="无权给该班级布置练习")

    from app.services import assignment_service

    students = db.query(Student).filter(Student.class_id == request.class_id).all()
    if not students:
        return {"success": False, "message": "班级无学生"}

    out = assignment_service.assign(
        db, [s.student_id for s in students],
        {"kind": "adaptive",
         "knowledge_points": [k for k in (request.knowledge_points or []) if k],
         "question_count": request.question_count},
    )

    if out["mode"] == "batch":
        return {
            "success": True,
            "practice_id": out["batch_id"],
            "mode": "batch",
            "batch_id": out["batch_id"],
            "total": out["total"],
            "assigned_count": 0,
            "assigned": [],
            "message": f"已开始为 {out['total']} 名学生布置练习（后台批次进行中）",
        }

    assigned = [
        {
            "student_id": r["student_id"],
            "student_name": r["student_name"],
            "record_id": r["record_id"],
            "question_count": r["question_count"],
            "status": r["status"],
            "audit": r.get("audit"),
        }
        for r in out["results"]
    ]
    done = sum(1 for a in assigned if a["status"] == "assigned")
    return {
        "success": True,
        "practice_id": assigned[0]["record_id"] if assigned else "",
        "mode": "sync",
        "assigned_count": done,
        "assigned": assigned,
        "message": f"已为 {done} 名学生布置个性化练习（已落库，学生任务列表可见）",
    }


# 未交卷学生也能看到/继续作答的状态：grading 只是「有人先交了卷」，考试本身没关；
# 真正关闭态（completed/archived）才挡住未交卷的学生，否则同班有人交卷会把全班踢出去
_EXAM_OPEN = ("published", "in_progress", "grading")
_EXAM_HIDDEN = ("draft", "cancelled")             # 无论是否交卷都不出现在学生列表


def _belongs_to(record: ExamRecord, student_id: str) -> bool:
    """逐生布置的卷子（question_stats.student_id 标归属）只归本人；全班卷人人可见。

    归属口径与 daily_practice / assignment_service.progress 一致——否则同班学生
    在任务列表里能拿到别人的个性化练习，取题与提交也一并放行。
    """
    stats = record.question_stats if isinstance(record.question_stats, dict) else {}
    owner = stats.get("student_id")
    return not owner or owner == student_id


def student_tasks(db: Session, student: Student) -> list:
    """学生任务装配的唯一实现（dict 形态）：练习全部可见；考试按生命周期 + 交卷状态。

    已交卷的考试始终可见（grading/completed 属「已完成」分区）——否则学生一提交
    考试就从列表消失，成绩与答卷都无处可看；未交卷时 published/in_progress/grading
    可见（同班有人先交卷不等于考试对其他人关闭），completed/archived 起才挡住未交卷学生，
    draft/cancelled 一律隐藏。tasks 端点与测试共用此装配，杜绝双份过滤逻辑漂移。
    """
    from app.services import exam_lifecycle

    visible = []
    records = db.query(ExamRecord).filter(
        ExamRecord.class_id == student.class_id,
        ExamRecord.type.in_([RecordType.PRACTICE, RecordType.EXAM]),
    ).all()
    for p in records:
        stats = p.question_stats if isinstance(p.question_stats, dict) else {}
        if not _belongs_to(p, student.student_id):
            continue          # 逐生布置的练习只对本人可见（同班他人看不到别人的卷子）
        submitted = db.query(StudentAnswer).filter(
            StudentAnswer.exam_record_id == p.record_id,
            StudentAnswer.student_id == student.student_id,
        ).count() > 0
        if p.type == RecordType.EXAM:
            status = exam_lifecycle.status_of(p)
            if status in _EXAM_HIDDEN:
                continue
            if status not in _EXAM_OPEN and not submitted:
                continue
        question_count = db.query(Question).filter(
            Question.record_id == p.record_id).count() or stats.get("question_count", 0)
        if isinstance(stats, dict) and "knowledge_points" in stats:
            knowledge_points = stats.get("knowledge_points", [])
        else:
            knowledge_points = []

        visible.append({
            "practice_id": p.record_id,
            "title": p.name or "",
            "type": "exam" if p.type == RecordType.EXAM else "practice",
            "question_count": question_count,
            "submitted": submitted,
            "knowledge_points": knowledge_points,
            "deadline": p.exam_date.strftime("%Y-%m-%d %H:%M") if p.exam_date else "",
        })
    return visible


# 兼容别名（既有测试引用）
_student_visible_tasks = student_tasks


@router.get("/student/{student_id}/tasks")
async def get_student_practice_tasks(student_id: str, db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("practice", "read", allow_self=True)),
    _scope: None = Depends(ScopeGuard("student_id", kind="student")),
):
    """
    获取学生今日练习任务
    """
    try:
        # 查询学生的练习记录
        student = db.query(Student).filter(Student.student_id == student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail=f"学生 {student_id} 不存在")

        # 任务装配唯一实现（考试按生命周期状态过滤 + title/type 区分）
        tasks = [
            PracticeTask(
                practice_id=t["practice_id"],
                student_id=student_id,
                student_name=student.name,
                knowledge_points=t["knowledge_points"],
                target_barrier="concept",
                question_count=t["question_count"],
                difficulty="medium",
                deadline=t["deadline"],
                status="completed" if t["submitted"] else "pending",
                title=t["title"],
                type=t["type"],
            )
            for t in student_tasks(db, student)
        ]

        return {
            "student_id": student_id,
            "student_name": student.name,
            "tasks": tasks
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取练习任务失败: {str(e)}")


@router.get("/student/{student_id}/practice/{practice_id}", response_model=StudentPracticeResponse)
async def get_practice_content(student_id: str, practice_id: str,
    current_user: dict = Depends(PermissionChecker("practice", "read", allow_self=True)),
    db: Session = Depends(get_db),
    _scope: None = Depends(ScopeGuard("student_id", kind="student")),
):
    """
    获取练习内容
    """
    # 查询练习记录
    practice = db.query(ExamRecord).filter(
        ExamRecord.record_id == practice_id
    ).first()

    if not practice:
        raise HTTPException(status_code=404, detail=f"练习记录 {practice_id} 不存在")

    from app.services import exam_lifecycle

    # 查询学生已完成的答题
    completed_answers = db.query(StudentAnswer).filter(
        StudentAnswer.exam_record_id == practice_id,
        StudentAnswer.student_id == student_id
    ).all()

    if not RequestScope.from_user(current_user, db).allows_class(practice.class_id):
        raise HTTPException(status_code=404, detail=f"练习记录 {practice_id} 不存在")
    if not _belongs_to(practice, student_id):
        raise HTTPException(status_code=404, detail=f"练习记录 {practice_id} 不存在")

    # 考试按学生维度放行（不泄漏未交卷考试的存在）：
    #   已交卷 → 回看整卷（考试一次性提交，不可能再作答）；
    #   未交卷 → 开放态（published/in_progress/grading）继续作答；其余关闭态 404。
    reviewing_submitted = False
    if practice.type == RecordType.EXAM:
        status = exam_lifecycle.status_of(practice)
        if status in _EXAM_HIDDEN:
            raise HTTPException(status_code=404, detail=f"练习记录 {practice_id} 不存在")
        if status not in _EXAM_OPEN and not completed_answers:
            raise HTTPException(status_code=404, detail=f"练习记录 {practice_id} 不存在")
        if completed_answers:
            reviewing_submitted = True
        else:
            exam_lifecycle.mark_started(db, practice)
            db.commit()

    # 查询练习题目
    questions = db.query(Question).filter(
        Question.record_id == practice_id
    ).all()

    completed_question_ids = {a.question_id for a in completed_answers}

    # 取题只给未完成的题目；已交卷的回看给整卷（响应不含标准答案）
    pending_questions = (
        questions if reviewing_submitted
        else [q for q in questions if q.question_id not in completed_question_ids]
    )

    return StudentPracticeResponse(
        practice_id=practice_id,
        student_id=student_id,
        knowledge_points=(
            practice.question_stats.get("knowledge_points", [])
            if isinstance(practice.question_stats, dict)
            else []
        ),
        questions=[
            PracticeQuestion(
                question_id=q.question_id,
                content=q.content,
                options=q.options,
                estimated_time=3
            )
            for q in pending_questions
        ],
        total_questions=len(questions),
        estimated_time=len(pending_questions) * 3
    )


@router.post("/submit", response_model=PracticeResult)
async def submit_practice(request: PracticeSubmitRequest, db: Session = Depends(get_db),
    current_user: dict = Depends(PermissionChecker("practice", "create", allow_self=True)),
):
    """
    提交练习答案
    选择题同步判（当场出分）；主观题（填空/计算/简答）入后台队列做 LLM 语义判定，
    学生见「主观题待判定」。落库与诊断经判卷中心单点完成。
    """
    # allow_self 的契约：student_id 在请求体里（ScopeGuard 够不着），就地校验范围
    require_student(current_user, db, request.student_id)
    try:
        from app.services import grading_center

        student = db.query(Student).filter(Student.student_id == request.student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail=f"学生 {request.student_id} 不存在")

        # 记录归属：practice_id 在请求体里，按它所属班级收窄（不能拿别校考试来落库）
        practice_record = db.query(ExamRecord).filter(
            ExamRecord.record_id == request.practice_id).first()
        if practice_record is None:
            raise HTTPException(status_code=404, detail=f"练习记录 {request.practice_id} 不存在")
        if not RequestScope.from_user(current_user, db).allows_class(practice_record.class_id):
            raise HTTPException(status_code=403, detail="无权提交该练习")
        if not _belongs_to(practice_record, request.student_id):
            raise HTTPException(status_code=403, detail="无权提交该练习")
        if practice_record.type == RecordType.EXAM:
            from app.services import exam_lifecycle
            # 写侧与读侧同一收口：关闭态（completed/archived/draft/cancelled）不再收卷，
            # 否则迟交答案会被 confirm 翻成生效并并入已完成的统计
            if exam_lifecycle.status_of(practice_record) not in _EXAM_OPEN:
                raise HTTPException(status_code=400, detail="该考试已结束，无法提交作答")
            if exam_lifecycle.exam_already_submitted(
                    db, request.practice_id, request.student_id):
                raise HTTPException(status_code=400, detail="该考试已提交过作答")

        # 线上 adapter：请求项 → 来源无关作答；答案键来自题库题目
        questions = {
            q.question_id: q
            for q in db.query(Question).filter(
                Question.record_id == request.practice_id
            ).all()
        }
        entries, key = [], []
        for ans in request.answers:
            q = questions.get(ans.get("question_id"))
            if not q:
                continue
            entries.append({
                "question_id": q.question_id,
                "answer": _extract_student_answer(ans, q),
            })
            key.append({
                "question_id": q.question_id,
                "answer": q.answer,
                "choice": grading_center.answer_key_choice(q.answer, q.options),
            })

        # Layer-1 同步判定（语义判定延迟到后台作业）
        graded = grading_center.grade(entries, key, semantic=False)
        resolved = [q for q in graded["questions"] if not q.get("needs_semantic")]

        # 主观题入队列做批量语义判定（先于 save 计算触发策略）
        pending = [
            {"question_id": q["question_id"], "student_answer": q["student_answer"],
             "correct_answer": q["correct_answer"]}
            for q in graded["questions"] if q.get("needs_semantic")
        ]

        # 判卷中心单点落库（幂等）；有主观题在途时由收尾的异步作业触发一次诊断
        grading_center.save(db, resolved, request.student_id, request.practice_id, "online",
                            trigger_diagnosis=not pending, upsert=True)

        # 主观题立即落 PENDING 行（ADR-0013 落行+消费：判定永不丢失、提交不阻塞）
        if pending:
            pending_rows = [
                {"question_id": p_["question_id"], "student_answer": p_["student_answer"],
                 "is_correct": False, "reason": grading_center.PENDING_REASON}
                for p_ in pending
            ]
            grading_center.save(db, pending_rows, request.student_id,
                                request.practice_id, "online",
                                trigger_diagnosis=False, upsert=True)
            # 快速消费：有 Redis 走 Celery；broker 不可达时静默交给 APScheduler 周期扫描
            # （不再同步降级内联跑 LLM——消灭提交阻塞，外部声音 #6）
            try:
                from app.jobs.tasks import semantic_grading_task
                semantic_grading_task.delay(request.practice_id)
            except Exception:
                pass

        # 更新学生练习完成数（一次提交计一次）
        student.exercises_completed = (student.exercises_completed or 0) + 1
        student.last_exercise_at = datetime.utcnow()
        db.commit()

        total_count = graded["total"]
        correct_count = graded["correct_count"]
        accuracy = correct_count / total_count if total_count > 0 else 0

        current_barrier = (
            dict(student.barrier_type)
            if isinstance(student.barrier_type, dict)
            else None
        )

        return PracticeResult(
            practice_id=request.practice_id,
            student_id=request.student_id,
            correct_count=correct_count,
            total_count=total_count,
            accuracy=round(accuracy, 2),
            difficulty_appropriate=0.4 <= accuracy <= 0.8,
            barrier_change=current_barrier,
            pending_semantic=graded["pending_semantic"],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提交失败: {str(e)}")


@router.get("/effect/{student_id}")
async def get_practice_effect(student_id: str, db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("practice", "read")),
    _scope: None = Depends(ScopeGuard("student_id", kind="student")),
):
    """
    查看自适应练习效果
    """
    # 查询学生历史练习
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"学生 {student_id} 不存在")

    # 查询该学生的练习记录
    practices = db.query(ExamRecord).filter(
        ExamRecord.class_id == student.class_id,
        ExamRecord.type == RecordType.PRACTICE
    ).order_by(ExamRecord.exam_date).all()

    if len(practices) < 2:
        return {
            "student_id": student_id,
            "message": "练习数据不足，无法评估效果"
        }

    # 计算最近两次练习的正确率对比
    latest = practices[-1]
    previous = practices[-2]

    from app.services.grading_center import effective_conditions

    latest_answers = db.query(StudentAnswer).filter(
        StudentAnswer.exam_record_id == latest.record_id,
        StudentAnswer.student_id == student_id,
        effective_conditions(),
    ).all()

    previous_answers = db.query(StudentAnswer).filter(
        StudentAnswer.exam_record_id == previous.record_id,
        StudentAnswer.student_id == student_id,
        effective_conditions(),
    ).all()

    latest_correct = sum(1 for a in latest_answers if a.is_correct)
    previous_correct = sum(1 for a in previous_answers if a.is_correct)

    latest_accuracy = latest_correct / len(latest_answers) if latest_answers else 0
    previous_accuracy = previous_correct / len(previous_answers) if previous_answers else 0

    improvement = latest_accuracy - previous_accuracy

    return {
        "student_id": student_id,
        "student_name": student.name,
        "improvement": {
            "before_practice_date": previous.exam_date.strftime("%Y-%m-%d") if previous.exam_date else None,
            "before_accuracy": round(previous_accuracy, 2),
            "after_practice_date": latest.exam_date.strftime("%Y-%m-%d") if latest.exam_date else None,
            "after_accuracy": round(latest_accuracy, 2),
            "improvement_rate": round(improvement, 2) if improvement != 0 else 0
        }
    }


@router.post("/push/daily")
async def push_daily_practice(db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("practice", "create")),
):
    """
    手动触发每日练习推送（供教师操作）
    """
    from app.services.notification_service import send_practice_notification

    # 获取所有学生
    students = db.query(Student).filter(Student.status == "approved").all()

    pushed_students = 0
    pushed_parents = 0

    for student in students:
        # 获取今日练习
        from datetime import datetime
        today = datetime.utcnow().date()

        practice = db.query(ExamRecord).filter(
            ExamRecord.class_id == student.class_id,
            ExamRecord.type == RecordType.PRACTICE,
            ExamRecord.exam_date >= datetime.combine(today, datetime.min.time())
        ).first()

        if practice:
            # 更新学生最后练习时间
            student.last_exercise_at = datetime.utcnow()
            pushed_students += 1

            # 发送通知给家长
            sent = send_practice_notification(student.student_id, practice.name)
            pushed_parents += sent

    db.commit()

    return {
        "success": True,
        "message": f"已推送 {pushed_students} 名学生的练习任务，发送 {pushed_parents} 条家长通知"
    }


# ============================================================
# P5-3: 练习模块补充端点
# ============================================================


@router.get("/{practice_id}/questions")
async def get_practice_questions(
    practice_id: str,
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("practice", "read")),
    _scope: None = Depends(ScopeGuard("practice_id", kind="exam_record")),
):
    """获取指定练习的题目列表"""
    practice = db.query(ExamRecord).filter(ExamRecord.record_id == practice_id).first()
    if not practice:
        raise HTTPException(status_code=404, detail=f"练习记录 {practice_id} 不存在")


    questions = db.query(Question).filter(Question.record_id == practice_id).all()

    return {
        "success": True,
        "practice_id": practice_id,
        "practice_name": practice.name,
        "total_questions": len(questions),
        "questions": [
            {
                "question_id": q.question_id,
                "content": q.content,
                "options": q.options,
                "answer": q.answer,
                "analysis": q.analysis,
                "knowledge_points": q.knowledge_points,
                "difficulty": q.difficulty.value if hasattr(q.difficulty, 'value') else q.difficulty
            }
            for q in questions
        ]
    }


@router.get("/history/{student_id}")
async def get_practice_history(
    student_id: str,
    limit: int = 20,
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("practice", "read", allow_self=True)),
    _scope: None = Depends(ScopeGuard("student_id", kind="student")),
):
    """获取学生练习历史"""
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"学生 {student_id} 不存在")

    # 查询该学生的练习记录（限本班：别校练习既不该出现在历史里，也不该泄漏存在性）
    practices = db.query(ExamRecord).filter(
        ExamRecord.type == RecordType.PRACTICE,
        ExamRecord.class_id == student.class_id,
    ).order_by(ExamRecord.exam_date.desc()).limit(limit).all()

    from app.services.grading_center import is_effective

    history = []
    for p in practices:
        answers = db.query(StudentAnswer).filter(
            StudentAnswer.exam_record_id == p.record_id,
            StudentAnswer.student_id == student_id
        ).all()

        # 待判定/缺标准答案/待确认的行不是成绩：不计入正确率，只报待判定数
        judged = [a for a in answers if is_effective(a)]
        correct = sum(1 for a in judged if a.is_correct)
        total = len(judged)

        history.append({
            "practice_id": p.record_id,
            "name": p.name,
            "date": p.exam_date.strftime("%Y-%m-%d %H:%M") if p.exam_date else None,
            "total_questions": total,
            "correct_count": correct,
            "accuracy": round(correct / total, 2) if total > 0 else 0,
            "pending_count": len(answers) - total,
            "status": "completed" if total > 0 else "pending"
        })

    return {
        "success": True,
        "student_id": student_id,
        "student_name": student.name,
        "history": history
    }


# ── wrong/list, wrong/master, review/list, historical 已迁至 practice_wrong.py ──


# ── 学生练习统计（design-upgrade #16：学生端游戏化数据源；streak 口径与 parent weekly 一致）──
@router.get("/student/{student_id}/stats")
async def get_student_practice_stats(
    student_id: str,
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("practice", "read", allow_self=True)),
):
    """学生自己的练习统计（累计答题/正确率/本周练习/连续打卡天数）。

    ADR-0008：学生本人可读自身数据；教师经 permission 矩阵可读。
    streak 口径与 app/api/parent.py get_child_weekly 保持一致：
    今天有答题则从今天回数连续天数，否则从昨天回数。
    """
    from datetime import timedelta

    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    total_answers = db.query(func.count(StudentAnswer.answer_id)).filter(
        StudentAnswer.student_id == student_id
    ).scalar() or 0

    correct_answers = db.query(func.count(StudentAnswer.answer_id)).filter(
        StudentAnswer.student_id == student_id,
        StudentAnswer.is_correct.is_(True),
    ).scalar() or 0

    week_start = datetime.utcnow() - timedelta(days=7)
    week_practice_count = db.query(func.count(StudentAnswer.answer_id)).filter(
        StudentAnswer.student_id == student_id,
        StudentAnswer.answered_at >= week_start,
    ).scalar() or 0

    # 连续打卡：取全部答题日期集合，从今天（或昨天）向前数连续天数
    streak_days = 0
    try:
        dates = db.query(StudentAnswer.answered_at).filter(
            StudentAnswer.student_id == student_id
        ).order_by(StudentAnswer.answered_at.desc()).limit(400).all()
        streak_set = set()
        for (answered_at,) in dates:
            if answered_at:
                d = answered_at.date() if hasattr(answered_at, "date") else answered_at
                streak_set.add(d)
        today = datetime.utcnow().date()
        check = today if today in streak_set else today - timedelta(days=1)
        while check in streak_set:
            streak_days += 1
            check -= timedelta(days=1)
    except Exception:
        streak_days = 0

    return {
        "success": True,
        "student_id": student_id,
        "total_answers": total_answers,
        "accuracy": round(correct_answers / total_answers, 2) if total_answers > 0 else 0,
        "week_practice_count": week_practice_count,
        "streak_days": streak_days,
    }

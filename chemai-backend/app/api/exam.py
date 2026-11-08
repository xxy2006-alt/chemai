"""
考试管理 API
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.database import (
    ExamRecord,
    Class,
    Student,
    StudentAnswer,
    Question,
    get_db,
    RecordType,
    Difficulty,
    QuestionSource,
    AuditStatus,
)
from app.middleware.auth import PermissionChecker
from app.middleware.scope import RequestScope, ScopeGuard
router = APIRouter()


class ExamCreateRequest(BaseModel):
    """创建考试请求"""
    class_id: str
    name: str
    exam_date: Optional[datetime] = None


class ExamResponse(BaseModel):
    """考试响应"""
    record_id: str
    class_id: str
    name: str
    type: str
    total_students: int
    present_students: int
    avg_score: Optional[float] = None
    exam_date: Optional[datetime] = None


@router.post("/create")
async def create_exam(
    request: ExamCreateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(PermissionChecker("exam", "create")),
):
    """创建新考试记录"""
    # class_id 在请求体里（不在路径上），ScopeGuard 只看路径参数 —— 就地校验范围
    if not RequestScope.from_user(current_user, db).allows_class(request.class_id):
        raise HTTPException(status_code=403, detail="无权在该班级创建考试")

    # 验证班级存在
    class_obj = db.query(Class).filter(Class.class_id == request.class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail=f"班级 {request.class_id} 不存在")

    # 获取学生数量
    total_students = db.query(Student).filter(Student.class_id == request.class_id).count()

    # 创建考试记录
    record_id = f"exam_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    exam_record = ExamRecord(
        record_id=record_id,
        class_id=request.class_id,
        name=request.name,
        type=RecordType.EXAM,
        total_students=total_students,
        present_students=0,
        exam_date=request.exam_date or datetime.now()
    )

    db.add(exam_record)
    db.commit()
    db.refresh(exam_record)

    return {
        "success": True,
        "record_id": exam_record.record_id,
        "class_id": exam_record.class_id,
        "name": exam_record.name,
        "type": exam_record.type.value if exam_record.type else "exam",
        "total_students": exam_record.total_students or 0,
        "present_students": exam_record.present_students or 0,
        "avg_score": exam_record.avg_score,
        "exam_date": exam_record.exam_date.isoformat() if exam_record.exam_date else None
    }


@router.get("/list/{class_id}")
async def list_exams(
    class_id: str,
    db: Session = Depends(get_db),
    _scope: None = Depends(ScopeGuard("class_id", kind="class")),
):
    """获取班级考试列表"""
    # 验证班级存在
    class_obj = db.query(Class).filter(Class.class_id == class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail=f"班级 {class_id} 不存在")

    # 查询考试记录
    exams = db.query(ExamRecord).filter(
        ExamRecord.class_id == class_id
    ).order_by(ExamRecord.created_at.desc()).all()

    return {
        "success": True,
        "class_id": class_id,
        "class_name": class_obj.name,
        "total_exams": len(exams),
        "exams": [
            {
                "record_id": e.record_id,
                "name": e.name,
                "total_students": e.total_students or 0,
                "present_students": e.present_students or 0,
                "avg_score": e.avg_score,
                "exam_date": e.exam_date.strftime("%Y-%m-%d") if e.exam_date else None,
                "question_stats": e.question_stats
            }
            for e in exams
        ]
    }


@router.get("/{exam_record_id}")
async def get_exam(
    exam_record_id: str,
    db: Session = Depends(get_db),
    _scope: None = Depends(ScopeGuard("exam_record_id", kind="exam_record")),
):
    """获取考试详情"""
    exam = db.query(ExamRecord).filter(ExamRecord.record_id == exam_record_id).first()

    if not exam:
        raise HTTPException(status_code=404, detail=f"考试记录 {exam_record_id} 不存在")

    return {
        "record_id": exam.record_id,
        "class_id": exam.class_id,
        "name": exam.name,
        "type": exam.type.value,
        "total_students": exam.total_students or 0,
        "present_students": exam.present_students or 0,
        "avg_score": exam.avg_score,
        "exam_date": exam.exam_date.strftime("%Y-%m-%d") if exam.exam_date else None,
        "question_stats": exam.question_stats
    }


@router.post("/{exam_record_id}/finalize")
async def finalize_exam(
    exam_record_id: str,
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("exam", "update")),
    _scope: None = Depends(ScopeGuard("exam_record_id", kind="exam_record")),
):
    """完成考试录入，更新统计信息（统计由判卷中心基于已保存作答计算）"""
    exam = db.query(ExamRecord).filter(ExamRecord.record_id == exam_record_id).first()

    if not exam:
        raise HTTPException(status_code=404, detail=f"考试记录 {exam_record_id} 不存在")

    from app.services import exam_lifecycle, grading_center

    # 迁移被拒（draft/cancelled/archived）必须在统计落库之前拦下：finalize 自己 commit，
    # 先统计后迁移会让「统计已写、状态没动」的响应仍报 success（同 cancel/publish 的 400 口径）
    if not exam_lifecycle.can_transition(exam, "completed"):
        raise HTTPException(
            status_code=400,
            detail=f"当前状态不允许完成录入（现状态：{exam_lifecycle.status_of(exam)}）")

    stats = grading_center.finalize(db, exam_record_id)
    if stats.get("error"):
        raise HTTPException(status_code=400, detail=stats["error"])

    # 收卷握手：grading（或已发布/进行中收卷）→ completed
    # transition 的事务边界归调用方（ADR-0012），这里必须提交，否则状态迁移被回滚
    exam_lifecycle.mark_completed_on_finalize(db, exam)
    db.commit()

    return {
        "success": True,
        "record_id": exam_record_id,
        "status": exam_lifecycle.status_of(exam),
        "present_students": stats["present_students"],
        "avg_score": round(stats["avg_score"], 1),
        "accuracy": stats["accuracy"]
    }


@router.post("/{exam_record_id}/cancel")
async def cancel_exam(
    exam_record_id: str,
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("exam", "update")),
    _scope: None = Depends(ScopeGuard("exam_record_id", kind="exam_record")),
):
    """取消考试（任意非终态 → cancelled；终态拒绝）"""
    exam = db.query(ExamRecord).filter(ExamRecord.record_id == exam_record_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail=f"考试记录 {exam_record_id} 不存在")

    from app.services import exam_lifecycle
    if not exam_lifecycle.transition(db, exam, "cancelled"):
        raise HTTPException(status_code=400,
                            detail=f"当前状态不允许取消（现状态：{exam_lifecycle.status_of(exam)}）")
    db.commit()
    return {"success": True, "record_id": exam_record_id, "status": "cancelled"}


@router.post("/{exam_record_id}/confirm")
async def confirm_exam(
    exam_record_id: str,
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("exam", "update")),
    _scope: None = Depends(ScopeGuard("exam_record_id", kind="exam_record")),
):
    """教师确认：该考试 AI 判定成绩批量生效并触发诊断（成绩确认门）"""
    from app.services import grading_center
    out = grading_center.confirm(db, exam_record_id)
    if out.get("error"):
        # 状态拒绝（已取消/已归档）是 400：记录存在，只是当前态不允许再确认
        raise HTTPException(status_code=400 if out.get("denied") else 404,
                            detail=out["error"])
    return {"success": True, "record_id": exam_record_id, **out}


# ============================================================
# P5-2: 考试管理补充端点
# ============================================================


class ExamUpdateRequest(BaseModel):
    """更新考试请求"""
    name: Optional[str] = None
    exam_date: Optional[datetime] = None


@router.put("/{exam_id}")
async def update_exam(
    exam_id: str,
    request: ExamUpdateRequest,
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("exam", "update")),
    _scope: None = Depends(ScopeGuard("exam_id", kind="exam_record")),
):
    """更新考试信息（名称、日期等）"""
    exam = db.query(ExamRecord).filter(ExamRecord.record_id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail=f"考试记录 {exam_id} 不存在")

    if request.name is not None:
        exam.name = request.name
    if request.exam_date is not None:
        exam.exam_date = request.exam_date

    db.commit()
    db.refresh(exam)

    return {
        "success": True,
        "record_id": exam.record_id,
        "name": exam.name,
        "exam_date": exam.exam_date.strftime("%Y-%m-%d") if exam.exam_date else None
    }


@router.delete("/{exam_id}")
async def delete_exam(
    exam_id: str,
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("exam", "delete")),
    _scope: None = Depends(ScopeGuard("exam_id", kind="exam_record")),
):
    """删除考试及相关数据（题目、答题记录）"""
    exam = db.query(ExamRecord).filter(ExamRecord.record_id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail=f"考试记录 {exam_id} 不存在")

    # 删除关联的学生答题记录
    db.query(StudentAnswer).filter(StudentAnswer.exam_record_id == exam_id).delete()
    # 删除关联的题目
    db.query(Question).filter(Question.record_id == exam_id).delete()
    # 删除考试记录
    db.delete(exam)
    db.commit()

    return {"success": True, "message": f"考试 {exam_id} 已删除"}


@router.get("/{exam_id}/result/{student_id}")
async def get_student_exam_result(
    exam_id: str,
    student_id: str,
    db: Session = Depends(get_db),
    _scope_exam: None = Depends(ScopeGuard("exam_id", kind="exam_record")),
    _scope_student: None = Depends(ScopeGuard("student_id", kind="student")),
):
    """获取单个学生在某次考试中的结果详情"""
    exam = db.query(ExamRecord).filter(ExamRecord.record_id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail=f"考试记录 {exam_id} 不存在")

    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"学生 {student_id} 不存在")

    # 查询该学生的答题记录
    answers = db.query(StudentAnswer).filter(
        StudentAnswer.exam_record_id == exam_id,
        StudentAnswer.student_id == student_id
    ).all()

    # 查询考试题目
    questions = db.query(Question).filter(Question.record_id == exam_id).all()
    question_map = {q.question_id: q for q in questions}

    question_results = []
    correct_count = 0
    total_score = 0

    for ans in answers:
        q = question_map.get(ans.question_id)
        kps = q.knowledge_points if q else []
        if ans.is_correct:
            correct_count += 1
            total_score += 1

        question_results.append({
            "question_id": ans.question_id,
            "content": q.content if q else "",
            "options": q.options if q else None,
            "answer": q.answer if q else "",
            "analysis": q.analysis if q else "",
            "knowledge_points": kps,
            "your_answer": ans.student_answer,
            "is_correct": ans.is_correct,
            "barrier_type": ans.barrier_type.value if ans.barrier_type else None
        })

    total = len(answers)
    accuracy = round(correct_count / total, 2) if total > 0 else 0

    return {
        "success": True,
        "exam_id": exam_id,
        "exam_name": exam.name,
        "student_id": student_id,
        "student_name": student.name,
        "total_questions": total,
        "correct_count": correct_count,
        "accuracy": accuracy,
        "score": round(accuracy * 100, 1),
        "questions": question_results
    }


# ============================================================
# redesign-4: 考试工作台 — 选题 / 发布 / 结果
# ============================================================

class AddQuestionsRequest(BaseModel):
    """批量添加题目请求"""
    question_ids: List[str]


@router.post("/{exam_id}/questions")
async def add_questions_to_exam(
    exam_id: str,
    request: AddQuestionsRequest,
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("exam", "update")),
    _scope: None = Depends(ScopeGuard("exam_id", kind="exam_record")),
):
    """批量将已有题目关联到考试（同时支持题库题目和历史真题）"""
    exam = db.query(ExamRecord).filter(ExamRecord.record_id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail=f"考试记录 {exam_id} 不存在")

    from app.services.exam_bank import exam_bank_service
    updated = 0
    for qid in request.question_ids:
        q = db.query(Question).filter(Question.question_id == qid).first()
        if q:
            q.record_id = exam_id
            updated += 1
        else:
            # 尝试从历史真题库查找
            hq = exam_bank_service.get_by_exam_id(qid)
            if hq:
                q = Question(
                    question_id=qid,
                    record_id=exam_id,
                    content=hq.content,
                    options=hq.options,
                    answer=hq.answer,
                    analysis=hq.analysis or "",
                    knowledge_points=hq.knowledge_points,
                    difficulty=Difficulty.coerce(hq.difficulty),
                    source=QuestionSource.MANUAL_SELECTED,
                    source_exam=hq.source,
                    audit_status=AuditStatus.PASSED
                )
                db.add(q)
                updated += 1

    db.commit()
    return {"success": True, "updated": updated, "total": len(request.question_ids)}


@router.get("/{exam_id}/questions")
async def get_exam_questions(
    exam_id: str,
    db: Session = Depends(get_db),
    _scope: None = Depends(ScopeGuard("exam_id", kind="exam_record")),
):
    """获取考试关联的题目列表"""
    exam = db.query(ExamRecord).filter(ExamRecord.record_id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail=f"考试记录 {exam_id} 不存在")

    questions = db.query(Question).filter(Question.record_id == exam_id).all()
    return {
        "exam_id": exam_id,
        "exam_name": exam.name,
        "total": len(questions),
        "questions": [
            {
                "question_id": q.question_id,
                "content": q.content,
                "options": q.options,
                "answer": q.answer,
                "analysis": q.analysis,
                "knowledge_points": q.knowledge_points,
                "difficulty": q.difficulty if q.difficulty is not None else None,
                "source": q.source.value if q.source else None
            }
            for q in questions
        ]
    }


@router.delete("/{exam_id}/questions/{question_id}")
async def remove_question_from_exam(
    exam_id: str,
    question_id: str,
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("exam", "delete")),
    _scope: None = Depends(ScopeGuard("exam_id", kind="exam_record")),
):
    """从考试中移除题目"""
    q = db.query(Question).filter(
        Question.question_id == question_id,
        Question.record_id == exam_id
    ).first()
    if not q:
        raise HTTPException(status_code=404, detail="题目不在该考试中")

    q.record_id = None
    db.commit()
    return {"success": True, "message": "题目已移除"}


@router.post("/{exam_id}/publish")
async def publish_exam(
    exam_id: str,
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("exam", "update")),
    _scope: None = Depends(ScopeGuard("exam_id", kind="exam_record")),
):
    """发布考试"""
    exam = db.query(ExamRecord).filter(ExamRecord.record_id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail=f"考试记录 {exam_id} 不存在")

    questions = db.query(Question).filter(Question.record_id == exam_id).count()
    if questions == 0:
        raise HTTPException(status_code=400, detail="考试没有题目，无法发布")

    # 生命周期：draft → published（非法迁移拒绝，如重复发布/已收卷）
    from app.services import exam_lifecycle
    if not exam_lifecycle.transition(db, exam, "published"):
        raise HTTPException(status_code=400,
                            detail=f"当前状态不允许发布（现状态：{exam_lifecycle.status_of(exam)}）")

    # question_stats 标志保留（兼容旧读侧/导出）
    stats = exam.question_stats or {}
    stats["published"] = True
    stats["published_at"] = datetime.now().isoformat()
    stats["question_count"] = questions
    exam.question_stats = stats

    exam.total_students = db.query(Student).filter(Student.class_id == exam.class_id).count()
    db.commit()
    return {
        "success": True,
        "exam_id": exam_id,
        "exam_name": exam.name,
        "published": True,
        "status": "published",
        "question_count": questions,
        "total_students": exam.total_students
    }


@router.get("/{exam_id}/results")
async def get_exam_results(
    exam_id: str,
    db: Session = Depends(get_db),
    _scope: None = Depends(ScopeGuard("exam_id", kind="exam_record")),
):
    """获取考试结果总览（所有学生）"""
    exam = db.query(ExamRecord).filter(ExamRecord.record_id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail=f"考试记录 {exam_id} 不存在")

    questions = db.query(Question).filter(Question.record_id == exam_id).all()
    students = db.query(Student).filter(Student.class_id == exam.class_id).all()

    student_results = []
    for student in students:
        answers = db.query(StudentAnswer).filter(
            StudentAnswer.exam_record_id == exam_id,
            StudentAnswer.student_id == student.student_id
        ).all()
        correct = sum(1 for a in answers if a.is_correct)
        total = len(answers)
        student_results.append({
            "student_id": student.student_id,
            "student_name": student.name,
            "answered": total,
            "correct": correct,
            "accuracy": round(correct / total, 2) if total > 0 else 0,
            "score": round(correct / total * 100, 1) if total > 0 else 0
        })

    stats = exam.question_stats or {}
    published = stats.get("published", False)

    return {
        "exam_id": exam_id,
        "exam_name": exam.name,
        "class_name": exam.exam_class.name if exam.exam_class else "",
        "published": published,
        "total_questions": len(questions),
        "total_students": len(students),
        "completed_count": sum(1 for s in student_results if s["answered"] > 0),
        "class_avg_accuracy": round(
            sum(s["accuracy"] for s in student_results) / len(student_results), 2
        ) if student_results else 0,
        "students": student_results
    }

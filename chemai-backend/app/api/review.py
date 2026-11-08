"""
复习任务 API
基于艾宾浩斯遗忘曲线的间隔重复复习系统
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.middleware.auth import PermissionChecker
from app.middleware.scope import ScopeGuard, require_student

from app.models.database import (
    Student, Question, get_db
)
from app.models.review_task import ReviewTask
from app.services.spaced_repetition import (
    sre, create_review_task, get_due_review_tasks,
    complete_review, generate_review_for_student
)

router = APIRouter()


class ReviewTaskResponse(BaseModel):
    """复习任务响应"""
    task_id: str
    question_id: str
    content: str
    options: Optional[List[str]] = None
    answer: Optional[str] = None
    analysis: Optional[str] = None
    knowledge_points: List[str]
    difficulty: str
    review_level: int
    next_review_at: Optional[str] = None


class ReviewSubmitRequest(BaseModel):
    """复习提交请求"""
    task_id: str
    is_correct: bool


class ReviewSubmitResponse(BaseModel):
    """复习提交响应"""
    task_id: str
    is_correct: bool
    review_level: int
    next_review_at: Optional[str] = None
    message: str


class DueReviewResponse(BaseModel):
    """到期复习任务响应"""
    student_id: str
    due_count: int
    tasks: List[ReviewTaskResponse]


@router.get("/student/{student_id}/due")
async def get_due_reviews(student_id: str, db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("review", "read", allow_self=True)),
    _scope: None = Depends(ScopeGuard("student_id", kind="student")),
):
    """
    获取学生到期应复习的任务
    """
    # 验证学生存在
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"学生 {student_id} 不存在")

    tasks = generate_review_for_student(student_id, limit=20)

    return {
        "success": True,
        "student_id": student_id,
        "due_count": len(tasks),
        "tasks": tasks
    }


@router.get("/student/{student_id}/count")
async def get_review_count(student_id: str, db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("review", "read", allow_self=True)),
    _scope: None = Depends(ScopeGuard("student_id", kind="student")),
):
    """
    获取学生待复习任务数量
    """
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"学生 {student_id} 不存在")

    tasks = get_due_review_tasks(student_id)

    return {
        "success": True,
        "student_id": student_id,
        "due_count": len(tasks)
    }


@router.post("/submit")
async def submit_review(request: ReviewSubmitRequest, db: Session = Depends(get_db),
    current_user: dict = Depends(PermissionChecker("review", "update", allow_self=True)),
):
    """
    提交复习结果
    """
    # allow_self 的契约：task_id 是不透明 ID，先落到学生再判范围，然后才改
    row = db.query(ReviewTask).filter(ReviewTask.task_id == request.task_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="复习任务不存在")
    require_student(current_user, db, row.student_id)

    task = complete_review(request.task_id, request.is_correct)

    if not task:
        raise HTTPException(status_code=404, detail="复习任务不存在")

    level_names = {
        0: "初次学习",
        1: "第1次复习",
        2: "第2次复习",
        3: "第3次复习",
        4: "第4次复习",
        5: "已掌握"
    }

    if task.next_review_at is None:
        message = "恭喜！该题目已达到复习周期上限，已掌握"
    else:
        days = (task.next_review_at - datetime.utcnow()).days + 1
        message = f"{level_names.get(task.review_level, '复习')}, {days}天后再次复习"

    return {
        "success": True,
        "task_id": task.task_id,
        "is_correct": request.is_correct,
        "review_level": task.review_level,
        "next_review_at": task.next_review_at.isoformat() if task.next_review_at else None,
        "message": message
    }


@router.post("/sync/{student_id}")
async def sync_review_tasks(student_id: str, db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("review", "create", allow_self=True)),
    _scope: None = Depends(ScopeGuard("student_id", kind="student")),
):
    """
    同步复习任务（从错题历史创建复习任务）
    """
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"学生 {student_id} 不存在")

    sre.sync_review_tasks_from_wrong_answers(student_id)

    return {
        "success": True,
        "message": "复习任务已同步"
    }


@router.get("/history/{student_id}")
async def get_review_history(student_id: str, limit: int = 20, db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("review", "read", allow_self=True)),
    _scope: None = Depends(ScopeGuard("student_id", kind="student")),
):
    """
    获取学生复习历史
    """
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"学生 {student_id} 不存在")

    tasks = db.query(ReviewTask).filter(
        ReviewTask.student_id == student_id,
        ReviewTask.completed_at.isnot(None)
    ).order_by(ReviewTask.completed_at.desc()).limit(limit).all()

    history = []
    for task in tasks:
        question = db.query(Question).filter(Question.question_id == task.question_id).first()
        if question:
            history.append({
                "task_id": task.task_id,
                "question_id": task.question_id,
                "content": question.content[:100] + "..." if len(question.content) > 100 else question.content,
                "review_level": task.review_level,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "status": task.status
            })

    return {
        "success": True,
        "student_id": student_id,
        "history": history
    }


@router.post("/create")
async def create_review(
    student_id: str,
    question_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(PermissionChecker("review", "create")),
):
    """
    手动创建复习任务
    """
    # student_id 是查询参数（不在路径上），就地校验范围
    require_student(current_user, db, student_id)

    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    question = db.query(Question).filter(Question.question_id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")

    task = create_review_task(student_id, question_id)

    return {
        "success": True,
        "task_id": task.task_id,
        "message": "复习任务已创建"
    }

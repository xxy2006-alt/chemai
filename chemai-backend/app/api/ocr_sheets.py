"""Answer sheet upload & progress API.

POST /batch — multipart upload, returns task IDs
GET  /batch/{batch_id} — batch status + per-task progress
POST /{task_id}/retry — retry failed task
GET  / — teacher's task list
"""
import os
import uuid
import time
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form
from pydantic import BaseModel
from typing import List, Optional, Union
from sqlalchemy.orm import Session
from app.models.database import get_db
from app.models.ocr_task import OCRTask
from app.middleware.auth import PermissionChecker

router = APIRouter()


class GradeRequest(BaseModel):
    batch_id: str
    teacher_id: str = ""
    # 标准答案：JSON 数组 [{q_number, answer}] 或原始文本 "1.A 2.B\n13. Cu+2H2SO4..."
    correct_answers: Optional[Union[str, list]] = None
    exam_id: str = ""


class SaveRequest(BaseModel):
    teacher_id: str = ""
    batch_id: str
    exam_id: str = ""

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "data", "answer_sheets")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/tasks/batch")
async def create_ocr_batch(
    files: List[UploadFile] = File(...),
    teacher_id: str = Form(""),
    db: Session = Depends(get_db),
    current_user: dict = Depends(PermissionChecker("ocr", "create")),
):
    """Upload a batch of answer sheet images. Returns batch_id + task_ids.

    批次归属（teacher_id）取自 token 身份：它同时是后续所有可见性/改判/保存的判定真源，
    不能由客户端自报（表单字段仅为兼容旧前端保留）。
    """
    owner_id = current_user.get("user_id") or ""
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Max 10 files per batch")

    batch_id = f"batch_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    task_ids = []

    for i, f in enumerate(files):
        ext = os.path.splitext(f.filename or f"sheet_{i}.jpg")[1] or ".jpg"
        fname = f"{batch_id}_{i:03d}{ext}"
        fpath = os.path.join(UPLOAD_DIR, fname)
        content = await f.read()
        with open(fpath, "wb") as fh:
            fh.write(content)

        task_id = f"ocr_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        task = OCRTask(
            task_id=task_id, teacher_id=owner_id, batch_id=batch_id,
            image_path=fpath, title=f"答题卡_{i+1:02d}",
            created_at=datetime.utcnow(),
        )
        db.add(task)
        task_ids.append(task_id)
    db.commit()

    return {
        "success": True, "batch_id": batch_id, "task_ids": task_ids,
        "count": len(task_ids),
    }


@router.get("/tasks/batch/{batch_id}")
async def get_batch_status(batch_id: str, db: Session = Depends(get_db),
    current_user: dict = Depends(PermissionChecker("ocr", "read")),
):
    """Get status of all tasks in a batch（按批次归属收窄，越界一律 404）。"""
    from app.services.grading_center import CallerScope

    tasks = db.query(OCRTask).filter(OCRTask.batch_id == batch_id).all()
    scope = CallerScope.from_user(db, current_user)
    if not tasks or any(not scope.allows_batch(t.teacher_id) for t in tasks):
        raise HTTPException(status_code=404, detail="Batch not found")

    task_list = []
    for t in tasks:
        task_list.append({
            "task_id": t.task_id, "title": t.title, "status": t.status,
            "progress": t.progress,
            "student_id": t.student_id,
            "student_name": t.student_name,
            "error": t.error_message,
            "confirmed": t.confirmed,
        })

    total = len(task_list)
    done = sum(1 for t in task_list if t["status"] == "done")
    failed = sum(1 for t in task_list if t["status"] == "failed")

    return {
        "success": True, "batch_id": batch_id, "total": total,
        "done": done, "failed": failed, "pending": total - done - failed,
        "tasks": task_list,
    }


@router.post("/tasks/{task_id}/retry")
async def retry_task(task_id: str, db: Session = Depends(get_db),
    current_user: dict = Depends(PermissionChecker("ocr", "create")),
):
    """Reset a failed task back to pending for retry（只允许重试自己批次的卡）。"""
    from app.services.grading_center import CallerScope

    task = db.query(OCRTask).filter(OCRTask.task_id == task_id).first()
    if not task or not CallerScope.from_user(db, current_user).allows_batch(task.teacher_id):
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = "pending"
    task.progress = 0
    task.error_message = ""
    task.ocr_result = None
    db.commit()
    return {"success": True, "message": "Task reset to pending"}


@router.get("/tasks")
async def list_teacher_tasks(
    teacher_id: str = "",
    db: Session = Depends(get_db),
    current_user: dict = Depends(PermissionChecker("ocr", "read")),
):
    """List tasks for a teacher, grouped by batch.

    身份取自 token（对齐 class_api.py 的做法，废弃「调用方自报 teacher_id」）：
    任课教师 / 学科组长只看自己上传的任务，校级管理员看**本校**教师上传的任务
    （仍支持按 `teacher_id` 筛选）。此前该参数留空即返回**所有教师**最近 100 条任务。

    ⚠️ 学科组长本该看到「本校 × 本学科」，但 `OCRTask` 上没有 class_id /
    subject 字段可推导，故一律收窄到自己 —— fail-closed。
    """
    from app.services.grading_center import CallerScope

    scope = CallerScope.from_user(db, current_user)
    q = db.query(OCRTask).filter(
        OCRTask.teacher_id.in_(scope.visible_batch_owners()),
    )
    if teacher_id and scope.school_wide:
        q = q.filter(OCRTask.teacher_id == teacher_id)
    tasks = q.order_by(OCRTask.created_at.desc()).limit(100).all()

    batches = {}
    for t in tasks:
        if t.batch_id not in batches:
            batches[t.batch_id] = {"tasks": [], "created_at": str(t.created_at)}
        batches[t.batch_id]["tasks"].append({
            "task_id": t.task_id, "title": t.title, "status": t.status,
            "progress": t.progress, "student_name": t.student_name,
            "confirmed": t.confirmed,
        })

    return {"success": True, "batches": batches}


@router.post("/grading/grade")
async def grade_batch(req: GradeRequest,
    current_user: dict = Depends(PermissionChecker("ocr", "create")),
):
    """对已完成 OCR 的批次判分。标准答案可贴文本（确定性解析）或 JSON 数组，或关联考试。

    直调判卷中心 grade_ocr_batch（与 Agent 工具共用同一编排与判定，ADR-0012），
    批次归属与考试班级按调用者范围收窄（身份取自 token）。
    """
    from app.models.database import get_db
    from app.services import grading_center
    from app.services.llm_grading import parse_correct_answers

    if not req.correct_answers and not req.exam_id:
        raise HTTPException(status_code=400, detail="缺少正确答案：请粘贴标准答案或关联考试")

    parsed_answers = None
    if req.correct_answers:
        if isinstance(req.correct_answers, str):
            parsed_answers = parse_correct_answers(req.correct_answers)
            if not parsed_answers:
                raise HTTPException(status_code=400,
                                    detail="标准答案解析不出题号（例：1.A 2.B 或 13. Cu+2H2SO4(浓)...）")
        else:
            parsed_answers = req.correct_answers

    db = next(get_db())
    try:
        results = grading_center.grade_ocr_batch(
            db, batch_id=req.batch_id, parsed_answers=parsed_answers, exam_id=req.exam_id or None,
            scope=grading_center.CallerScope.from_user(db, current_user),
        )
    finally:
        db.close()
    if not results:
        raise HTTPException(status_code=400, detail="没有完成识别的答题卡")
    denied = next((r["error"] for r in results if r.get("denied")), None)
    if denied:
        raise HTTPException(status_code=403, detail=denied)

    unjudged = sum(r.get("unjudged", 0) for r in results)
    summary = "\n".join(
        f"{r.get('student_name') or r['task_id']}: {r['error']}" if "error" in r
        else f"{r.get('student_name') or r['task_id']}: {r['score']}/{r['total']}分"
             + (f"（{r['unjudged']} 题未判）" if r.get("unjudged") else "")
        for r in results
    )
    return {
        "message": f"批改完成，共{len(results)}份"
                   + ("（部分失败）" if any("error" in r for r in results) else "")
                   + (f"，{unjudged} 题未判（缺标准答案或判定服务不可用，不计入成绩）" if unjudged else ""),
        "summary": summary,
        "results": results,
        "next_action": "请确认批改结果，确认后可保存",
    }


@router.post("/grading/save")
async def save_grading(req: SaveRequest,
    current_user: dict = Depends(PermissionChecker("ocr", "create")),
):
    """保存批改结果：必须关联真实考试（exam_id 校验 + 保存后触发 barrier 诊断）。

    直调判卷中心 save_batch（与 Agent 工具共用单实现，ADR-0012），
    考试与批次归属按调用者范围收窄（身份取自 token）。
    """
    from app.models.database import get_db
    from app.services import grading_center

    db = next(get_db())
    try:
        out = grading_center.save_batch(
            db, batch_id=req.batch_id, exam_id=req.exam_id,
            scope=grading_center.CallerScope.from_user(db, current_user),
        )
    finally:
        db.close()
    if out.get("error"):
        raise HTTPException(status_code=403 if out.get("denied") else 400,
                            detail=out["error"])
    return out


@router.get("/grading/queue")
async def grading_queue(
    db: Session = Depends(get_db),
    current_user: dict = Depends(PermissionChecker("ocr", "read")),
):
    """判卷中心待确认队列：已批改未确认的答题卡批 + 待确认成绩（按身份与班级范围收窄）。"""
    from app.services import grading_center

    # 读侧范围：答题卡批按上传者归属、待确认考试按班级范围（ADR-0010 第二层范围）
    return grading_center.grading_queue(
        db, grading_center.CallerScope.from_user(db, current_user),
    )


class OverrideRequest(BaseModel):
    answer_id: str
    is_correct: bool
    reason: str = ""


@router.post("/grading/override")
async def override_grading(
    req: OverrideRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(PermissionChecker("exam", "update")),
):
    """教师改判：更新对错与理由，并以该记录所属考试为单位重触发诊断。

    只改判自己范围内的学生作答（answer_id 是模型/前端自报的，按学生范围反查收窄）。
    """
    from app.middleware.scope import RequestScope
    from app.models.database import StudentAnswer
    from app.services import grading_center

    row = db.query(StudentAnswer).filter(StudentAnswer.answer_id == req.answer_id).first()
    if row is None or not RequestScope.from_user(current_user, db).allows_student(row.student_id):
        raise HTTPException(status_code=404, detail="作答记录不存在")

    out = grading_center.override(
        db, answer_id=req.answer_id, is_correct=req.is_correct,
        reason=req.reason, teacher_id=current_user["user_id"],
    )
    if not out.get("updated"):
        raise HTTPException(status_code=404, detail=out.get("error", "改判失败"))
    return out


@router.get("/grading/submissions")
async def list_submissions(
    exam_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(PermissionChecker("exam", "read")),
):
    """线上/判卷中心已保存作答的逐生逐题浏览（改判入口的数据源）。

    exam_id 是查询参数（不是路径参数，ScopeGuard 够不着），就地按考试所属班级收窄。
    """
    from app.middleware.scope import RequestScope
    from app.models.database import ExamRecord, Student, StudentAnswer, Question

    exam = db.query(ExamRecord).filter(ExamRecord.record_id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="考试记录不存在")
    if not RequestScope.from_user(current_user, db).allows_class(exam.class_id):
        raise HTTPException(status_code=403, detail="无权访问该考试的作答")

    rows = (
        db.query(StudentAnswer, Student.name, Question.content)
        .join(Student, Student.student_id == StudentAnswer.student_id)
        .join(Question, Question.question_id == StudentAnswer.question_id)
        .filter(StudentAnswer.exam_record_id == exam_id)
        .order_by(StudentAnswer.student_id, StudentAnswer.question_id)
        .all()
    )

    students: dict = {}
    for ans, name, content in rows:
        s = students.setdefault(ans.student_id, {
            "student_id": ans.student_id, "name": name, "questions": [],
        })
        s["questions"].append({
            "answer_id": ans.answer_id,
            "question_id": ans.question_id,
            "content": (content or "")[:120],
            "student_answer": ans.student_answer,
            "is_correct": ans.is_correct,
            "reason": ans.grade_reason,
            "source": ans.source.value if ans.source else None,
        })

    return {"success": True, "exam_id": exam_id, "students": list(students.values())}

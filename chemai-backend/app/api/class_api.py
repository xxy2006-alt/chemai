"""
班级管理API
GET /api/classes - 获取班级列表
POST /api/classes - 创建班级
PUT /api/classes/{id} - 更新班级
DELETE /api/classes/{id} - 删除班级
GET /api/classes/{id}/students - 获取班级学生
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.middleware.auth import PermissionChecker
from app.middleware.scope import RequestScope
from app.models.database import get_db, Class, Student, Teacher, TeacherClassSubject, StudentAnswer, Question

router = APIRouter()


class ClassCreate(BaseModel):
    name: str
    grade_id: str  # 年级ID，如 "grade_2026_高一"
    subject: Optional[str] = "化学"


class ClassUpdate(BaseModel):
    name: Optional[str] = None
    grade_id: Optional[str] = None
    subject: Optional[str] = None


@router.get("")
async def get_classes(
    current_user: dict = Depends(PermissionChecker("class", "read")),
    db: Session = Depends(get_db)
):
    """
    获取班级列表

    数据范围（ADR-0010）：只返回该身份可见的班级。
    身份取自 token —— 原 `teacher_id` 查询参数已移除（调用方自报身份是反模式，
    学生或任意人传 teacher_id 就能拿到别人的班）。
    """
    allowed = RequestScope.from_user(current_user, db).class_ids()
    if not allowed:
        return {"success": True, "total": 0, "classes": []}

    classes = db.query(Class).filter(Class.class_id.in_(allowed)).all()

    result = []
    for c in classes:
        # 获取该班级的所有任课教师（通过 TeacherClassSubject）
        tcs_records = db.query(TeacherClassSubject).filter(
            TeacherClassSubject.class_id == c.class_id
        ).all()
        teacher_ids = [r.teacher_id for r in tcs_records]
        teachers = db.query(Teacher).filter(Teacher.teacher_id.in_(teacher_ids)).all() if teacher_ids else []

        # 班主任 = teacher_class_subject 里 is_class_teacher 的那位（阶段 6.2）。
        # 原先读 `classes.teacher_id`，但建表时那个字段恒为 None（init_db 写死），
        # 所以 teacher_id / teacher_name 一直是 null、is_class_teacher 一直是 False。
        head_teacher_id = next(
            (r.teacher_id for r in tcs_records if r.is_class_teacher), None
        )
        head_teacher = next((t for t in teachers if t.teacher_id == head_teacher_id), None)

        result.append({
            "class_id": c.class_id,
            "name": c.name,
            "teacher_id": head_teacher_id,  # 班主任ID
            "teacher_name": head_teacher.name if head_teacher else None,
            "grade": c.grade,
            "grade_id": c.grade_id,
            "subject": c.subject,
            "student_count": c.student_count or 0,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "teachers": [
                {
                    "teacher_id": t.teacher_id,
                    "name": t.name,
                    "subject": next((r.subject for r in tcs_records if r.teacher_id == t.teacher_id), None),
                    "is_class_teacher": t.teacher_id == head_teacher_id
                }
                for t in teachers
            ] if teachers else []
        })

    return {
        "success": True,
        "total": len(result),
        "classes": result
    }


@router.post("")
async def create_class(
    request: ClassCreate,
    current_user: dict = Depends(PermissionChecker("class", "create")),
    db: Session = Depends(get_db)
):
    """
    创建班级
    """
    # 检查年级是否存在，且属于调用者学校（否则可把班级挂到别校年级下）
    from app.models.database import Grade
    grade = db.query(Grade).filter(Grade.grade_id == request.grade_id).first()
    if not grade:
        raise HTTPException(status_code=404, detail="年级不存在")
    school_id = current_user.get("school_id")
    if not school_id or grade.school_id != school_id:
        raise HTTPException(status_code=403, detail="无权在该年级下建班")

    # 生成班级ID
    class_id = f"class_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    class_obj = Class(
        class_id=class_id,
        name=request.name,
        grade_id=request.grade_id,
        grade=grade.name,  # 从年级表获取年级名称
        subject=request.subject or "化学",
        student_count=0
    )
    db.add(class_obj)
    db.commit()

    return {
        "success": True,
        "message": "班级创建成功",
        "class_id": class_id
    }


@router.put("/{class_id}")
async def update_class(
    class_id: str,
    request: ClassUpdate,
    current_user: dict = Depends(PermissionChecker("class", "update")),
    db: Session = Depends(get_db)
):
    """
    更新班级信息
    """
    if not RequestScope.from_user(current_user, db).allows_class(class_id):
        raise HTTPException(status_code=403, detail="无权修改该班级")

    class_obj = db.query(Class).filter(Class.class_id == class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="班级不存在")

    if request.name is not None:
        class_obj.name = request.name
    if request.grade_id is not None:
        # 新年级必须存在且属于本校（换到别校年级会把班级移出本校范围）
        from app.models.database import Grade
        grade = db.query(Grade).filter(Grade.grade_id == request.grade_id).first()
        if not grade:
            raise HTTPException(status_code=404, detail="年级不存在")
        school_id = current_user.get("school_id")
        if not school_id or grade.school_id != school_id:
            raise HTTPException(status_code=403, detail="无权把班级改到该年级")
        class_obj.grade_id = request.grade_id
        class_obj.grade = grade.name  # 更新年级名称
    if request.subject is not None:
        class_obj.subject = request.subject

    class_obj.updated_at = datetime.utcnow()
    db.commit()

    return {"success": True, "message": "班级信息已更新"}


@router.delete("/{class_id}")
async def delete_class(
    class_id: str,
    current_user: dict = Depends(PermissionChecker("class", "delete")),
    db: Session = Depends(get_db)
):
    """
    删除班级
    """
    if not RequestScope.from_user(current_user, db).allows_class(class_id):
        raise HTTPException(status_code=403, detail="无权删除该班级")

    class_obj = db.query(Class).filter(Class.class_id == class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="班级不存在")

    # 检查班级是否有学生
    if class_obj.student_count and class_obj.student_count > 0:
        raise HTTPException(status_code=400, detail="班级仍有学生，无法删除")

    db.delete(class_obj)
    db.commit()

    return {"success": True, "message": "班级已删除"}


@router.get("/{class_id}/students")
async def get_class_students(
    class_id: str,
    current_user: dict = Depends(PermissionChecker("class", "read")),
    db: Session = Depends(get_db)
):
    """
    获取班级学生列表（含姓名与手机号）
    """
    if not RequestScope.from_user(current_user, db).allows_class(class_id):
        raise HTTPException(status_code=403, detail="无权访问该班级")

    class_obj = db.query(Class).filter(Class.class_id == class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="班级不存在")

    students = db.query(Student).filter(Student.class_id == class_id).all()
    student_ids = [s.student_id for s in students]

    # 聚合每名学生的薄弱知识点（错题知识点计数，取前 5）
    weak_map: dict = {}
    if student_ids:
        wrong_answers = db.query(StudentAnswer).filter(
            StudentAnswer.student_id.in_(student_ids),
            StudentAnswer.is_correct.is_(False),
        ).all()
        qids = list({a.question_id for a in wrong_answers})
        qmap = {q.question_id: q for q in db.query(Question).filter(
            Question.question_id.in_(qids)).all()} if qids else {}
        for a in wrong_answers:
            q = qmap.get(a.question_id)
            if not q or not q.knowledge_points:
                continue
            kp_count = weak_map.setdefault(a.student_id, {})
            for kp in q.knowledge_points:
                kp_count[kp] = kp_count.get(kp, 0) + 1

    return {
        "success": True,
        "class_id": class_id,
        "class_name": class_obj.name,
        "total": len(students),
        "students": [
            {
                "student_id": s.student_id,
                "name": s.name,
                "phone": s.phone,
                "status": s.status,
                "barrier_type": s.barrier_type,
                "weak_knowledge_points": [
                    kp for kp, _ in sorted(
                        weak_map.get(s.student_id, {}).items(),
                        key=lambda x: (-x[1], x[0]),
                    )
                ][:5],
                "exercises_completed": s.exercises_completed,
                "created_at": s.created_at.isoformat() if s.created_at else None
            }
            for s in students
        ]
    }

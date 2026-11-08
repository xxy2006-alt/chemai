"""
用户管理API
GET /api/users/students - 获取学生列表
GET /api/users/teachers - 获取教师列表
POST /api/users/student - 创建学生
PUT /api/users/student/{id} - 更新学生
DELETE /api/users/student/{id} - 删除学生
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.middleware.auth import PermissionChecker
from app.middleware.scope import RequestScope
from app.models.database import get_db, Teacher, Student, Account, Class, TeacherClassSubject

router = APIRouter()


class StudentCreate(BaseModel):
    name: str
    class_id: str
    phone: Optional[str] = None


class StudentUpdate(BaseModel):
    name: Optional[str] = None
    class_id: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None


class TeacherCreate(BaseModel):
    name: str
    school_id: Optional[str] = None
    phone: Optional[str] = None


class TeacherUpdate(BaseModel):
    name: Optional[str] = None
    school_id: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None


@router.get("/students")
async def get_students(
    class_id: Optional[str] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(PermissionChecker("student", "read")),
    db: Session = Depends(get_db)
):
    """
    获取学生列表

    数据范围（ADR-0010）：只返回该身份可见班级里的学生。
    指定了范围外的班级时返回空列表而非 403 —— 不泄漏"这个班存在"。
    """
    allowed = RequestScope.from_user(current_user, db).class_ids()

    query = db.query(Student)

    if class_id:
        if class_id not in allowed:
            return {"success": True, "total": 0, "students": []}
        query = query.filter(Student.class_id == class_id)
    else:
        query = query.filter(Student.class_id.in_(allowed))
    if status:
        query = query.filter(Student.status == status)

    students = query.all()

    # Collect class names + accuracy data in batch
    class_ids = set(s.class_id for s in students if s.class_id)
    class_names = {}
    if class_ids:
        from app.models.database import Class
        for c in db.query(Class).filter(Class.class_id.in_(class_ids)).all():
            class_names[c.class_id] = c.name

    # Batch accuracy per student（只认生效行：判定中/待确认的作答不是成绩）
    from sqlalchemy import case, func
    from app.models.database import StudentAnswer
    from app.services.grading_center import effective_conditions

    accuracy_map = {}
    acc_rows = (
        db.query(
            StudentAnswer.student_id,
            func.avg(case((StudentAnswer.is_correct.is_(True), 1.0), else_=0.0)),
        )
        .filter(effective_conditions())
        .group_by(StudentAnswer.student_id)
        .all()
    )
    for sid, acc in acc_rows:
        if acc is not None:
            accuracy_map[sid] = round(float(acc), 2)

    return {
        "success": True,
        "total": len(students),
        "students": [
            {
                "student_id": s.student_id,
                "name": s.name,
                "class_id": s.class_id,
                "class_name": class_names.get(s.class_id, ""),
                "phone": s.phone,
                "status": s.status,
                "barrier_type": s.barrier_type,
                "exercises_completed": s.exercises_completed,
                "last_exercise_at": s.last_exercise_at.isoformat() if s.last_exercise_at else None,
                "accuracy": accuracy_map.get(s.student_id),
                "created_at": s.created_at.isoformat() if s.created_at else None
            }
            for s in students
        ]
    }


@router.get("/student/{student_id}/detail")
async def get_student_detail(
    student_id: str,
    current_user: dict = Depends(PermissionChecker("student", "read")),
    db: Session = Depends(get_db),
):
    """获取学生详情: 薄弱知识点 + 最近活动"""
    import json
    from sqlalchemy import text
    from collections import Counter
    if not RequestScope.from_user(current_user, db).allows_student(student_id):
        raise HTTPException(status_code=403, detail="无权访问该学生")
    s = db.query(Student).filter(Student.student_id == student_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="学生不存在")
    wkp, activity = [], []
    # 薄弱知识点只认生效行：判定中/待确认的作答不是错题，不该进薄弱点
    from app.models.database import Question, StudentAnswer
    from app.services.grading_center import effective_conditions

    rows = (
        db.query(Question.knowledge_points)
        .join(StudentAnswer, StudentAnswer.question_id == Question.question_id)
        .filter(
            StudentAnswer.student_id == student_id,
            StudentAnswer.is_correct.is_(False),
            effective_conditions(),
        )
        .order_by(StudentAnswer.answered_at.desc())
        .limit(30)
        .all()
    )
    kp_count = Counter()
    for (kj,) in rows:
        for k in (json.loads(kj) if isinstance(kj, str) else (kj or [])):
            kp_count[k] += 1
    wkp = [k for k, _ in kp_count.most_common(5)]
    act_rows = db.execute(text(
        "SELECT q.knowledge_points, q.difficulty, sa.is_correct, sa.answered_at FROM student_answers sa "
        "JOIN questions q ON sa.question_id=q.question_id WHERE sa.student_id=:s "
        "ORDER BY sa.answered_at DESC LIMIT 10"
    ), {"s": student_id}).fetchall()
    for row in act_rows:
        d = row[3]
        if isinstance(d, str):
            date_str = d[:10] if len(d) > 10 else (d[:5] if '-' in d else '')
        elif hasattr(d, 'strftime'):
            date_str = d.strftime("%m-%d")
        else:
            date_str = str(d)[:10]
        kps = json.loads(row[0]) if isinstance(row[0], str) else (row[0] or [])
        kp_name = kps[0] if kps else "化学"
        diff_label = {"EASY":"基础","MEDIUM":"进阶","HARD":"拔高"}.get(row[1],"")
        status = "✓" if row[2] else "✗"
        desc = f"{status} {kp_name}{diff_label+'·' if diff_label else ''}练习"
        activity.append({"date": date_str, "desc": desc, "is_correct": row[2]})
    return {"success": True, "weak_knowledge_points": wkp, "recent_activity": activity}


@router.get("/teachers")
async def get_teachers(
    status: Optional[str] = None,
    current_user: dict = Depends(PermissionChecker("teacher", "read")),
    db: Session = Depends(get_db)
):
    """
    获取教师列表

    数据范围：只返回本校教师。school_id 取自 token，不接受调用方自报。
    无学校的身份（如平台超管）看不到任何教师 —— ADR-0011。
    """
    school_id = current_user.get("school_id")
    if not school_id:
        return {"success": True, "total": 0, "teachers": []}

    query = db.query(Teacher).filter(Teacher.school_id == school_id)

    if status:
        query = query.filter(Teacher.status == status)

    teachers = query.all()

    return {
        "success": True,
        "total": len(teachers),
        "teachers": [
            {
                "teacher_id": t.teacher_id,
                "name": t.name,
                "school_id": t.school_id,
                "phone": t.phone,
                "status": t.status,
                "created_at": t.created_at.isoformat() if t.created_at else None
            }
            for t in teachers
        ]
    }


@router.post("/student")
async def create_student(
    request: StudentCreate,
    current_user: dict = Depends(PermissionChecker("student", "create")),
    db: Session = Depends(get_db)
):
    """
    创建学生
    """
    # 只能往自己有权操作的班里放学生
    if not RequestScope.from_user(current_user, db).allows_class(request.class_id):
        raise HTTPException(status_code=403, detail="无权操作目标班级")

    # 检查班级是否存在
    class_obj = db.query(Class).filter(Class.class_id == request.class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="班级不存在")

    # 生成学生ID
    student_id = f"student_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    student = Student(
        student_id=student_id,
        name=request.name,
        class_id=request.class_id,
        phone=request.phone,
        status="approved"  # 直接approved，也可以设为pending
    )
    db.add(student)

    # 更新班级学生数
    class_obj.student_count = (class_obj.student_count or 0) + 1

    db.commit()

    return {
        "success": True,
        "message": "学生创建成功",
        "student_id": student_id
    }


@router.put("/student/{student_id}")
async def update_student(
    student_id: str,
    request: StudentUpdate,
    current_user: dict = Depends(PermissionChecker("student", "update")),
    db: Session = Depends(get_db)
):
    """
    更新学生信息
    """
    scope = RequestScope.from_user(current_user, db)
    if not scope.allows_student(student_id):
        raise HTTPException(status_code=403, detail="无权修改该学生")
    # 转班时必须同时有权操作目标班，否则等于把学生塞进管不到的班
    if request.class_id is not None and not scope.allows_class(request.class_id):
        raise HTTPException(status_code=403, detail="无权操作目标班级")

    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    if request.name is not None:
        student.name = request.name
    if request.phone is not None:
        student.phone = request.phone
    if request.status is not None:
        student.status = request.status
    if request.class_id is not None:
        # 如果更换班级
        if request.class_id != student.class_id:
            # 减少原班级人数
            old_class = db.query(Class).filter(Class.class_id == student.class_id).first()
            if old_class and old_class.student_count:
                old_class.student_count = max(0, old_class.student_count - 1)

            # 增加新班级人数
            new_class = db.query(Class).filter(Class.class_id == request.class_id).first()
            if new_class:
                new_class.student_count = (new_class.student_count or 0) + 1

            student.class_id = request.class_id

    student.updated_at = datetime.utcnow()
    db.commit()

    return {"success": True, "message": "学生信息已更新"}


@router.delete("/student/{student_id}")
async def delete_student(
    student_id: str,
    current_user: dict = Depends(PermissionChecker("student", "delete")),
    db: Session = Depends(get_db)
):
    """
    删除学生
    """
    if not RequestScope.from_user(current_user, db).allows_student(student_id):
        raise HTTPException(status_code=403, detail="无权删除该学生")

    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    # 删除关联账户
    db.query(Account).filter(Account.student_id == student_id).delete()

    # 减少班级人数
    class_obj = db.query(Class).filter(Class.class_id == student.class_id).first()
    if class_obj and class_obj.student_count:
        class_obj.student_count = max(0, class_obj.student_count - 1)

    # 删除学生
    db.delete(student)
    db.commit()

    return {"success": True, "message": "学生已删除"}


@router.put("/teacher/{teacher_id}")
async def update_teacher(
    teacher_id: str,
    request: TeacherUpdate,
    current_user: dict = Depends(PermissionChecker("teacher", "update")),
    db: Session = Depends(get_db)
):
    """
    更新教师信息
    """
    teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="教师不存在")

    # 只能改本校教师；也不得把教师挪到别校（跨校越权）
    school_id = current_user.get("school_id")
    if not school_id or teacher.school_id != school_id:
        raise HTTPException(status_code=403, detail="无权修改该教师")
    if request.school_id is not None and request.school_id != school_id:
        raise HTTPException(status_code=403, detail="无权变更教师所属学校")

    if request.name is not None:
        teacher.name = request.name
    if request.school_id is not None:
        teacher.school_id = request.school_id
    if request.phone is not None:
        teacher.phone = request.phone
    if request.status is not None:
        teacher.status = request.status

    teacher.updated_at = datetime.utcnow()
    db.commit()

    return {"success": True, "message": "教师信息已更新"}


@router.post("/teacher/approve/{teacher_id}")
async def approve_teacher(
    teacher_id: str,
    current_user: dict = Depends(PermissionChecker("teacher", "create")),
    db: Session = Depends(get_db)
):
    """
    审批通过教师
    """
    teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="教师不存在")

    school_id = current_user.get("school_id")
    if not school_id or teacher.school_id != school_id:
        raise HTTPException(status_code=403, detail="无权审批该教师")

    teacher.status = "approved"
    teacher.updated_at = datetime.utcnow()
    db.commit()

    return {"success": True, "message": "教师已审批通过"}


@router.post("/student/approve/{student_id}")
async def approve_student(
    student_id: str,
    current_user: dict = Depends(PermissionChecker("student", "update")),
    db: Session = Depends(get_db)
):
    """
    审批通过学生
    """
    if not RequestScope.from_user(current_user, db).allows_student(student_id):
        raise HTTPException(status_code=403, detail="无权审批该学生")

    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    student.status = "approved"
    student.updated_at = datetime.utcnow()
    db.commit()

    return {"success": True, "message": "学生已审批通过"}


# ============================================
# 教师-班级关联管理
# ============================================

class TeacherClassAssign(BaseModel):
    class_id: str
    subject: str
    is_class_teacher: bool = False


@router.post("/teacher/{teacher_id}/assign-classes")
async def assign_teacher_classes(
    teacher_id: str,
    assignments: list[TeacherClassAssign],
    current_user: dict = Depends(PermissionChecker("teacher", "update")),
    db: Session = Depends(get_db)
):
    """
    分配教师到班级/科目
    """
    teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="教师不存在")

    # 只能给本校教师排课
    school_id = current_user.get("school_id")
    if not school_id or teacher.school_id != school_id:
        raise HTTPException(status_code=403, detail="无权为该教师排课")

    # 班级同样收窄到调用者范围：否则可把外校班级排给本校教师，
    # 而 TeacherClassSubject 正是 RequestScope 推导「这个教师能看哪些班」的唯一依据
    scope = RequestScope.from_user(current_user, db)
    out_of_scope = [a.class_id for a in assignments if not scope.allows_class(a.class_id)]
    if out_of_scope:
        raise HTTPException(status_code=403,
                            detail=f"无权分配这些班级（不在你的范围内）: {out_of_scope}")

    # 删除旧的关联
    db.query(TeacherClassSubject).filter(
        TeacherClassSubject.teacher_id == teacher_id
    ).delete()

    # 添加新的关联
    for assignment in assignments:
        tcs = TeacherClassSubject(
            id=f"tcs_{teacher_id}_{assignment.class_id}_{assignment.subject}",
            teacher_id=teacher_id,
            class_id=assignment.class_id,
            subject=assignment.subject,
            is_class_teacher=assignment.is_class_teacher,
            assigned_at=datetime.utcnow()
        )
        db.add(tcs)

    db.commit()
    return {"success": True, "message": f"已分配{len(assignments)}个班级/科目"}


@router.get("/teacher/{teacher_id}/classes")
async def get_teacher_classes(
    teacher_id: str,
    current_user: dict = Depends(PermissionChecker("teacher", "read")),
    db: Session = Depends(get_db)
):
    """
    获取教师任教的班级列表（本人，或校级管理员看本校教师）
    """
    teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="教师不存在")

    if not RequestScope.from_user(current_user, db).allows_teacher(teacher_id):
        raise HTTPException(status_code=403, detail="无权查看该教师的班级")

    tcs_list = db.query(TeacherClassSubject).filter(
        TeacherClassSubject.teacher_id == teacher_id
    ).all()

    result = []
    for tcs in tcs_list:
        class_obj = db.query(Class).filter(Class.class_id == tcs.class_id).first()
        if class_obj:
            result.append({
                "tcs_id": tcs.id,
                "class_id": tcs.class_id,
                "class_name": class_obj.name,
                "subject": tcs.subject,
                "is_class_teacher": tcs.is_class_teacher,
                "grade_id": class_obj.grade_id
            })

    return {"success": True, "classes": result}


# ============================================
# 学生批量导入
# ============================================

class StudentBatchImport(BaseModel):
    class_id: str
    students: list[dict]  # [{"name": "张三", "phone": "13800138000"}, ...]


@router.post("/students/batch-import")
async def batch_import_students(
    import_data: StudentBatchImport,
    current_user: dict = Depends(PermissionChecker("student", "create")),
    db: Session = Depends(get_db)
):
    """
    批量导入学生
    """
    if not RequestScope.from_user(current_user, db).allows_class(import_data.class_id):
        raise HTTPException(status_code=403, detail="无权操作目标班级")

    # 检查班级是否存在
    class_obj = db.query(Class).filter(Class.class_id == import_data.class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="班级不存在")

    imported = []
    failed = []

    for i, student_data in enumerate(import_data.students):
        try:
            name = student_data.get("name")
            phone = student_data.get("phone")

            if not name:
                failed.append({"index": i, "reason": "姓名为空"})
                continue

            student_id = f"student_{datetime.now().strftime('%Y%m%d%H%M%S')}_{i}"
            student = Student(
                student_id=student_id,
                name=name,
                class_id=import_data.class_id,
                phone=phone,
                status="approved"
            )
            db.add(student)
            imported.append({"name": name, "student_id": student_id})
        except Exception as e:
            failed.append({"index": i, "reason": str(e)})

    # 更新班级学生数
    class_obj.student_count = (class_obj.student_count or 0) + len(imported)
    db.commit()

    return {
        "success": True,
        "message": f"导入完成：成功{len(imported)}个，失败{len(failed)}个",
        "imported": imported,
        "failed": failed
    }


# ============================================
# 学生调班
# ============================================

class StudentTransfer(BaseModel):
    new_class_id: str


@router.post("/student/{student_id}/transfer")
async def transfer_student(
    student_id: str,
    request: StudentTransfer,
    current_user: dict = Depends(PermissionChecker("student", "update")),
    db: Session = Depends(get_db)
):
    """
    学生调班
    """
    scope = RequestScope.from_user(current_user, db)
    if not scope.allows_student(student_id):
        raise HTTPException(status_code=403, detail="无权调班该学生")
    if not scope.allows_class(request.new_class_id):
        raise HTTPException(status_code=403, detail="无权操作目标班级")

    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    # 检查新班级是否存在
    new_class = db.query(Class).filter(Class.class_id == request.new_class_id).first()
    if not new_class:
        raise HTTPException(status_code=404, detail="目标班级不存在")

    old_class_id = student.class_id

    # 减少原班级人数
    old_class = db.query(Class).filter(Class.class_id == old_class_id).first()
    if old_class and old_class.student_count:
        old_class.student_count = max(0, old_class.student_count - 1)

    # 增加新班级人数
    new_class.student_count = (new_class.student_count or 0) + 1

    # 更新学生班级
    student.class_id = request.new_class_id
    student.updated_at = datetime.utcnow()

    db.commit()

    return {
        "success": True,
        "message": f"学生已从{old_class_id}调至{request.new_class_id}"
    }


@router.post("/student/{student_id}/reset-password")
async def reset_student_password(
    student_id: str,
    current_user: dict = Depends(PermissionChecker("student", "update")),
    db: Session = Depends(get_db)
):
    """
    重置学生密码为默认密码 123456
    """
    from app.models.database import Account
    import hashlib

    if not RequestScope.from_user(current_user, db).allows_student(student_id):
        raise HTTPException(status_code=403, detail="无权重置该学生密码")

    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    account = db.query(Account).filter(Account.student_id == student_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="学生账户不存在")

    account.password_hash = hashlib.sha256("123456".encode()).hexdigest()
    db.commit()

    return {"success": True, "message": f"学生 {student.name} 的密码已重置为 123456"}

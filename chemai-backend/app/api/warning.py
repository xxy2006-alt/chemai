"""
学情预警 API
实时检测学生学情异常并触发预警
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from app.models.database import (
    Student, Class, get_db
)
from app.models.warning_log import WarningLog
from app.services.early_warning import ews, check_all_warnings, get_pending_warnings
from app.models.warning_log import WARNING_TYPE_NAMES, WARNING_LEVEL_NAMES
from app.middleware.auth import PermissionChecker, get_current_user
from app.middleware.scope import RequestScope, ScopeGuard

router = APIRouter()


class WarningResponse(BaseModel):
    """预警响应"""
    warning_id: str
    student_id: str
    student_name: str
    class_name: str
    warning_type: str
    warning_type_name: str
    level: str
    level_name: str
    title: str
    content: Optional[str]
    status: str
    created_at: str


class ProcessWarningRequest(BaseModel):
    """处理预警请求"""
    note: Optional[str] = None
    action: str = "processed"  # processed/ignored


@router.get("/pending")
async def get_pending_warnings_api(
    request: Request,
    class_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    获取待处理预警列表（按调用者数据范围收窄；class_id 越界一律 403）
    """
    # 身份取自 token（权限已由 router 基线的 warning:read 校验，此处只要范围）
    scope = RequestScope.from_user(get_current_user(request), db)
    if class_id:
        if not scope.allows_class(class_id):
            raise HTTPException(status_code=403, detail="无权访问该班级")
        warnings = get_pending_warnings(class_id, db=db)
    else:
        warnings = get_pending_warnings(None, scope.class_ids(), db=db)

    result = []
    for w in warnings:
        student = db.query(Student).filter(Student.student_id == w.student_id).first()
        class_obj = db.query(Class).filter(Class.class_id == student.class_id).first() if student else None

        result.append({
            "warning_id": w.warning_id,
            "student_id": w.student_id,
            "student_name": student.name if student else "未知",
            "class_name": class_obj.name if class_obj else "未知",
            "warning_type": w.warning_type,
            "warning_type_name": WARNING_TYPE_NAMES.get(w.warning_type, w.warning_type),
            "level": w.level,
            "level_name": WARNING_LEVEL_NAMES.get(w.level, w.level),
            "title": w.title,
            "content": w.content,
            "status": w.status,
            "created_at": w.created_at.isoformat() if w.created_at else None
        })

    return {
        "success": True,
        "count": len(result),
        "warnings": result
    }


@router.get("/student/{student_id}")
async def get_student_warnings(student_id: str, db: Session = Depends(get_db),
    _scope: None = Depends(ScopeGuard("student_id", kind="student")),
):
    """
    获取指定学生的预警历史
    """
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    warnings = ews.get_warnings_by_student(db, student_id)

    result = []
    for w in warnings:
        result.append({
            "warning_id": w.warning_id,
            "student_id": w.student_id,
            "student_name": student.name,
            "warning_type": w.warning_type,
            "warning_type_name": WARNING_TYPE_NAMES.get(w.warning_type, w.warning_type),
            "level": w.level,
            "level_name": WARNING_LEVEL_NAMES.get(w.level, w.level),
            "title": w.title,
            "content": w.content,
            "status": w.status,
            "processed_by": w.processed_by,
            "processed_at": w.processed_at.isoformat() if w.processed_at else None,
            "processed_note": w.processed_note,
            "created_at": w.created_at.isoformat() if w.created_at else None
        })

    return {
        "success": True,
        "student_id": student_id,
        "student_name": student.name,
        "warnings": result
    }


@router.put("/{warning_id}/process")
async def process_warning_api(
    warning_id: str,
    request: ProcessWarningRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("warning", "update")),
):
    """
    处理预警（按该预警所属学生的数据范围收窄；越界一律 404）
    """
    row = db.query(WarningLog).filter(WarningLog.warning_id == warning_id).first()
    scope = RequestScope.from_user(get_current_user(http_request), db)
    if row is None or not scope.allows_student(row.student_id):
        raise HTTPException(status_code=404, detail="预警不存在")

    # 从会话中获取处理人ID（这里简化处理）
    processed_by = "teacher"  # TODO: 从认证会话中获取

    warning = ews.process_warning(
        db, warning_id, processed_by,
        request.note, request.action
    )

    if not warning:
        raise HTTPException(status_code=404, detail="预警不存在")

    return {
        "success": True,
        "message": f"预警已{('标记为忽略' if request.action == 'ignored' else '处理')}",
        "warning_id": warning_id
    }


@router.post("/check")
async def check_warnings_api(request: Request, db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("warning", "create")),
):
    """
    手动触发预警检查（按调用者数据范围收窄：只为自己范围内的学生建预警并发家长通知）
    """
    try:
        scope = RequestScope.from_user(get_current_user(request), db)
        warnings = check_all_warnings(scope.class_ids())
        return {
            "success": True,
            "message": f"已检查并创建 {len(warnings)} 条预警",
            "warnings_created": len(warnings)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/class/{class_id}/summary")
async def get_class_warning_summary(class_id: str, db: Session = Depends(get_db),
    _scope: None = Depends(ScopeGuard("class_id", kind="class")),
):
    """
    获取班级预警汇总
    """
    class_obj = db.query(Class).filter(Class.class_id == class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="班级不存在")

    # 获取班级所有学生的预警
    students = db.query(Student).filter(Student.class_id == class_id).all()
    student_ids = [s.student_id for s in students]

    # 统计各类预警数量
    warnings = db.query(WarningLog).filter(
        WarningLog.student_id.in_(student_ids),
        WarningLog.status == "pending"
    ).all()

    summary = {
        "total": len(warnings),
        "by_type": {},
        "by_level": {},
        "critical_count": 0
    }

    for w in warnings:
        # 按类型统计
        if w.warning_type not in summary["by_type"]:
            summary["by_type"][w.warning_type] = 0
        summary["by_type"][w.warning_type] += 1

        # 按级别统计
        if w.level not in summary["by_level"]:
            summary["by_level"][w.level] = 0
        summary["by_level"][w.level] += 1

        # 紧急预警计数
        if w.level == "critical":
            summary["critical_count"] += 1

    return {
        "success": True,
        "class_id": class_id,
        "class_name": class_obj.name,
        "summary": summary
    }

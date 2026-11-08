"""
年级管理API
GET /api/grades - 获取年级列表
POST /api/grades - 创建年级
PUT /api/grades/{grade_id} - 更新年级
DELETE /api/grades/{grade_id} - 删除年级
"""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from app.models.database import get_db, Grade
from app.middleware.auth import PermissionChecker

router = APIRouter()


class GradeCreate(BaseModel):
    name: str  # "高一"
    year: int  # 2025


class GradeUpdate(BaseModel):
    name: Optional[str] = None
    year: Optional[int] = None
    status: Optional[int] = None  # 1:在读 0:已毕业


class GradeResponse(BaseModel):
    success: bool
    grade: Optional[dict] = None
    message: str = ""


@router.get("")
async def get_grades(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(PermissionChecker("grade", "read"))
):
    """
    获取年级列表
    """
    school_id = current_user.get("school_id")

    query = db.query(Grade)
    if school_id:
        query = query.filter(Grade.school_id == school_id)

    grades = query.order_by(Grade.year.desc()).all()

    return {
        "success": True,
        "total": len(grades),
        "grades": [
            {
                "grade_id": g.grade_id,
                "name": g.name,
                "year": g.year,
                "status": g.status,
                "school_id": g.school_id
            }
            for g in grades
        ]
    }


@router.post("")
async def create_grade(
    request: Request,
    grade_data: GradeCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(PermissionChecker("grade", "create"))
):
    """
    创建年级
    """
    school_id = current_user.get("school_id")

    # 检查是否已存在同名年级
    existing = db.query(Grade).filter(
        Grade.school_id == school_id,
        Grade.name == grade_data.name
    ).first()
    if existing:
        return {"success": False, "message": f"年级{grade_data.name}已存在"}

    grade_id = f"grade_{grade_data.year}_{grade_data.name}"
    grade = Grade(
        grade_id=grade_id,
        school_id=school_id,
        name=grade_data.name,
        year=grade_data.year,
        status=1
    )
    db.add(grade)
    db.commit()

    return {
        "success": True,
        "message": f"年级{grade_data.name}创建成功",
        "grade_id": grade_id
    }


@router.put("/{grade_id}")
async def update_grade(
    grade_id: str,
    request: Request,
    grade_data: GradeUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(PermissionChecker("grade", "update"))
):
    """
    更新年级
    """
    grade = db.query(Grade).filter(Grade.grade_id == grade_id).first()
    if not grade:
        return {"success": False, "message": "年级不存在"}

    if grade_data.name is not None:
        grade.name = grade_data.name
    if grade_data.year is not None:
        grade.year = grade_data.year
    if grade_data.status is not None:
        grade.status = grade_data.status

    db.commit()

    return {
        "success": True,
        "message": "年级信息已更新"
    }


@router.delete("/{grade_id}")
async def delete_grade(
    grade_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(PermissionChecker("grade", "delete"))
):
    """
    删除年级（需先清空班级）
    """
    grade = db.query(Grade).filter(Grade.grade_id == grade_id).first()
    if not grade:
        return {"success": False, "message": "年级不存在"}

    # 检查是否有班级
    from app.models.database import Class
    classes = db.query(Class).filter(Class.grade_id == grade_id).all()
    if classes:
        return {
            "success": False,
            "message": f"年级下有{len(classes)}个班级，请先删除班级"
        }

    db.delete(grade)
    db.commit()

    return {
        "success": True,
        "message": "年级已删除"
    }

"""
学校设置API
GET /api/school - 获取学校信息
PUT /api/school - 更新学校信息
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session

from app.models.database import get_db, School
from app.middleware.auth import PermissionChecker

router = APIRouter()


class SchoolUpdate(BaseModel):
    name: Optional[str] = None
    region: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    current_term: Optional[str] = None
    subjects: Optional[List[str]] = None


class SchoolResponse(BaseModel):
    success: bool
    school: Optional[dict] = None
    message: str = ""


@router.get("")
async def get_school(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(PermissionChecker("school", "read"))
):
    """
    获取学校信息
    """
    school_id = current_user.get("school_id")

    # admin可以看任何学校
    if current_user["role"] == "admin" and not school_id:
        # 尝试获取第一个学校
        school = db.query(School).first()
    else:
        school = db.query(School).filter(School.school_id == school_id).first()

    if not school:
        return SchoolResponse(success=False, message="学校不存在")

    return SchoolResponse(
        success=True,
        school={
            "school_id": school.school_id,
            "name": school.name,
            "region": school.region,
            "address": school.address,
            "phone": school.phone,
            "current_term": school.current_term,
            "subjects": school.subjects or []
        }
    )


@router.put("")
async def update_school(
    request: Request,
    school_update: SchoolUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(PermissionChecker("school", "update"))
):
    """
    更新学校信息
    只有admin可以更新
    """
    school_id = current_user.get("school_id")

    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="只有管理员可以修改学校信息")

    # admin可以修改任何学校
    if current_user["role"] == "admin" and not school_id:
        school = db.query(School).first()
    else:
        school = db.query(School).filter(School.school_id == school_id).first()

    if not school:
        return SchoolResponse(success=False, message="学校不存在")

    # 更新字段
    if school_update.name is not None:
        school.name = school_update.name
    if school_update.region is not None:
        school.region = school_update.region
    if school_update.address is not None:
        school.address = school_update.address
    if school_update.phone is not None:
        school.phone = school_update.phone
    if school_update.current_term is not None:
        school.current_term = school_update.current_term
    if school_update.subjects is not None:
        school.subjects = school_update.subjects

    db.commit()

    return SchoolResponse(
        success=True,
        message="学校信息已更新",
        school={
            "school_id": school.school_id,
            "name": school.name,
            "region": school.region,
            "address": school.address,
            "phone": school.phone,
            "current_term": school.current_term,
            "subjects": school.subjects or []
        }
    )


@router.post("")
async def create_school(
    request: Request,
    school_data: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(PermissionChecker("school", "create"))
):
    """
    创建学校（仅admin）
    """
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="只有管理员可以创建学校")

    # 检查是否已有学校
    existing = db.query(School).first()
    if existing:
        return SchoolResponse(success=False, message="学校已存在，请直接编辑")

    school = School(
        school_id=school_data.get("school_id", "school_001"),
        name=school_data.get("name", "新学校"),
        region=school_data.get("region"),
        address=school_data.get("address"),
        phone=school_data.get("phone"),
        current_term=school_data.get("current_term"),
        subjects=school_data.get("subjects", ["语文", "数学", "英语"])
    )
    db.add(school)
    db.commit()

    return SchoolResponse(
        success=True,
        message="学校创建成功",
        school={
            "school_id": school.school_id,
            "name": school.name
        }
    )

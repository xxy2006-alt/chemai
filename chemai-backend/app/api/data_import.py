"""
历史数据导入 API

学校上线时的数据入口：学籍名册 / 教学安排 / 历次考试成绩（含逐题明细）。
权限：学校管理员 / 教务管理员。
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.middleware.auth import PermissionChecker
from app.services.data_import import data_import_service

router = APIRouter(prefix="/api/import", tags=["data-import"])


class RosterRow(BaseModel):
    class_name: str
    student_no: str
    name: str


class RosterImportRequest(BaseModel):
    rows: List[RosterRow] = Field(..., min_length=1)
    grade_name: Optional[str] = None
    grade_year: Optional[int] = None


class TeachingRow(BaseModel):
    teacher_id: str
    teacher_name: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    role: str = "teacher"
    class_name: str
    subject: str = "化学"
    is_class_teacher: bool = False
    grade_name: Optional[str] = None
    grade_year: Optional[int] = None


class TeachingImportRequest(BaseModel):
    rows: List[TeachingRow] = Field(..., min_length=1)


class QuestionSpec(BaseModel):
    no: str
    qtype: str = "single_choice"
    full_score: float
    answer: Optional[str] = None
    content: Optional[str] = None
    options: Optional[List[str]] = None
    analysis: Optional[str] = None
    knowledge_points: Optional[List[str]] = None
    probe_dimension: Optional[str] = None  # concept/reading/expression
    difficulty: int = 3


class ScoreRow(BaseModel):
    student_no: str
    total: Optional[float] = None
    items: Optional[dict] = None
    answer_texts: Optional[dict] = None


class ExamImportRequest(BaseModel):
    name: str
    class_name: str
    subject: str = "化学"
    exam_date: Optional[str] = None
    grade_name: Optional[str] = None
    grade_year: Optional[int] = None
    questions: Optional[List[QuestionSpec]] = None
    scores: List[ScoreRow] = Field(default_factory=list)


def _operator(current_user: dict) -> str:
    return (
        current_user.get("teacher_id")
        or current_user.get("username")
        or "import"
    )


@router.post("/roster")
async def import_roster(
    request: RosterImportRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(PermissionChecker("class", "create")),
):
    """学籍名册导入：按学号去重，已存在跳过"""
    try:
        return data_import_service.import_roster(
            db, _operator(current_user),
            [row.model_dump() for row in request.rows],
            grade_name=request.grade_name,
            grade_year=request.grade_year,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"名册导入失败: {e}")


@router.post("/teaching-assignments")
async def import_teaching_assignments(
    request: TeachingImportRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(PermissionChecker("teacher", "create")),
):
    """教学安排导入：教师建档 + 任教关系"""
    try:
        return data_import_service.import_teaching_assignments(
            db, _operator(current_user),
            [row.model_dump() for row in request.rows],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"教学安排导入失败: {e}")


@router.post("/exam")
async def import_exam(
    request: ExamImportRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(PermissionChecker("exam", "create")),
):
    """历次考试成绩导入：同班同名同日期幂等；逐题明细落题目与作答"""
    try:
        payload = request.model_dump()
        return data_import_service.import_exam(db, _operator(current_user), payload)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"成绩导入失败: {e}")

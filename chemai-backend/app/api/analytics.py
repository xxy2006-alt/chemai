"""
P2-2: 数据分析API
提供班级学情数据、学生排名、障碍分布等分析端点
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.middleware.auth import PermissionChecker
from app.middleware.scope import ScopeGuard
from app.models.database import get_db, Teacher, StudentAnswer
from app.services.data_visualization import DataVisualizationService

router = APIRouter()


class ClassOverviewResponse(BaseModel):
    """班级概览响应"""
    class_id: str
    class_name: str
    student_count: int
    total_practice: int
    total_exams: int
    overall_avg_score: float
    grade: str


class StudentRankingItem(BaseModel):
    """学生排名项"""
    student_id: str
    student_name: str
    avg_score: float
    completion_rate: float
    error_rate: float
    consecutive_days: int
    exercises_completed: int


class BarrierDistributionResponse(BaseModel):
    """障碍分布响应"""
    distribution: Dict[str, float]
    total: int
    labels: List[str]


class KnowledgeHeatmapItem(BaseModel):
    """知识点热力图项"""
    knowledge_point: str
    error_rate: float
    total_questions: int
    level: str  # high/medium/low


class ScoreDistributionResponse(BaseModel):
    """成绩分布响应"""
    distribution: Dict[str, int]
    labels: List[str]
    values: List[int]


class PracticeTrendItem(BaseModel):
    """练习趋势项"""
    date: str
    day_name: str
    practice_count: int
    completion_rate: float


class TeacherWorkloadResponse(BaseModel):
    """教师工作量响应"""
    questions_created: int
    corrections: int
    warnings_processed: int
    exams_arranged: int


class ClassComparisonItem(BaseModel):
    """班级对比项"""
    class_id: str
    class_name: str
    student_count: int
    avg_score: float
    metric_value: float


class TopBottomStudentsResponse(BaseModel):
    """TOP/BOTTOM学生响应"""
    top: List[StudentRankingItem]
    bottom: List[StudentRankingItem]


class StudentPersonalStatsResponse(BaseModel):
    """学生个人统计响应"""
    student_id: str
    student_name: str
    total_exercises: int
    total_answers: int
    accuracy: float
    consecutive_days: int
    barrier_breakdown: Dict[str, float]
    knowledge_mastery: List[Dict[str, Any]]


@router.get("/class/{class_id}/overview")
async def get_class_overview(
    class_id: str, _: None = Depends(ScopeGuard("class_id")), db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("analysis", "read"))):
    """
    获取班级概览数据
    """
    service = DataVisualizationService(db)
    overview = service.get_class_overview(class_id)

    if not overview:
        raise HTTPException(status_code=404, detail="班级不存在")

    return {"success": True, **overview}


@router.get("/class/{class_id}/ranking")
async def get_student_ranking(
    class_id: str,
    _: None = Depends(ScopeGuard("class_id")),
    metric: str = "avg_score",
    limit: int = 10,
    order: str = "desc",
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("analysis", "read")),
):
    """
    获取学生排名
    metric: avg_score / completion_rate / error_rate / consecutive_days
    """
    service = DataVisualizationService(db)
    rankings = service.get_student_ranking(class_id, metric, limit, order)

    return {
        "success": True,
        "class_id": class_id,
        "metric": metric,
        "count": len(rankings),
        "rankings": rankings
    }


@router.get("/class/{class_id}/top-bottom")
async def get_top_bottom_students(
    class_id: str,
    _: None = Depends(ScopeGuard("class_id")),
    limit: int = 5,
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("analysis", "read")),
):
    """
    获取班级TOP和BOTTOM学生
    """
    service = DataVisualizationService(db)
    result = service.get_top_bottom_students(class_id, limit)

    return {
        "success": True,
        "class_id": class_id,
        "top": result["top"],
        "bottom": result["bottom"]
    }


@router.get("/class/{class_id}/barrier-distribution")
async def get_barrier_distribution(
    class_id: str,
    _: None = Depends(ScopeGuard("class_id")),
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("analysis", "read")),
):
    """
    获取班级障碍类型分布
    """
    service = DataVisualizationService(db)
    distribution = service.get_barrier_distribution(class_id)

    return {
        "success": True,
        "class_id": class_id,
        **distribution
    }


@router.get("/class/{class_id}/knowledge-heatmap")
async def get_knowledge_heatmap(
    class_id: str,
    _: None = Depends(ScopeGuard("class_id")),
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("analysis", "read")),
):
    """
    获取知识点掌握热力图
    """
    service = DataVisualizationService(db)
    heatmap = service.get_knowledge_heatmap(class_id)

    return {
        "success": True,
        "class_id": class_id,
        "count": len(heatmap),
        "heatmap": heatmap
    }


@router.get("/class/{class_id}/score-distribution")
async def get_score_distribution(
    class_id: str,
    _: None = Depends(ScopeGuard("class_id")),
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("analysis", "read")),
):
    """
    获取成绩分布直方图
    """
    service = DataVisualizationService(db)
    distribution = service.get_score_distribution(class_id)

    return {
        "success": True,
        "class_id": class_id,
        **distribution
    }


@router.get("/class/{class_id}/practice-trend")
async def get_practice_trend(
    class_id: str,
    _: None = Depends(ScopeGuard("class_id")),
    days: int = 7,
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("analysis", "read")),
):
    """
    获取练习完成趋势
    """
    service = DataVisualizationService(db)
    trend = service.get_practice_trend(class_id, days)

    return {
        "success": True,
        "class_id": class_id,
        "days": days,
        "trend": trend
    }


@router.get("/teacher/{teacher_id}/workload")
async def get_teacher_workload(
    teacher_id: str,
    _: None = Depends(ScopeGuard("teacher_id", kind="teacher")),
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("analysis", "read")),
):
    """
    获取教师工作量统计
    """
    # 验证教师存在
    teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="教师不存在")

    service = DataVisualizationService(db)
    workload = service.get_teacher_workload(teacher_id)

    return {
        "success": True,
        "teacher_id": teacher_id,
        "teacher_name": teacher.name,
        **workload
    }


@router.get("/teacher/{teacher_id}/class-comparison")
async def get_class_comparison(
    teacher_id: str,
    _: None = Depends(ScopeGuard("teacher_id", kind="teacher")),
    metric: str = "avg_score",
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("analysis", "read")),
):
    """
    获取教师所辖班级对比
    """
    teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="教师不存在")

    service = DataVisualizationService(db)
    comparison = service.get_class_comparison(teacher_id, metric)

    return {
        "success": True,
        "teacher_id": teacher_id,
        "metric": metric,
        "classes": comparison
    }


@router.get("/student/{student_id}/personal-stats")
async def get_student_personal_stats(
    student_id: str,
    _: None = Depends(ScopeGuard("student_id", kind="student")),
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("analysis", "read", allow_self=True)),
):
    """
    获取学生个人统计数据
    """
    service = DataVisualizationService(db)
    stats = service.get_student_personal_stats(student_id)

    if not stats:
        raise HTTPException(status_code=404, detail="学生不存在")

    return {
        "success": True,
        **stats
    }


@router.get("/dashboard/teacher/{teacher_id}")
async def get_teacher_dashboard(
    teacher_id: str,
    _: None = Depends(ScopeGuard("teacher_id", kind="teacher")),
    class_id: Optional[str] = None,
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("analysis", "read")),
):
    """
    获取教师端数据大盘综合数据
    包含班级概览、学生排名、障碍分布、知识点热力图等
    """
    from app.models.database import TeacherClassSubject

    teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="教师不存在")

    service = DataVisualizationService(db)

    # 获取教师所辖班级列表
    teacher_classes = db.query(TeacherClassSubject).filter(
        TeacherClassSubject.teacher_id == teacher_id
    ).all()
    class_ids = [tc.class_id for tc in teacher_classes]

    if not class_ids:
        return {
            "success": True,
            "teacher_id": teacher_id,
            "teacher_name": teacher.name,
            "classes": [],
            "workload": {"questions_created": 0, "corrections": 0, "warnings_processed": 0, "exams_arranged": 0}
        }

    # 如果指定了班级，只返回该班级数据
    if class_id and class_id in class_ids:
        classes_data = [{
            "class_id": class_id,
            "overview": service.get_class_overview(class_id),
            "top_bottom": service.get_top_bottom_students(class_id, limit=3),
            "barrier_distribution": service.get_barrier_distribution(class_id),
            "knowledge_heatmap": service.get_knowledge_heatmap(class_id)[:10],
            "score_distribution": service.get_score_distribution(class_id),
            "practice_trend": service.get_practice_trend(class_id, days=7)
        }]
    else:
        # 返回所有班级对比数据
        classes_data = []
        for cid in class_ids:
            overview = service.get_class_overview(cid)
            rankings = service.get_student_ranking(cid, metric="avg_score", limit=100)
            avg_score = sum(s["avg_score"] for s in rankings) / len(rankings) if rankings else 0

            classes_data.append({
                "class_id": cid,
                "class_name": overview.get("class_name", ""),
                "student_count": overview.get("student_count", 0),
                "avg_score": round(avg_score, 1),
                "total_practice": overview.get("total_practice", 0)
            })

    # 获取教师工作量
    workload = service.get_teacher_workload(teacher_id)

    return {
        "success": True,
        "teacher_id": teacher_id,
        "teacher_name": teacher.name,
        "classes": classes_data,
        "workload": workload
    }


@router.get("/dashboard/student/{student_id}")
async def get_student_dashboard(
    student_id: str,
    _: None = Depends(ScopeGuard("student_id", kind="student")),
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("analysis", "read", allow_self=True)),
):
    """
    获取学生端个人数据看板
    包含练习统计、知识点掌握、障碍类型分布等
    """
    service = DataVisualizationService(db)
    stats = service.get_student_personal_stats(student_id)

    if not stats:
        raise HTTPException(status_code=404, detail="学生不存在")

    # 获取最近练习趋势(仅该学生)
    from datetime import timedelta

    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)

    answers = db.query(StudentAnswer).filter(
        StudentAnswer.student_id == student_id,
        StudentAnswer.answered_at >= start_date
    ).all()

    # 按日统计
    daily_stats = {}
    for answer in answers:
        day = answer.answered_at.strftime("%Y-%m-%d")
        if day not in daily_stats:
            daily_stats[day] = {"total": 0, "correct": 0}
        daily_stats[day]["total"] += 1
        if answer.is_correct:
            daily_stats[day]["correct"] += 1

    trend = []
    for i in range(7):
        date = start_date + timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        day_data = daily_stats.get(date_str, {"total": 0, "correct": 0})
        accuracy = round(day_data["correct"] / day_data["total"] * 100, 1) if day_data["total"] > 0 else 0
        trend.append({
            "date": date_str,
            "day_name": date.strftime("%m/%d"),
            "questions": day_data["total"],
            "accuracy": accuracy
        })

    return {
        "success": True,
        **stats,
        "weekly_trend": trend
    }


@router.get("/dashboard/parent/{student_id}")
async def get_parent_child_dashboard(
    student_id: str,
    _: None = Depends(ScopeGuard("student_id", kind="student")),
    db: Session = Depends(get_db),
    _perm: None = Depends(PermissionChecker("analysis", "read", allow_self=True)),
):
    """
    获取家长端子女学习数据(简化版)
    核心指标: 完成率、正确率、连续天数、预警状态
    """
    service = DataVisualizationService(db)
    stats = service.get_student_personal_stats(student_id)

    if not stats:
        raise HTTPException(status_code=404, detail="学生不存在")

    # 简化数据用于家长端展示
    return {
        "success": True,
        "student_id": student_id,
        "student_name": stats.get("student_name", ""),
        "summary": {
            "accuracy": stats.get("accuracy", 0),
            "consecutive_days": stats.get("consecutive_days", 0),
            "total_exercises": stats.get("total_exercises", 0),
            "weak_knowledge_count": len([k for k in stats.get("knowledge_mastery", []) if k["mastery_rate"] < 60])
        },
        "knowledge_mastery": stats.get("knowledge_mastery", [])[:5],  # 只显示前5个
        "barrier_breakdown": stats.get("barrier_breakdown", {})
    }

"""
F3: 三层错题报告生成 API
基于PRD v1.0完整版功能规格
注: 家长摘要版暂不做，仅实现老师详情版+学生筛选版
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.middleware.auth import PermissionChecker, get_current_user
from app.middleware.scope import RequestScope, ScopeGuard
from app.models.database import (
    ExamRecord, Question, StudentAnswer, Student,
    get_db, Teacher, Class, RecordType, TeacherClassSubject
)

router = APIRouter()


# 知识点典型错误映射
_KP_TYPICAL_ERRORS = {
    "盐类水解": "混淆水解与电离的概念，未理解\"有弱才水解\"原则",
    "电离": "未区分强电解质与弱电解质的电离程度差异",
    "氧化还原": "电子转移方向和数目判断错误",
    "原电池": "正负极判断错误，未理解电子流向",
    "电解池": "阴阳极判断错误，离子放电顺序不清",
    "化学平衡": "平衡移动方向判断错误，未理解勒夏特列原理",
    "反应速率": "影响速率因素分析不全面",
    "元素周期律": "同周期/同主族性质递变规律混淆",
    "有机化学": "官能团性质和反应类型判断错误",
    "物质的量": "公式运用不熟练，计量关系混淆",
}

# 知识点干预建议映射
_KP_INTERVENTIONS = {
    "盐类水解": "建议复习盐类水解的定义，强调\"有弱才水解\"的原则，配合练习判断离子水解程度",
    "电离": "强电解质完全电离，弱电解质部分电离，建议用电离方程式练习巩固",
    "氧化还原": "强化氧化性/还原性强弱判断，建议配平专项练习",
    "原电池": "建议从电子流向入手分析，理解牺牲阳极保护法",
    "电解池": "建议背诵离子放电顺序，结合电解类型练习",
    "化学平衡": "建议理解平衡常数含义，多做平衡移动判断题",
    "反应速率": "建议掌握活化能概念，理解温度/浓度/压强对速率影响",
    "元素周期律": "建议用表格对比同周期同主族性质递变",
    "有机化学": "建议从官能团角度系统梳理性质，多做有机推断题",
    "物质的量": "建议用公式卡片法记忆n=m/M=V/Vm=cV等公式",
}

# 鼓励语
_ENGOURAGEMENTS_CORRECT = [
    "太棒了！这道题完全正确！",
    "完美！你对这部分知识掌握得很扎实！",
    "正确！继续保持这样的状态！",
    "厉害！这个问题回答得很准确！",
]

_ENGOURAGEMENTS_WRONG = [
    "别灰心，这道题确实有难度，找到问题所在就是进步的开始！",
    "这道题考察的知识点比较综合，建议先梳理相关概念再重新思考。",
    "不要紧，很多同学在这类题目上都会犯错，关键是要理解其中的原理。",
    "发现错误就是进步的开始，把这道题的知识点搞清楚，下次一定能做对！",
]


def _get_typical_error(knowledge_points: List[str]) -> str:
    """根据知识点生成典型错误描述"""
    for kp in knowledge_points:
        if kp in _KP_TYPICAL_ERRORS:
            return _KP_TYPICAL_ERRORS[kp]
    return "对知识点理解不够深入，需加强基础概念学习"


def _get_intervention_suggestion(knowledge_points: List[str]) -> str:
    """根据知识点生成干预建议"""
    suggestions = []
    for kp in knowledge_points:
        if kp in _KP_INTERVENTIONS:
            suggestions.append(_KP_INTERVENTIONS[kp])
    if suggestions:
        return "；".join(suggestions)
    return "建议复习相关知识点，多做练习巩固"


def _get_encouragement(knowledge_points: List[str], is_correct: bool) -> str:
    """生成鼓励语"""
    import random
    if is_correct:
        return random.choice(_ENGOURAGEMENTS_CORRECT)
    else:
        base = random.choice(_ENGOURAGEMENTS_WRONG)
        # 针对性补充
        for kp in knowledge_points:
            if kp in ["盐类水解", "电离"]:
                return base + " 注意区分\"水解\"与\"电离\"的概念。"
            elif kp in ["氧化还原"]:
                return base + " 注意电子转移的方向和数目。"
            elif kp in ["原电池", "电解池"]:
                return base + " 建议从电子流向入手分析。"
        return base


def _generate_summary(score_pct: float) -> str:
    """根据得分百分比生成总体评价"""
    if score_pct >= 90:
        return "你在本次考试中表现非常优秀！继续保持！"
    elif score_pct >= 75:
        return "你在本次考试中表现良好，有少量提升空间，继续加油！"
    elif score_pct >= 60:
        return "你在本次考试中表现中等，建议加强薄弱知识点的学习。"
    elif score_pct >= 40:
        return "这次考试反映出一些知识掌握不扎实，建议认真复习相关章节。"
    else:
        return "不要气馁！这是一个发现问题的好机会，建议从基础概念开始系统复习。"


class TeacherReportQuestion(BaseModel):
    """老师详情版 - 错题"""
    question_number: str
    knowledge_points: List[str]
    error_count: int
    error_rate: float
    typical_error: str  # 典型错误原因
    intervention_suggestion: str  # 干预建议


class TeacherReportResponse(BaseModel):
    """老师详情版报告"""
    exam_id: str
    class_id: str
    exam_name: str
    total_students: int
    present_students: int
    avg_score: float
    questions: List[TeacherReportQuestion]
    generated_at: str


class StudentReportQuestion(BaseModel):
    """学生筛选版 - 错题"""
    question_number: str
    knowledge_points: List[str]
    your_answer: str
    correct_answer: str
    encouragement: str  # 鼓励性话语 / 待判定提示
    pending: bool = False  # 判定中/待确认：还没生效，不是答错


class StudentReportResponse(BaseModel):
    """学生筛选版报告"""
    student_id: str
    student_name: str
    exam_name: str
    your_score: Optional[float] = None  # 全部作答判定中时无成绩可呈现（None，不是 0 分）
    class_avg_score: float
    rank: Optional[int] = None  # 班级排名(不显示具体数字,仅做参考)
    questions: List[StudentReportQuestion]
    summary: str  # 总体评价
    generated_at: str
    pending_count: int = 0  # 判定中/待确认的题数（不计入 your_score）


@router.get("/teacher/{record_or_teacher_id}")
async def get_teacher_report(
    record_or_teacher_id: str,
    request: Request,
    _perm: None = Depends(PermissionChecker("analysis", "read", allow_self=False)),
    db: Session = Depends(get_db),
):
    """
    生成老师详情版错题报告
    支持两种模式:
    - exam模式: 传入exam_record_id,返回该次考试的教师报告
    - overview模式: 传入teacher_id,返回该教师的汇总报告

    参数双语义（考试 id / 教师 id），按实际命中类型收窄范围。
    """
    scope = RequestScope.from_user(get_current_user(request), db)

    # 先尝试作为exam_record_id查询
    exam_record = db.query(ExamRecord).filter(
        ExamRecord.record_id == record_or_teacher_id
    ).first()

    if exam_record is not None:
        # exam 模式：按该考试所属班级收窄
        if not scope.allows_class(exam_record.class_id):
            raise HTTPException(status_code=403, detail="无权查看该考试的教师报告")
    else:
        # 作为teacher_id处理,返回教师总览
        teacher = db.query(Teacher).filter(Teacher.teacher_id == record_or_teacher_id).first()
        if not teacher:
            raise HTTPException(status_code=404, detail=f"考试记录或教师 {record_or_teacher_id} 不存在")
        if not scope.allows_teacher(teacher.teacher_id):
            raise HTTPException(status_code=403, detail="无权查看该教师的报告")

        # 查询该教师所带班级的所有考试
        # （阶段 6.2：原先读 `classes.teacher_id`，那个字段恒为 NULL —— 于是 class_ids
        #  恒为空、教师总览永远返回空考试列表。真源是任课关系表）
        classes = (
            db.query(Class)
            .join(TeacherClassSubject, TeacherClassSubject.class_id == Class.class_id)
            .filter(TeacherClassSubject.teacher_id == teacher.teacher_id)
            .all()
        )
        class_ids = [c.class_id for c in classes]
        exams = db.query(ExamRecord).filter(
            ExamRecord.class_id.in_(class_ids)
        ).order_by(ExamRecord.exam_date.desc()).limit(20).all()

        exam_list = []
        total_avg = 0
        for e in exams:
            class_obj = db.query(Class).filter(Class.class_id == e.class_id).first()
            exam_list.append({
                "record_id": e.record_id,
                "exam_name": e.name,
                "class_name": class_obj.name if class_obj else "",
                "exam_date": e.exam_date.strftime("%Y-%m-%d") if e.exam_date else None,
                "avg_score": e.avg_score,
                "total_students": e.total_students or 0,
                "present_students": e.present_students or 0
            })
            if e.avg_score:
                total_avg += e.avg_score

        return {
            "success": True,
            "type": "overview",
            "teacher_id": teacher.teacher_id,
            "teacher_name": teacher.name,
            "total_classes": len(classes),
            "total_exams": len(exams),
            "overall_avg_score": round(total_avg / len(exams), 1) if exams else 0,
            "exams": exam_list
        }

    # 查询该考试的所有题目
    questions = db.query(Question).filter(
        Question.record_id == record_or_teacher_id
    ).all()

    # 查询学生答题记录
    question_stats = []
    total_errors = 0
    present_students = exam_record.present_students or 0

    from app.services.grading_center import effective_conditions

    for q in questions:
        # 统计该题错误人数（只认生效行：待判定/未确认不是错答）
        wrong_answers = db.query(StudentAnswer).filter(
            StudentAnswer.question_id == q.question_id,
            StudentAnswer.is_correct.is_(False),
            effective_conditions(),
        ).count()

        error_rate = wrong_answers / present_students if present_students > 0 else 0

        # 根据知识点生成典型错误和干预建议
        kps = q.knowledge_points or []
        typical_error = _get_typical_error(kps)
        intervention = _get_intervention_suggestion(kps)

        question_stats.append(TeacherReportQuestion(
            question_number=q.question_id.split("_")[-1] if "_" in q.question_id else q.question_id,
            knowledge_points=kps,
            error_count=wrong_answers,
            error_rate=round(error_rate, 3),
            typical_error=typical_error,
            intervention_suggestion=intervention
        ))

        total_errors += wrong_answers

    # 按错误率排序
    question_stats.sort(key=lambda x: x.error_rate, reverse=True)

    # 生成时间
    generated_at = (
        exam_record.exam_date.strftime("%Y-%m-%d %H:%M")
        if exam_record.exam_date
        else datetime.now().strftime("%Y-%m-%d %H:%M")
    )
    return TeacherReportResponse(
        exam_id=record_or_teacher_id,
        class_id=exam_record.class_id,
        exam_name=exam_record.name,
        total_students=exam_record.total_students or 0,
        present_students=present_students,
        avg_score=exam_record.avg_score or 0,
        questions=question_stats,
        generated_at=generated_at
    )


@router.get("/student/{student_id}/kp-mastery")
async def get_student_kp_mastery(
    student_id: str,
    _perm: None = Depends(PermissionChecker("analysis", "read", allow_self=True)),
    _scope: None = Depends(ScopeGuard("student_id", kind="student")),
    db: Session = Depends(get_db),
):
    """学生知识点掌握报告"""
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"学生 {student_id} 不存在")

    # 查询该学生所有答题记录
    answers = db.query(StudentAnswer).filter(
        StudentAnswer.student_id == student_id
    ).all()

    # 按知识点聚合
    kp_correct = {}
    kp_total = {}
    for a in answers:
        q = db.query(Question).filter(Question.question_id == a.question_id).first()
        if q and q.knowledge_points:
            for kp in q.knowledge_points:
                if kp not in kp_total:
                    kp_total[kp] = 0
                    kp_correct[kp] = 0
                kp_total[kp] += 1
                if a.is_correct:
                    kp_correct[kp] += 1

    mastery_list = []
    for kp, total in kp_total.items():
        mastery_list.append({
            "knowledge_point": kp,
            "total_questions": total,
            "correct_count": kp_correct.get(kp, 0),
            "mastery": round(kp_correct.get(kp, 0) / total * 100, 1) if total > 0 else 0
        })

    mastery_list.sort(key=lambda x: x["mastery"])

    return {
        "success": True,
        "student_id": student_id,
        "student_name": student.name,
        "kp_mastery": mastery_list
    }


@router.get("/student/{student_id}/barrier-change")
async def get_student_barrier_change(
    student_id: str,
    _perm: None = Depends(PermissionChecker("analysis", "read", allow_self=True)),
    _scope: None = Depends(ScopeGuard("student_id", kind="student")),
    db: Session = Depends(get_db),
):
    """学生障碍类型变化报告"""
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"学生 {student_id} 不存在")

    # 按考试分组统计barrier分布变化
    exams = db.query(ExamRecord).join(
        StudentAnswer, ExamRecord.record_id == StudentAnswer.exam_record_id
    ).filter(
        StudentAnswer.student_id == student_id
    ).order_by(ExamRecord.exam_date.asc()).all()

    timeline = []
    seen = set()
    for e in exams:
        if e.record_id in seen:
            continue
        seen.add(e.record_id)
        answers = db.query(StudentAnswer).filter(
            StudentAnswer.exam_record_id == e.record_id,
            StudentAnswer.student_id == student_id
        ).all()

        barrier_dist = {"concept": 0, "reading": 0, "expression": 0}
        for a in answers:
            if a.barrier_type and not a.is_correct:
                bt = a.barrier_type.value
                barrier_dist[bt] = barrier_dist.get(bt, 0) + 1

        timeline.append({
            "exam_id": e.record_id,
            "exam_name": e.name,
            "exam_date": e.exam_date.strftime("%Y-%m-%d") if e.exam_date else None,
            "barrier_distribution": barrier_dist
        })

    return {
        "success": True,
        "student_id": student_id,
        "student_name": student.name,
        "current_barrier": student.barrier_type,
        "timeline": timeline
    }


@router.get("/student/{student_id}/trend")
async def get_student_learning_trend(
    student_id: str,
    _perm: None = Depends(PermissionChecker("analysis", "read", allow_self=True)),
    _scope: None = Depends(ScopeGuard("student_id", kind="student")),
    db: Session = Depends(get_db),
):
    """学生学习趋势报告"""
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"学生 {student_id} 不存在")

    # 查询所有考试的成绩变化
    exams = db.query(ExamRecord).join(
        StudentAnswer, ExamRecord.record_id == StudentAnswer.exam_record_id
    ).filter(
        StudentAnswer.student_id == student_id
    ).order_by(ExamRecord.exam_date.asc()).all()

    trend_data = []
    seen = set()
    for e in exams:
        if e.record_id in seen:
            continue
        seen.add(e.record_id)
        answers = db.query(StudentAnswer).filter(
            StudentAnswer.exam_record_id == e.record_id,
            StudentAnswer.student_id == student_id
        ).all()
        correct = sum(1 for a in answers if a.is_correct)
        total = len(answers)
        trend_data.append({
            "exam_id": e.record_id,
            "exam_name": e.name,
            "exam_date": e.exam_date.strftime("%Y-%m-%d") if e.exam_date else None,
            "score": round(correct / total * 100, 1) if total > 0 else 0,
            "correct_count": correct,
            "total_questions": total
        })

    return {
        "success": True,
        "student_id": student_id,
        "student_name": student.name,
        "trend": trend_data,
        "total_exams": len(trend_data),
        "latest_score": trend_data[-1]["score"] if trend_data else 0,
        "earliest_score": trend_data[0]["score"] if trend_data else 0
    }



@router.get("/student/{exam_record_id}/{student_id}", response_model=StudentReportResponse)
async def get_student_report(
    exam_record_id: str,
    student_id: str,
    _perm: None = Depends(PermissionChecker("analysis", "read", allow_self=True)),
    _scope: None = Depends(ScopeGuard("student_id", kind="student")),
    _exam_scope: None = Depends(ScopeGuard("exam_record_id", kind="exam_record")),
    db: Session = Depends(get_db)
):
    """
    生成学生筛选版错题报告
    仅呈现个人错题(不显示他人成绩); 配合鼓励性话语
    """
    # 查询学生信息
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"学生 {student_id} 不存在")

    # 查询考试记录
    exam_record = db.query(ExamRecord).filter(
        ExamRecord.record_id == exam_record_id
    ).first()
    if not exam_record:
        raise HTTPException(status_code=404, detail=f"考试记录 {exam_record_id} 不存在")

    # 查询该学生的答题记录
    student_answers = db.query(StudentAnswer).filter(
        StudentAnswer.exam_record_id == exam_record_id,
        StudentAnswer.student_id == student_id
    ).all()

    # 查询该考试的题目
    questions = db.query(Question).filter(
        Question.record_id == exam_record_id
    ).all()
    question_map = {q.question_id: q for q in questions}

    # 构建学生错题列表：未生效行（判定中/缺标准答案/待教师确认）不算成绩，
    # 也不提前回显标准答案（ADR-0013：学生看到「判定中」而不是「答错」）
    from app.services.grading_center import is_effective

    wrong_questions = []
    total_score = 0
    max_possible_score = 0
    pending_count = 0

    for ans in student_answers:
        q = question_map.get(ans.question_id)
        if not q:
            continue

        if not is_effective(ans):
            pending_count += 1
            wrong_questions.append(StudentReportQuestion(
                question_number=q.question_id.split("_")[-1] if "_" in q.question_id else q.question_id,
                knowledge_points=q.knowledge_points or [],
                your_answer=ans.student_answer or "",
                correct_answer="",
                encouragement="本题判定中，成绩待教师确认后更新",
                pending=True,
            ))
            continue

        max_score = 6  # 默认每题6分
        max_possible_score += max_score

        if ans.is_correct:
            total_score += max_score
            encouragement = _get_encouragement(q.knowledge_points or [], is_correct=True)
            wrong_questions.append(StudentReportQuestion(
                question_number=q.question_id.split("_")[-1] if "_" in q.question_id else q.question_id,
                knowledge_points=q.knowledge_points or [],
                your_answer=ans.student_answer or "",
                correct_answer=q.answer or "",
                encouragement=encouragement
            ))
        else:
            encouragement = _get_encouragement(q.knowledge_points or [], is_correct=False)
            wrong_questions.append(StudentReportQuestion(
                question_number=q.question_id.split("_")[-1] if "_" in q.question_id else q.question_id,
                knowledge_points=q.knowledge_points or [],
                your_answer=ans.student_answer or "",
                correct_answer=q.answer or "",
                encouragement=encouragement
            ))

    # 计算百分比得分：整卷都还没生效时没有成绩可呈现（按 0 分给评价与每题「判定中」自相矛盾）
    if max_possible_score > 0:
        your_score_pct = total_score / max_possible_score * 100
        your_score, summary = round(your_score_pct, 1), _generate_summary(your_score_pct)
    elif pending_count > 0:
        your_score, summary = None, "本卷作答正在判定中，成绩待教师确认后更新。"
    else:
        your_score, summary = 0.0, _generate_summary(0)

    # 生成时间
    generated_at = (
        exam_record.exam_date.strftime("%Y-%m-%d %H:%M")
        if exam_record.exam_date
        else datetime.now().strftime("%Y-%m-%d %H:%M")
    )
    return StudentReportResponse(
        student_id=student_id,
        student_name=student.name,
        exam_name=exam_record.name,
        your_score=your_score,
        class_avg_score=exam_record.avg_score or 0,
        rank=None,  # 不显示具体排名
        questions=wrong_questions,
        summary=summary,
        generated_at=generated_at,
        pending_count=pending_count,
    )


@router.post("/send-to-students/{exam_record_id}")
async def send_report_to_students(
    exam_record_id: str,
    _perm: None = Depends(PermissionChecker("analysis", "create", allow_self=False)),
    _scope: None = Depends(ScopeGuard("exam_record_id", kind="exam_record")),
    db: Session = Depends(get_db),
):
    """
    一键发送学生版报告给全班学生
    推送至学生端App查看
    """
    # 查询考试记录
    exam_record = db.query(ExamRecord).filter(
        ExamRecord.record_id == exam_record_id
    ).first()

    if not exam_record:
        raise HTTPException(status_code=404, detail=f"考试记录 {exam_record_id} 不存在")

    # 查询该班级所有学生
    from app.models.database import Student, Class
    students = db.query(Student).join(Class).filter(
        Class.class_id == exam_record.class_id
    ).all()

    # TODO: 实现实际的推送逻辑（短信/邮件/App推送）
    # 目前仅返回模拟成功
    sent_count = len(students)

    return {
        "success": True,
        "sent_count": sent_count,
        "failed_count": 0,
        "message": f"已成功发送{sent_count}份报告"
    }


@router.get("/export/{exam_record_id}")
async def export_report(
    exam_record_id: str,
    format: str = "json",  # json/pdf/excel
    _perm: None = Depends(PermissionChecker("analysis", "read", allow_self=False)),
    _scope: None = Depends(ScopeGuard("exam_record_id", kind="exam_record")),
    db: Session = Depends(get_db)
):
    """
    导出报告
    支持格式: json(默认), pdf, excel
    """
    # 查询考试记录
    exam_record = db.query(ExamRecord).filter(
        ExamRecord.record_id == exam_record_id
    ).first()

    if not exam_record:
        raise HTTPException(status_code=404, detail=f"考试记录 {exam_record_id} 不存在")

    # 获取报告数据
    report_data = await get_teacher_report(exam_record_id, db)

    if format == "json":
        return {
            "success": True,
            "format": "json",
            "data": report_data
        }
    elif format == "pdf":
        # TODO: 实现PDF导出
        return {
            "success": False,
            "format": "pdf",
            "message": "PDF导出功能待实现",
            "download_url": f"/api/report/download/{exam_record_id}.pdf"
        }
    elif format == "excel":
        # TODO: 实现Excel导出
        return {
            "success": False,
            "format": "excel",
            "message": "Excel导出功能待实现",
            "download_url": f"/api/report/download/{exam_record_id}.xlsx"
        }
    else:
        raise HTTPException(status_code=400, detail=f"不支持的格式: {format}")


@router.get("/exam-analytics/{exam_record_id}")
async def get_exam_analytics(
    exam_record_id: str,
    _perm: None = Depends(PermissionChecker("analysis", "read", allow_self=False)),
    _scope: None = Depends(ScopeGuard("exam_record_id", kind="exam_record")),
    db: Session = Depends(get_db),
):
    """考试分析：分数分布 + 完成情况 + 每题错误率."""
    exam = db.query(ExamRecord).filter(ExamRecord.record_id == exam_record_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="考试不存在")

    students = db.query(Student).filter(Student.class_id == exam.class_id).all()
    total_students = len(students)
    completed = 0
    scores = []

    for s in students:
        answers = db.query(StudentAnswer).filter(
            StudentAnswer.exam_record_id == exam_record_id,
            StudentAnswer.student_id == s.student_id,
        ).all()
        if answers:
            completed += 1
            correct = sum(1 for a in answers if a.is_correct)
            scores.append((s.name, correct, len(answers)))

    avg_score = round(sum(s[1] for s in scores) / len(scores), 1) if scores else 0
    completion_pct = round(completed / total_students * 100) if total_students else 0

    # Per-question error rate
    questions = db.query(Question).filter(Question.record_id == exam_record_id).all()
    question_stats = []
    for q in questions:
        answers = db.query(StudentAnswer).filter(
            StudentAnswer.question_id == q.question_id,
            StudentAnswer.exam_record_id == exam_record_id,
        ).all()
        total_ans = len(answers)
        correct_ans = sum(1 for a in answers if a.is_correct)
        error_rate = round((1 - correct_ans / total_ans) * 100) if total_ans else 0
        question_stats.append({
            "question_id": q.question_id,
            "content": (q.content or "")[:80],
            "knowledge_points": q.knowledge_points or [],
            "error_rate": error_rate,
            "answer_count": total_ans,
        })

    question_stats.sort(key=lambda x: x["error_rate"], reverse=True)

    return {
        "success": True,
        "exam_name": exam.name,
        "class_name": exam.class_id,
        "total_students": total_students,
        "completed": completed,
        "completion_pct": completion_pct,
        "avg_score": avg_score,
        "scores": [{"name": s[0], "correct": s[1], "total": s[2]} for s in scores[:30]],
        "top_errors": question_stats[:5],
    }


# ============================================================
# P5-4: 报告模块补充端点
# ============================================================


@router.get("/student/{student_id}")
async def get_student_report_overview(
    student_id: str,
    _perm: None = Depends(PermissionChecker("analysis", "read", allow_self=True)),
    _scope: None = Depends(ScopeGuard("student_id", kind="student")),
    db: Session = Depends(get_db),
):
    """学生报告概览 - 显示最近的考试成绩汇总和障碍趋势"""
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"学生 {student_id} 不存在")

    # 查询该学生最近的考试记录
    exams = db.query(ExamRecord).join(
        StudentAnswer, ExamRecord.record_id == StudentAnswer.exam_record_id
    ).filter(
        StudentAnswer.student_id == student_id
    ).order_by(ExamRecord.exam_date.desc()).limit(10).all()

    exam_results = []
    for e in exams:
        answers = db.query(StudentAnswer).filter(
            StudentAnswer.exam_record_id == e.record_id,
            StudentAnswer.student_id == student_id
        ).all()
        correct = sum(1 for a in answers if a.is_correct)
        total = len(answers)
        exam_results.append({
            "exam_id": e.record_id,
            "exam_name": e.name,
            "exam_date": e.exam_date.strftime("%Y-%m-%d") if e.exam_date else None,
            "score": round(correct / total * 100, 1) if total > 0 else 0,
            "correct_count": correct,
            "total_questions": total
        })

    return {
        "success": True,
        "student_id": student_id,
        "student_name": student.name,
        "class_id": student.class_id,
        "barrier_type": student.barrier_type,
        "exercises_completed": student.exercises_completed or 0,
        "exam_results": exam_results
    }


@router.get("/class/{class_id}")
async def get_class_report_overview(
    class_id: str,
    _perm: None = Depends(PermissionChecker("analysis", "read", allow_self=False)),
    _scope: None = Depends(ScopeGuard("class_id", kind="class")),
    db: Session = Depends(get_db),
):
    """班级报告概览"""
    class_obj = db.query(Class).filter(Class.class_id == class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail=f"班级 {class_id} 不存在")

    exams = db.query(ExamRecord).filter(
        ExamRecord.class_id == class_id,
        ExamRecord.type == RecordType.EXAM
    ).order_by(ExamRecord.exam_date.desc()).limit(20).all()

    exam_stats = []
    for e in exams:
        answers = db.query(StudentAnswer).filter(
            StudentAnswer.exam_record_id == e.record_id
        ).all()
        correct_count = sum(1 for a in answers if a.is_correct)
        total_count = len(answers)
        exam_stats.append({
            "record_id": e.record_id,
            "name": e.name,
            "exam_date": e.exam_date.strftime("%Y-%m-%d") if e.exam_date else None,
            "total_students": e.total_students or 0,
            "present_students": e.present_students or 0,
            "avg_score": e.avg_score,
            "overall_accuracy": round(correct_count / total_count, 2) if total_count > 0 else 0
        })

    return {
        "success": True,
        "class_id": class_id,
        "class_name": class_obj.name,
        "student_count": class_obj.student_count or 0,
        "exams": exam_stats
    }


@router.get("/print/{exam_record_id}")
async def print_report(
    exam_record_id: str,
    type: str = "teacher",  # teacher or student
    _perm: None = Depends(PermissionChecker("analysis", "read", allow_self=False)),
    _scope: None = Depends(ScopeGuard("exam_record_id", kind="exam_record")),
    db: Session = Depends(get_db)
):
    """
    F3: 导出/打印报告为 HTML 页面（浏览器打印即 PDF）
    """
    from app.services.export_service import generate_report_html
    from app.models.database import ExamRecord, Question, StudentAnswer

    exam = db.query(ExamRecord).filter(ExamRecord.record_id == exam_record_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="考试记录不存在")

    # Build exam data
    questions = db.query(Question).filter(Question.record_id == exam_record_id).all()
    question_stats = []
    kp_errors = {}

    for q in questions:
        answers = db.query(StudentAnswer).filter(
            StudentAnswer.question_id == q.question_id
        ).all()
        total = len(answers)
        wrong = sum(1 for a in answers if not a.is_correct)
        rate = wrong / total if total > 0 else 0

        question_stats.append({
            "question_number": q.question_id[-4:],
            "knowledge_points": q.knowledge_points or [],
            "error_count": wrong,
            "error_rate": rate,
        })

        for kp in (q.knowledge_points or []):
            if kp not in kp_errors:
                kp_errors[kp] = {"errors": 0, "total": 0}
            kp_errors[kp]["errors"] += wrong
            kp_errors[kp]["total"] += total

    knowledge_point_stats = [
        {"knowledge_point": kp, "error_count": v["errors"],
         "error_rate": v["errors"] / v["total"] if v["total"] > 0 else 0}
        for kp, v in kp_errors.items()
    ]

    exam_data = {
        "exam_name": exam.name,
        "total_students": exam.total_students,
        "present_students": exam.present_students,
        "avg_score": exam.avg_score or 0,
        "question_stats": question_stats,
        "knowledge_point_stats": knowledge_point_stats,
        "encouragement": "建议重点复习高频错误知识点，针对性练习同类题目。",
    }

    html = generate_report_html(exam_data, report_type=type)
    return HTMLResponse(content=html)


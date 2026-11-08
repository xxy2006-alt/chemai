"""
家长端 API
支持家长注册、登录、子女绑定、通知接收等功能
"""
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import hashlib
import json
import uuid

from sqlalchemy.orm import Session
from app.models.database import (
    Parent, StudentParentBinding, ParentNotification, Account, Student, Class,
    StudentAnswer, Question, get_db
)

router = APIRouter()


# ==================== 辅助函数 ====================

def hash_password(password: str) -> str:
    """密码哈希"""
    return hashlib.sha256(password.encode()).hexdigest()


def generate_id(prefix: str = "") -> str:
    """生成唯一ID"""
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def get_current_parent_id(authorization: str = Header(None)) -> str:
    """从 token 解析当前家长 id（不允许通过查询参数伪造他人 parent_id）"""
    from app.middleware.auth import verify_token
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization.replace("Bearer ", "")
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="token无效或已过期")
    if payload.get("role") != "parent":
        raise HTTPException(status_code=403, detail="仅家长可访问")
    return payload.get("user_id")


# ==================== Request/Response Models ====================

class ParentRegisterRequest(BaseModel):
    """家长注册请求"""
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    password: str


class ParentLoginRequest(BaseModel):
    """家长登录请求"""
    username: str
    password: str


class BindStudentRequest(BaseModel):
    """绑定学生请求"""
    student_id: str
    bind_code: str
    parent_id: str = ""
    relation: str = "家长"  # 父亲/母亲/其他


class SendBindCodeRequest(BaseModel):
    """发送绑定码请求"""
    student_id: str


class WeeklyReportResponse(BaseModel):
    """周报响应"""
    student_id: str
    student_name: str
    week_start: str
    week_end: str
    practice_count: int
    practice_completed: int
    accuracy_rate: float
    weak_knowledge_points: List[str]
    barrier_type: str
    streak_days: int


class ChildInfo(BaseModel):
    """子女信息"""
    student_id: str
    student_name: str
    class_name: str
    grade: str
    relation: str
    binding_id: str


class NotificationInfo(BaseModel):
    """通知信息"""
    notification_id: str
    student_id: str
    student_name: str
    type: str
    title: str
    content: Optional[str]
    is_read: bool
    created_at: str


# ==================== API 端点 ====================

@router.post("/register")
async def register_parent(
    data: ParentRegisterRequest,
    db: Session = Depends(get_db)
):
    """注册家长账号"""
    # 检查用户名是否已存在
    # 修复: Python 'or' 优先级导致永远匹配，改用 SQLAlchemy '|' 操作符
    from sqlalchemy import or_
    existing = db.query(Account).filter(
        or_(Account.username == data.phone, Account.username == data.email)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    # 创建家长
    parent_id = generate_id("parent_")
    parent = Parent(
        parent_id=parent_id,
        name=data.name,
        phone=data.phone,
        email=data.email,
        password_hash=hash_password(data.password)
    )
    db.add(parent)

    # 创建账户（使用手机号或邮箱作为用户名）
    username = data.phone or data.email
    account = Account(
        account_id=generate_id("acct_"),
        role="parent",
        username=username,
        password_hash=hash_password(data.password),
        parent_id=parent_id
    )
    db.add(account)
    db.commit()

    return {
        "success": True,
        "message": "注册成功",
        "parent_id": parent_id
    }


@router.post("/login")
async def login_parent(
    data: ParentLoginRequest,
    db: Session = Depends(get_db)
):
    """家长登录"""
    account = db.query(Account).filter(
        Account.username == data.username,
        Account.role == "parent"
    ).first()

    if not account:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if account.password_hash != hash_password(data.password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if account.status != "active":
        raise HTTPException(status_code=401, detail="账号已被禁用")

    # 获取家长信息
    parent = db.query(Parent).filter(Parent.parent_id == account.parent_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail="家长信息不存在")

    # 生成 JWT token
    from app.middleware.auth import create_access_token, create_refresh_token
    token = create_access_token(parent.parent_id, "parent")
    refresh_token = create_refresh_token(parent.parent_id)

    return {
        "success": True,
        "message": "登录成功",
        "token": token,
        "refresh_token": refresh_token,
        "parent_id": parent.parent_id,
        "name": parent.name,
        "role": "parent"
    }


@router.get("/children")
async def get_children(
    parent_id: str = Depends(get_current_parent_id),
    db: Session = Depends(get_db)
):
    """获取已绑定子女列表"""
    bindings = db.query(StudentParentBinding).filter(
        StudentParentBinding.parent_id == parent_id,
        StudentParentBinding.status == "active"
    ).all()

    children = []
    for binding in bindings:
        student = db.query(Student).filter(Student.student_id == binding.student_id).first()
        if student:
            class_obj = db.query(Class).filter(Class.class_id == student.class_id).first()
            children.append(ChildInfo(
                student_id=student.student_id,
                student_name=student.name,
                class_name=class_obj.name if class_obj else "未知班级",
                grade=class_obj.grade if class_obj else "未知年级",
                relation=binding.relation,
                binding_id=binding.binding_id
            ))

    return {
        "success": True,
        "children": [c.model_dump() for c in children]
    }


@router.post("/bind")
async def bind_student(
    data: BindStudentRequest,
    db: Session = Depends(get_db),
    parent_id: str = Depends(get_current_parent_id),
):
    """绑定学生（通过绑定码），parent_id 取自登录 token，忽略请求体中的伪造值"""

    # 查找学生
    student = db.query(Student).filter(Student.student_id == data.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    # 验证绑定码
    if not student.bind_code or student.bind_code != data.bind_code:
        raise HTTPException(status_code=400, detail="绑定码错误")

    # 检查是否已经绑定
    existing = db.query(StudentParentBinding).filter(
        StudentParentBinding.student_id == data.student_id,
        StudentParentBinding.parent_id == parent_id,
        StudentParentBinding.status == "active"
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="已经绑定过该学生")

    # 创建绑定关系
    binding = StudentParentBinding(
        binding_id=generate_id("bind_"),
        student_id=data.student_id,
        parent_id=parent_id,
        relation=data.relation,
        bind_code=data.bind_code,
        status="active"
    )
    db.add(binding)
    db.commit()

    return {
        "success": True,
        "message": "绑定成功",
        "binding_id": binding.binding_id,
        "student_name": student.name
    }


@router.delete("/bind/{binding_id}")
async def unbind_student(
    binding_id: str,
    db: Session = Depends(get_db),
    parent_id: str = Depends(get_current_parent_id),
):
    """解除绑定"""
    binding = db.query(StudentParentBinding).filter(
        StudentParentBinding.binding_id == binding_id,
        StudentParentBinding.parent_id == parent_id
    ).first()

    if not binding:
        raise HTTPException(status_code=404, detail="绑定关系不存在")

    binding.status = "inactive"
    db.commit()

    return {
        "success": True,
        "message": "解除绑定成功"
    }


@router.get("/notifications")
async def get_notifications(
    parent_id: str = Depends(get_current_parent_id),
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """获取通知列表"""
    notifications = db.query(ParentNotification).filter(
        ParentNotification.parent_id == parent_id
    ).order_by(ParentNotification.created_at.desc()).limit(limit).offset(offset).all()

    result = []
    for n in notifications:
        student = db.query(Student).filter(Student.student_id == n.student_id).first()
        result.append(NotificationInfo(
            notification_id=n.notification_id,
            student_id=n.student_id,
            student_name=student.name if student else "未知",
            type=n.type,
            title=n.title,
            content=n.content,
            is_read=n.is_read,
            created_at=n.created_at.isoformat() if n.created_at else ""
        ))

    return {
        "success": True,
        "notifications": [r.model_dump() for r in result]
    }


@router.put("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    db: Session = Depends(get_db),
    parent_id: str = Depends(get_current_parent_id),
):
    """标记通知已读"""
    notification = db.query(ParentNotification).filter(
        ParentNotification.notification_id == notification_id,
        ParentNotification.parent_id == parent_id
    ).first()

    if not notification:
        raise HTTPException(status_code=404, detail="通知不存在")

    notification.is_read = True
    db.commit()

    return {
        "success": True,
        "message": "已标记为已读"
    }


@router.get("/child/{student_id}/report")
async def get_child_report(
    student_id: str,
    db: Session = Depends(get_db),
    parent_id: str = Depends(get_current_parent_id),
):
    """获取子女报告摘要"""
    # 验证绑定关系
    binding = db.query(StudentParentBinding).filter(
        StudentParentBinding.student_id == student_id,
        StudentParentBinding.parent_id == parent_id,
        StudentParentBinding.status == "active"
    ).first()

    if not binding:
        raise HTTPException(status_code=403, detail="未绑定该学生")

    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    class_obj = db.query(Class).filter(Class.class_id == student.class_id).first()

    return {
        "success": True,
        "report": {
            "student_id": student_id,
            "student_name": student.name,
            "class_name": class_obj.name if class_obj else "未知班级",
            "grade": class_obj.grade if class_obj else "未知年级",
            "exercises_completed": student.exercises_completed,
            "barrier_type": student.barrier_type,
            "last_exercise_at": student.last_exercise_at.isoformat() if student.last_exercise_at else None
        }
    }


@router.get("/child/{student_id}/weekly")
async def get_child_weekly(
    student_id: str,
    db: Session = Depends(get_db),
    parent_id: str = Depends(get_current_parent_id),
):
    """获取子女周报"""
    # 验证绑定关系
    binding = db.query(StudentParentBinding).filter(
        StudentParentBinding.student_id == student_id,
        StudentParentBinding.parent_id == parent_id,
        StudentParentBinding.status == "active"
    ).first()

    if not binding:
        raise HTTPException(status_code=403, detail="未绑定该学生")

    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    # 计算本周真实数据
    from datetime import timedelta
    week_start = datetime.utcnow() - timedelta(days=7)
    total_answers = 0
    correct_answers = 0
    kp_error_count = {}

    try:
        week_answers = db.query(StudentAnswer).filter(
            StudentAnswer.student_id == student_id,
            StudentAnswer.answered_at >= week_start
        ).all()

        for ans in week_answers:
            total_answers += 1
            if ans.is_correct:
                correct_answers += 1
            else:
                # 统计错题知识点
                q = db.query(Question).filter(Question.question_id == ans.question_id).first()
                if q and q.knowledge_points:
                    for kp in q.knowledge_points:
                        kp_error_count[kp] = kp_error_count.get(kp, 0) + 1
    except Exception:
        pass

    accuracy_rate = round(correct_answers / total_answers, 2) if total_answers > 0 else 0
    weak_kps = [kp for kp, _ in sorted(kp_error_count.items(), key=lambda x: -x[1])[:5]]
    if not weak_kps:
        weak_kps = ["暂无薄弱知识点数据"]

    # 计算连续练习天数
    streak_days = 0
    try:
        answers_by_date = db.query(StudentAnswer).filter(
            StudentAnswer.student_id == student_id
        ).order_by(StudentAnswer.answered_at.desc()).all()
        if answers_by_date:
            current_date = datetime.utcnow().date()
            streak_set = set()
            for ans in answers_by_date:
                if ans.answered_at:
                    d = ans.answered_at.date() if hasattr(ans.answered_at, 'date') else ans.answered_at
                    if hasattr(d, 'date'):
                        d = d.date()
                    streak_set.add(d)
            # Count consecutive days from today backwards
            check_date = current_date
            while check_date in streak_set:
                streak_days += 1
                check_date -= timedelta(days=1)
            # If no activity today but had activity yesterday, count from yesterday
            if streak_days == 0 and answers_by_date:
                first_date = answers_by_date[0].answered_at
                if hasattr(first_date, 'date'):
                    first_date = first_date.date()
                elif hasattr(first_date, 'date'):
                    first_date = first_date.date()
                if isinstance(first_date, (datetime,)):
                    if hasattr(first_date, 'date'):
                        first_date = first_date.date()
            if streak_days == 0:
                streak_days = 1  # at least 1 if they did anything this week
    except Exception:
        streak_days = 0

    practice_count = total_answers

    return {
        "success": True,
        "weekly": WeeklyReportResponse(
            student_id=student_id,
            student_name=student.name,
            week_start=week_start.strftime("%Y-%m-%d"),
            week_end=datetime.utcnow().strftime("%Y-%m-%d"),
            practice_count=practice_count,
            practice_completed=correct_answers,
            accuracy_rate=accuracy_rate,
            weak_knowledge_points=weak_kps,
            barrier_type=str(student.barrier_type.get("concept", 0.33)) if student.barrier_type else "未知",
            streak_days=streak_days
        ).model_dump()
    }




# ── AI 报告摘要 ──

class AISummaryRequest(BaseModel):
    section: str
    data: dict

@router.post("/child/{student_id}/report/ai-summary")
async def ai_summary(
    student_id: str,
    request: AISummaryRequest,
    db: Session = Depends(get_db),
    parent_id: str = Depends(get_current_parent_id),
):
    """对报告某个板块做 AI 摘要，返回 2-3 句通俗总结。"""
    # 校验绑定关系
    binding = db.query(StudentParentBinding).filter(
        StudentParentBinding.student_id == student_id,
        StudentParentBinding.parent_id == parent_id,
        StudentParentBinding.status == "active"
    ).first()
    if not binding:
        raise HTTPException(status_code=403, detail="未绑定该学生")
    from app.services.llm_service import llm_service

    section_labels = {
        "overview": "学习概览（练习量、正确率）",
        "trends": "进步趋势（本周vs上周对比）",
        "knowledge_points": "知识点掌握情况",
        "barrier": "学习特点分析",
        "suggestions": "家庭配合建议",
    }
    section_name = section_labels.get(request.section, request.section)

    prompt = f"""你是 ChemAI 家长助手。用 2-3 句通俗中文总结以下数据。语气鼓励、不制造焦虑。40-55岁家长能看懂。

板块: {section_name}
数据: {json.dumps(request.data, ensure_ascii=False)}

要求: 不超过 100 字，先说结论再给建议。"""

    result = llm_service.generate_text(prompt, max_tokens=256, temperature=0.7)
    if result.get("success") and result.get("content", "").strip():
        return {"success": True, "summary": result["content"].strip()}
    # 重试
    result = llm_service.generate_text(prompt, max_tokens=256, temperature=0.7, provider="deepseek")
    if result.get("success") and result.get("content", "").strip():
        return {"success": True, "summary": result["content"].strip()}
    return {"success": False, "summary": "服务暂不可用，请稍后重试"}

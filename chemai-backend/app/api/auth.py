"""
认证相关API
POST /api/auth/login - 登录
POST /api/auth/logout - 登出
POST /api/auth/refresh - 刷新Token
POST /api/auth/apply - 教师入驻申请
GET /api/auth/me - 获取当前用户
"""
from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import hashlib
import secrets
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.database import get_db, Teacher, Student, Account, TeacherApplication, Parent, StudentParentBinding
from app.middleware.auth import (
    create_access_token, create_refresh_token, menus_for, permissions_for,
    role_label, verify_token, verify_refresh_token,
)
# 别名：本模块的 /me 端点函数也叫 get_current_user，直接同名导入会读错
from app.middleware.auth import get_current_user as require_login

router = APIRouter()


def _find_account(db: Session, user_id: str) -> Optional[Account]:
    """按token中的 user_id（人员id：teacher_id/student_id/parent_id 或 account_id）反查账户"""
    return (
        db.query(Account)
        .filter(
            or_(
                Account.account_id == user_id,
                Account.teacher_id == user_id,
                Account.student_id == user_id,
                Account.parent_id == user_id,
            )
        )
        .first()
    )


def hash_password(password: str) -> str:
    """哈希密码（SHA256）"""
    return hashlib.sha256(password.encode()).hexdigest()


class LoginRequest(BaseModel):
    username: str
    password: str


class ApplyRequest(BaseModel):
    name: str
    phone: str
    school: str
    subject: str


class RefreshRequest(BaseModel):
    refresh_token: str


class AuthResponse(BaseModel):
    success: bool
    message: str = ""
    user: Optional[dict] = None
    token: Optional[str] = None
    refresh_token: Optional[str] = None


def get_user_info(account: Account, db: Session) -> dict:
    """从账户获取用户信息。

    阶段 5：这里同时是 login / refresh / `/me` 三处的共同来源，**能力清单只在这一处算** ——
    三个端点下发的 role_label / permissions / menus 因此天然一致，不会有哪个端点忘了带。
    """
    user_info = {
        "id": account.account_id,
        "role": account.role,
        "role_label": role_label(account.role),
        "permissions": permissions_for(account.role),
        "menus": menus_for(account.role),
        "username": account.username
    }

    if account.role == "super_admin":
        # ADR-0011：超管**不挂 school_id** —— 数据范围为空是设计，不是漏配。
        # 这里刻意不去 teachers 表借 school_id（借了就等于给了常驻跨校权限，
        # 正是 ADR-0011 要避免的）。跨校排查走 /api/break-glass 的限时提权。
        user_info["name"] = role_label(account.role)
        user_info["status"] = "approved"

    elif account.role in ("teacher", "subject_lead", "academic_admin") and account.teacher_id:
        teacher = db.query(Teacher).filter(Teacher.teacher_id == account.teacher_id).first()
        if teacher:
            user_info["name"] = teacher.name
            user_info["id"] = teacher.teacher_id
            user_info["teacher_id"] = teacher.teacher_id
            user_info["status"] = teacher.status
            user_info["school_id"] = teacher.school_id

    elif account.role == "student" and account.student_id:
        student = db.query(Student).filter(Student.student_id == account.student_id).first()
        if student:
            user_info["name"] = student.name
            user_info["id"] = student.student_id
            user_info["student_id"] = student.student_id
            user_info["class_id"] = student.class_id
            user_info["status"] = student.status

    elif account.role == "admin":
        user_info["name"] = "管理员"
        user_info["status"] = "approved"
        # 尝试获取admin的teacher_id以获取school_id
        if account.teacher_id:
            admin_teacher = db.query(Teacher).filter(Teacher.teacher_id == account.teacher_id).first()
            if admin_teacher:
                user_info["school_id"] = admin_teacher.school_id

    elif account.role == "parent" and account.parent_id:
        parent = db.query(Parent).filter(Parent.parent_id == account.parent_id).first()
        if parent:
            user_info["name"] = parent.name
            user_info["id"] = parent.parent_id
            user_info["parent_id"] = parent.parent_id
            user_info["status"] = parent.status
            # 获取绑定的学生信息
            binding = db.query(StudentParentBinding).filter(
                StudentParentBinding.parent_id == parent.parent_id,
                StudentParentBinding.status == "active"
            ).first()
            if binding:
                student = db.query(Student).filter(Student.student_id == binding.student_id).first()
                if student:
                    user_info["student_id"] = student.student_id
                    user_info["student_name"] = student.name
                    user_info["class_id"] = student.class_id

    return user_info


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    用户登录
    返回JWT token
    """
    # 查找账户
    account = db.query(Account).filter(Account.username == request.username).first()
    if not account:
        return AuthResponse(success=False, message="用户名或密码错误")

    # 验证密码
    if account.password_hash != hash_password(request.password):
        return AuthResponse(success=False, message="用户名或密码错误")

    # 检查账户状态
    if account.status != "active":
        return AuthResponse(success=False, message="账户已被禁用")

    # 获取用户信息
    user_info = get_user_info(account, db)

    # 生成JWT token
    token = create_access_token(
        user_id=user_info["id"],
        role=user_info["role"],
        school_id=user_info.get("school_id")
    )
    refresh_token = create_refresh_token(user_id=user_info["id"])

    return AuthResponse(
        success=True,
        message="登录成功",
        user=user_info,
        token=token,
        refresh_token=refresh_token
    )


@router.post("/refresh")
async def refresh_token(request: RefreshRequest, db: Session = Depends(get_db)):
    """
    刷新Access Token
    """
    payload = verify_refresh_token(request.refresh_token)
    if not payload:
        return {"success": False, "message": "refresh token无效"}

    user_id = payload.get("user_id")

    # 获取账户信息
    account = _find_account(db, user_id)
    if not account:
        return {"success": False, "message": "用户不存在"}

    if account.status != "active":
        return {"success": False, "message": "账户已被禁用"}

    user_info = get_user_info(account, db)

    # 生成新的access token
    new_token = create_access_token(
        user_id=user_info["id"],
        role=user_info["role"],
        school_id=user_info.get("school_id")
    )

    return {
        "success": True,
        "access_token": new_token,
        "user": user_info
    }


@router.post("/logout")
async def logout(
    request: Request,
    authorization: str = Header(None),
    db: Session = Depends(get_db),
    _user: dict = Depends(require_login),
):
    """
    用户登出

    登出发生在**已经登录之后** —— 此前它跟着 `/api/auth/` 的整段白名单一起免鉴权，
    现在要求有效 token（阶段 4.6）。
    """
    # JWT不需要在服务端存储token，客户端删除token即可
    return {"success": True, "message": "已退出登录"}


@router.get("/me")
async def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
    _user: dict = Depends(require_login),
):
    """
    获取当前用户信息
    需要携带token（Header: Authorization: Bearer <token>）

    阶段 4.6：移出 `/api/auth/` 整段白名单 —— 无 token / token 无效现在返回
    **401**（此前返回 200 + `{"success": false}`，把「没登录」伪装成了正常响应）。
    """
    if not authorization:
        return {"success": False, "message": "未登录", "user": None}

    token = authorization.replace("Bearer ", "")
    payload = verify_token(token)
    if not payload:
        return {"success": False, "message": "token无效", "user": None}

    user_id = payload.get("user_id")

    # 查找账户
    account = _find_account(db, user_id)
    if not account:
        return {"success": False, "message": "用户不存在", "user": None}

    user_info = get_user_info(account, db)
    return {"success": True, "user": user_info}


@router.post("/apply")
async def teacher_apply(request: ApplyRequest, db: Session = Depends(get_db)):
    """
    教师入驻申请
    """
    # 检查手机号是否已申请
    existing = db.query(TeacherApplication).filter(
        TeacherApplication.phone == request.phone
    ).first()
    if existing:
        if existing.status == "pending":
            return {"success": False, "message": "该手机号已提交申请，请等待审核"}
        elif existing.status == "approved":
            return {"success": False, "message": "该手机号已审核通过，请直接登录"}

    # 创建申请
    # app_id 同时是**查状态的凭据**：`GET /apply/{app_id}` 无鉴权（申请人此时还没有账号），
    # 所以它必须不可枚举。原先是 `app_YYYYMMDDHHMMSS` —— 逐秒猜就能翻出申请人的
    # 姓名/手机/学校。加随机后缀把「按时间枚举」堵死（阶段 4.6 实施中发现）。
    app_id = f"app_{datetime.now().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(6)}"
    application = TeacherApplication(
        id=app_id,
        name=request.name,
        phone=request.phone,
        school=request.school,
        subject=request.subject,
        status="pending"
    )
    db.add(application)
    db.commit()

    return {
        "success": True,
        "message": "申请已提交，请等待管理员审核",
        "application_id": app_id
    }


@router.get("/apply/{app_id}")
async def get_application(app_id: str, db: Session = Depends(get_db)):
    """获取申请状态"""
    application = db.query(TeacherApplication).filter(
        TeacherApplication.id == app_id
    ).first()
    if not application:
        return {"success": False, "message": "申请不存在"}

    return {
        "success": True,
        "application": {
            "id": application.id,
            "name": application.name,
            "phone": application.phone,
            "school": application.school,
            "subject": application.subject,
            "status": application.status,
            "created_at": application.created_at.isoformat() if application.created_at else None
        }
    }

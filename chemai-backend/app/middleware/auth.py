"""
权限认证中间件
提供JWT认证和权限验证功能
纯Python实现，无需pyjwt依赖
"""
import json
import base64
import hmac
import hashlib
from enum import Enum
from functools import wraps
from datetime import datetime, timedelta
from typing import Optional, Callable
from fastapi import Request, HTTPException
import os

# JWT配置
SECRET_KEY = os.getenv("CHEMAI_JWT_SECRET", "chemai-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24  # 开发阶段延长至24小时
REFRESH_TOKEN_EXPIRE_DAYS = 7

# 权限配置
# ── 写动作用真正的写动作把关（2026-09-13）────────────────────
# 这几个资源原先只有 read（或只到 _CR），于是它们的**写端点只能借 read 把关** ——
# 「read 权限能触发一次全量 LLM 诊断 / 覆盖学生的诊断结果」读起来就是错的。
# 更实际的害处：后来人照着矩阵做判断会得出错误结论，或者看到"有依赖把门"就把
# 函数体里的额外检查删掉（`/api/logs` 就这么埋着一个洞，已挖出修掉）。
#
# ⚠️ 扩的时候**保持各角色原有可见性不变**（原来能过的现在仍能过）—— 只修语义。
# 这些端点大多零调用方，改的是「以后照着矩阵做判断」的正确性。
_ANALYSIS_W = ["create", "read", "update"]   # 触发诊断 / 覆盖结果 / 改配置 / 发报告
_MEMORY_W = ["create", "read"]               # 诊断完成后写入学情记忆
_WARNING_W = ["create", "read", "update"]    # 触发检测 / 处理预警
_REVIEW_W = ["create", "read", "update"]     # 建复习任务 / 提交结果 / 同步
_NOTIFICATION_W = ["create", "read", "update"]  # 发送 / 标记已读 / 订阅退订
ROLE_PERMISSIONS = {
    'admin': {
        'school': ['create', 'read', 'update', 'delete'],
        'grade': ['create', 'read', 'update', 'delete'],
        'class': ['create', 'read', 'update', 'delete'],
        'teacher': ['create', 'read', 'update', 'delete'],
        'student': ['create', 'read', 'update', 'delete'],
        'analysis': _ANALYSIS_W,
    },
    'academic_admin': {
        'school': ['read'],
        'grade': ['create', 'read', 'update'],
        'class': ['create', 'read', 'update', 'delete'],
        'teacher': ['read', 'update'],
        'student': ['create', 'read', 'update', 'delete'],
        'analysis': _ANALYSIS_W,
    },
    'subject_lead': {
        'school': ['read'],
        'grade': ['read'],
        'class': ['read'],
        'teacher': ['read'],
        'student': ['read'],
        'analysis': _ANALYSIS_W,
    },
    'teacher': {
        'school': ['read'],
        'grade': ['read'],
        'class': ['read'],
        'teacher': ['read'],
        'student': ['read'],
        'analysis': _ANALYSIS_W,
    },
    'student': {
        # ⚠️ 这里**曾经有** `'grade': ['read']` —— 原意大概是「读自己的成绩」，
        # 但 `grade` 这个资源键是「年级管理」的（`/api/grades` 返回学校年级元数据），
        # 于是学生能列全校的年级列表。2026-09-12 删掉，语义重叠消除。
        #
        # **没有新建「成绩」资源键**，因为不需要：学生读自己成绩的路径是
        # `/api/report/student/{id}`（返回 your_score / class_avg_score / rank），
        # 走 `analysis:read` + `allow_self` + ScopeGuard 收窄到本人 —— ADR-0008 的模型。
        # 新建一个没有端点消费的键只会变成死键（完整性断言会拦）。
        'self_data': ['read'],
        'assignment': ['read'],
    }
}

# 本人角色（ADR-0008）：不走上面的资源矩阵，权限规则是「身份即范围」。
# 仅用于 allow_self=True 的端点 —— 放行后由端点做数据范围收窄。
SELF_ROLES = ("student", "parent")


# ── 内容类资源 ────────────────────────────────────────────────
# 上面的矩阵只覆盖「学校治理」域。出题、建考试、上传答题卡这些**内容生产**，
# 原矩阵完全没有 —— 它在设计文档里把任课教师写成了全只读，与前端实际用法矛盾
# （教师端 question.py 4 处、exam.py 8 处都在写）。
#
# 约定（2026-09-12 与项目方确认）：
#   - 任课教师**能**出题、建考试（做题的是学生，不是老师）
#   - 学科组长同权
#   - 教务管理员能建能改**不能删** —— 沿用设计文档「不能删年级 / 不能建删教师」的同一惯例，
#     删除是破坏性操作，留给学校管理员
#   - 同日补定：真题库 `exam_bank` 也给任课教师 _CRU（教师端 ExamPage 有建题库 /
#     导入题目共 5 处调用，原先只给 _R 会把整页废掉）。**删除仍留管理员** ——
#     `ExamRecord` 没有创建者字段、`QuestionSet.teacher_id` 由客户端自报，
#     放开删除等于「教师可删全校任意考试/题库」，比字面范围大得多。
_CRUD = ["create", "read", "update", "delete"]
_CRU = ["create", "read", "update"]
_CR = ["create", "read"]
_R = ["read"]
_RU = ["read", "update"]

# `agent` 与其他资源不同：会话是**每人自己的数据**，角色只区分「能不能用这个功能」，
# 真正的作用域由归属表（`conversation_owners` + `middleware/conversation.py`）决定。
# 所以四个员工角色同权、且都给到 delete —— 删的是**自己的**会话。
_AGENT = ["create", "read", "update", "delete"]

CONTENT_PERMISSIONS = {
    'admin': {
        'question': _CRUD, 'exam': _CRUD, 'exam_bank': _CRUD,
        'ocr': _CRUD, 'practice': _CRUD, 'notification': _CRUD,
        'warning': _WARNING_W, 'knowledge': _R, 'memory': _MEMORY_W, 'review': _REVIEW_W,
        'workspace': _CRUD, 'agent': _AGENT,
    },
    'academic_admin': {
        'question': _CRU, 'exam': _CRU, 'exam_bank': _CRU,
        'ocr': _CR, 'practice': _CRU, 'notification': _NOTIFICATION_W,
        'warning': _WARNING_W, 'knowledge': _R, 'memory': _MEMORY_W, 'review': _REVIEW_W,
        'workspace': _CR, 'agent': _AGENT,
    },
    'subject_lead': {
        'question': _CRU, 'exam': _CRU, 'exam_bank': _CRU,
        'ocr': _CR, 'practice': _CRU, 'notification': _NOTIFICATION_W,
        'warning': _WARNING_W, 'knowledge': _R, 'memory': _MEMORY_W, 'review': _REVIEW_W,
        # 工作区浏览器的用途就是「让老师选/建自己的工作区」——
        # 只给 read 等于废掉这个功能（见 app/api/workspace_api.py 模块 docstring）
        'workspace': _CR, 'agent': _AGENT,
    },
    'teacher': {
        'question': _CRU, 'exam': _CRU, 'exam_bank': _CRU,
        'ocr': _CR, 'practice': _CRU, 'notification': _NOTIFICATION_W,
        'warning': _WARNING_W, 'knowledge': _R, 'memory': _MEMORY_W, 'review': _REVIEW_W,
        'workspace': _CR, 'agent': _AGENT,
    },
}

for _role, _extra in CONTENT_PERMISSIONS.items():
    ROLE_PERMISSIONS.setdefault(_role, {}).update(_extra)


# 学校管理端的集成配置（LMS / Webhook / API 密钥 / SFTP）—— **仅学校管理员**。
# 不属于「内容」，所以不放进 CONTENT_PERMISSIONS，单独加。
ROLE_PERMISSIONS['admin'].setdefault('integration', list(_CRUD))

# 操作日志 —— **仅学校管理员**。
# 原先 `/api/logs` 借用 `grade:read` 当门（注释写「复用grade权限」），但**学生恰好有
# `grade:read`**，那扇门对学生在权限层是开着的；真正拦住他们的是函数体里手写的
# `role != "admin"` —— 等于矩阵之外还有第二套授权。给它自己的资源键，矩阵重新成为
# 唯一的授权真源（阶段 7.1 的表驱动测试发现）。
ROLE_PERMISSIONS['admin'].setdefault('log', ['read', 'create'])


# ── 平台超管（2026-09-12 与项目方确认）──────────────────────────
# 「能不能调这个端点」和「能看到哪些数据」是**两层**：
#   - 能力（本矩阵）：超管**等同 admin** —— 项目方明确「超管的账号应当有管理员的全部权限」
#   - 数据范围（RequestScope）：超管**默认空集**，跨校要走 break-glass（ADR-0011）
# 所以超管能调端点、但看不到任何学校的数据，直到发起 break-glass。
# 注意：这依赖「每个端点都接了范围校验」—— 只声明能力不接范围的端点，
# 超管会直接拿到全量数据。新增端点时别忘了这一层。
ROLE_PERMISSIONS['super_admin'] = {
    resource: list(actions) for resource, actions in ROLE_PERMISSIONS['admin'].items()
}

# break-glass 提权端点本身 **只有超管能用** —— 所以加在镜像**之后**（admin 不该有它）。
# 三个动作对应：create=开提权 / read=查生效状态 / delete=提前结束。
ROLE_PERMISSIONS['super_admin']['break_glass'] = ['create', 'read', 'delete']


# ── 角色清单（阶段 0.1）───────────────────────────────────────
# 这个枚举的用处是「**7 个角色的唯一清单**」——此前角色集合散在好几处
# （ROLE_PERMISSIONS 的键、ROLE_LABELS 的键、SELF_ROLES、STAFF_ROLES…），
# 加一个角色要改四五个地方且没有任何东西会提醒你漏了哪处。
# 继承 `str` 是刻意的：现有代码到处是裸字符串比较（`role == "teacher"`），
# 枚举值要能直接当字符串用，否则迁移会引入一堆 `.value`。


class Role(str, Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    ACADEMIC_ADMIN = "academic_admin"
    SUBJECT_LEAD = "subject_lead"
    TEACHER = "teacher"
    STUDENT = "student"
    PARENT = "parent"


ALL_ROLES = tuple(r.value for r in Role)

# ── 前端能力清单（阶段 5）─────────────────────────────────────
# 角色的中文显示名
ROLE_LABELS = {
    'super_admin': '平台超级管理员',
    'admin': '学校管理员',
    'academic_admin': '教务管理员',
    'subject_lead': '学科组长',
    'teacher': '任课教师',
    'student': '学生',
    'parent': '家长',
}

# 教师端侧边栏菜单 —— 每项声明它需要的资源/动作。
# 后端只下发**菜单 key 列表**；path / 中文名 / 元素符号这些展示细节留在前端
# （`frontend/src/App.tsx` 的 MENU_REGISTRY）。权限是单一真源在这里，
# 展示是单一真源在前端。
MENUS = [
    {"key": "chat",        "resource": "agent",       "action": "read"},
    {"key": "class",       "resource": "analysis",    "action": "read"},
    {"key": "students",    "resource": "student",     "action": "read"},
    {"key": "exam",        "resource": "question",    "action": "read"},
    {"key": "diagnosis",   "resource": "analysis",    "action": "read"},
    {"key": "ocr",         "resource": "ocr",         "action": "read"},
    {"key": "integration", "resource": "integration", "action": "read"},
]


def role_label(role: str) -> str:
    """角色的中文显示名。未知角色回落到角色值本身（不返回空，免得前端显示空白）。"""
    return ROLE_LABELS.get(role or "", role or "")


def permissions_for(role: str) -> list:
    """该角色的能力清单，形如 `["exam:read", "question:create", ...]`（排序、稳定）。

    本人角色（student / parent）在矩阵里没有条目 —— 他们的访问权是逐端点的
    `allow_self` + 范围收窄，不是资源级能力，所以这里返回空列表。
    """
    perms = ROLE_PERMISSIONS.get(role or "", {})
    return sorted(f"{res}:{act}" for res, acts in perms.items() for act in acts)


def menus_for(role: str) -> list:
    """该角色能看到的教师端菜单 key（顺序同 `MENUS`）。

    学生 / 家长没有任何教师端资源 → 空列表，前端据此显示「无教师端权限」页。
    """
    return [m["key"] for m in MENUS if can(role, m["resource"], m["action"])]


def base64url_encode(data: bytes) -> str:
    """URL-safe base64编码"""
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')


def base64url_decode(data: str) -> bytes:
    """URL-safe base64解码"""
    padding = 4 - len(data) % 4
    if padding != 4:
        data += '=' * padding
    return base64.urlsafe_b64decode(data)


def create_jwt(payload: dict, secret: str, expires_in: int = None) -> str:
    """
    创建JWT token（简化实现）
    不依赖外部库
    """
    # 添加标准声明
    now = datetime.utcnow()
    payload['iat'] = int(now.timestamp())
    if expires_in:
        payload['exp'] = int((now + timedelta(hours=expires_in)).timestamp())

    # Header
    header = {"alg": "HS256", "typ": "JWT"}
    header_encoded = base64url_encode(json.dumps(header, ensure_ascii=False).encode('utf-8'))
    payload_encoded = base64url_encode(json.dumps(payload, ensure_ascii=False).encode('utf-8'))

    # Signature
    signature_input = f"{header_encoded}.{payload_encoded}"
    signature = hmac.new(
        secret.encode('utf-8'),
        signature_input.encode('utf-8'),
        hashlib.sha256
    ).digest()
    signature_encoded = base64url_encode(signature)

    return f"{header_encoded}.{payload_encoded}.{signature_encoded}"


def verify_jwt(token: str, secret: str, verify_exp: bool = True) -> Optional[dict]:
    """
    验证JWT token（简化实现）
    返回payload或None
    """
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None

        header_encoded, payload_encoded, signature_encoded = parts

        # 验证签名
        signature_input = f"{header_encoded}.{payload_encoded}"
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            signature_input.encode('utf-8'),
            hashlib.sha256
        ).digest()
        expected_signature_encoded = base64url_encode(expected_signature)

        if signature_encoded != expected_signature_encoded:
            return None

        # 解析payload
        payload = json.loads(base64url_decode(payload_encoded))

        # 验证过期时间
        if verify_exp and 'exp' in payload:
            exp = payload['exp']
            if datetime.utcnow().timestamp() > exp:
                return None  # token过期

        return payload

    except Exception:
        return None


def create_access_token(user_id: str, role: str, school_id: str = None, extra_data: dict = None) -> str:
    """创建访问令牌 (JWT)"""
    payload = {
        "user_id": user_id,
        "role": role,
        "school_id": school_id,
        "type": "access"
    }
    if extra_data:
        payload.update(extra_data)
    return create_jwt(payload, SECRET_KEY, expires_in=ACCESS_TOKEN_EXPIRE_HOURS)


def create_refresh_token(user_id: str) -> str:
    """创建刷新令牌"""
    payload = {
        "user_id": user_id,
        "type": "refresh"
    }
    return create_jwt(payload, SECRET_KEY, expires_in=REFRESH_TOKEN_EXPIRE_DAYS * 24)


def verify_token(token: str) -> Optional[dict]:
    """验证访问token"""
    payload = verify_jwt(token, SECRET_KEY, verify_exp=True)
    if payload and payload.get("type") == "access":
        return payload
    return None


def verify_refresh_token(token: str) -> Optional[dict]:
    """验证刷新token"""
    payload = verify_jwt(token, SECRET_KEY, verify_exp=True)
    if payload and payload.get("type") == "refresh":
        return payload
    return None


def can(role: str, resource: str, action: str) -> bool:
    """检查权限"""
    if not role or role not in ROLE_PERMISSIONS:
        return False
    permissions = ROLE_PERMISSIONS.get(role, {})
    resource_perms = permissions.get(resource, [])
    return action in resource_perms


def get_current_user(request: Request) -> dict:
    """
    从请求中获取当前用户信息
    用于FastAPI Depends
    """
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        raise HTTPException(status_code=401, detail="未携带token")

    token = auth_header.replace('Bearer ', '')
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="token无效或已过期")

    return {
        "user_id": payload.get('user_id'),
        "role": payload.get('role'),
        "school_id": payload.get('school_id')
    }


def require_auth(f: Callable):
    """
    登录验证装饰器
    用于FastAPI端点
    """
    @wraps(f)
    async def decorated(request: Request, *args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            raise HTTPException(status_code=401, detail="未携带token")

        token = auth_header.replace('Bearer ', '')
        payload = verify_token(token)
        if not payload:
            raise HTTPException(status_code=401, detail="token无效或已过期")

        # 注入用户信息到request
        request.user_id = payload.get('user_id')
        request.user_role = payload.get('role')
        request.school_id = payload.get('school_id')

        return await f(request, *args, **kwargs)
    return decorated


def require_permission(resource: str, action: str):
    """
    权限验证装饰器工厂
    用于FastAPI端点

    用法:
        @router.get("/students")
        @require_permission("student", "read")
        async def get_students(request: Request):
            ...
    """
    def decorator(f: Callable):
        @wraps(f)
        async def decorated(request: Request, *args, **kwargs):
            # 先验证登录
            auth_header = request.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer '):
                raise HTTPException(status_code=401, detail="未携带token")

            token = auth_header.replace('Bearer ', '')
            payload = verify_token(token)
            if not payload:
                raise HTTPException(status_code=401, detail="token无效或已过期")

            # 注入用户信息
            request.user_id = payload.get('user_id')
            request.user_role = payload.get('role')
            request.school_id = payload.get('school_id')

            # 检查权限
            role = payload.get('role')
            if not can(role, resource, action):
                raise HTTPException(status_code=403, detail=f"无{resource}:{action}权限")

            return await f(request, *args, **kwargs)
        return decorated
    return decorator


class PermissionChecker:
    """
    权限检查器，用于FastAPI Depends

    用法:
        @router.get("/students")
        async def get_students(
            request: Request,
            current_user: dict = Depends(PermissionChecker("student", "read"))
        ):
            ...

    `allow_self=True` 用于**本人角色也有入口**的端点（如「我的报告」「我的学习计划」）：
    本人角色（student / parent）不走资源矩阵 —— ADR-0008 把它们划在矩阵之外 ——
    而是放行后由端点的 `RequestScope` / `ScopeGuard` 收窄到「自己」。

    ⚠️ **契约**：用了 `allow_self=True` 的端点必须做数据范围校验，
    否则任何学生/家长都能读到别人的数据。守卫测试只能看到"声明存在"，
    看不到这个契约是否被遵守。
    """

    def __init__(self, resource: str, action: str, allow_self: bool = False):
        self.resource = resource
        self.action = action
        self.allow_self = allow_self

    def __call__(self, request: Request) -> dict:
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            raise HTTPException(status_code=401, detail="未携带token")

        token = auth_header.replace('Bearer ', '')
        payload = verify_token(token)
        if not payload:
            raise HTTPException(status_code=401, detail="token无效或已过期")

        role = payload.get('role')
        if not (self.allow_self and role in SELF_ROLES):
            if not can(role, self.resource, self.action):
                raise HTTPException(status_code=403, detail=f"无{self.resource}:{self.action}权限")

        return {
            "user_id": payload.get('user_id'),
            "role": role,
            "school_id": payload.get('school_id')
        }


def get_teacher_classes(db, teacher_id: str, role: str) -> list:
    """
    获取教师任教的班级列表
    根据角色不同返回不同范围的班级
    """
    from app.models.database import Class, TeacherClassSubject, Teacher

    if role == 'admin':
        # 管理员看所有班级
        return db.query(Class).all()

    if role in ['academic_admin', 'subject_lead']:
        # 查找教师所在的学校
        teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id).first()
        if not teacher or not teacher.school_id:
            return []
        # 返回同学校的所有班级
        return db.query(Class).filter(Class.grade_id.in_(
            db.query(TeacherClassSubject.class_id).filter(
                TeacherClassSubject.teacher_id == teacher_id
            ).subquery()
        )).all()

    # 普通教师只看自己任教的班级
    tcs_records = db.query(TeacherClassSubject).filter(
        TeacherClassSubject.teacher_id == teacher_id
    ).all()
    class_ids = [r.class_id for r in tcs_records]
    if not class_ids:
        return []
    return db.query(Class).filter(Class.class_id.in_(class_ids)).all()


def get_class_students(db, class_id: str, teacher_id: str = None, role: str = None) -> list:
    """
    获取班级的学生列表
    会根据教师权限自动过滤
    """
    from app.models.database import Student

    # 管理员和教务管理员可以看任何班级
    if role in ['admin', 'academic_admin']:
        return db.query(Student).filter(Student.class_id == class_id).all()

    # 其他教师只能看自己任教的班级
    if teacher_id:
        from app.models.database import TeacherClassSubject
        tcs = db.query(TeacherClassSubject).filter(
            TeacherClassSubject.teacher_id == teacher_id,
            TeacherClassSubject.class_id == class_id
        ).first()
        if not tcs:
            return []  # 无权访问该班级

    return db.query(Student).filter(Student.class_id == class_id).all()

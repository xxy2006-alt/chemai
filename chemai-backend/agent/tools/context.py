"""agent/tools/context.py — 每请求身份上下文（contextvars，任务级隔离）。

**身份由 channel 从已签名的 token 解出后注入**（三个 agent 端点都注入，见 ADR-0014）。
工具不向用户索要身份，也不接受模型自报的身份 —— 服务端身份是唯一来源。

实测（2026-09-14 探针）：contextvars 能从端点函数一路传到 Starlette 的流式生成器、
`gather` 出的并行分支、以及命名子 task，所以 SSE 路径不需要显式传参。

**这份上下文此前只带 user_id**，`role` / `school_id` 被丢掉了 —— 而 `RequestScope`
算数据范围正需要它们。ADR-0014 把三个字段一起带上，接缝（`agent/guard.py`）据此
校验工具收到的 student_id / class_id / teacher_id 是否落在调用者的 Data Scope 内。

⚠️ 别删「无身份」这个状态：它要能被表达出来（返回 `{}`），接缝据此 fail-closed。
"""
import contextvars
from typing import Optional

_current_identity: contextvars.ContextVar[Optional[dict]] = contextvars.ContextVar(
    "chemai_current_identity", default=None
)


def set_current_identity(user_id: str, role: str = "", school_id: Optional[str] = None) -> None:
    """请求开始时由 channel 调用。user_id 为空表示清除（无身份的请求）。"""
    uid = (user_id or "").strip()
    if not uid:
        _current_identity.set(None)
        return
    _current_identity.set({
        "user_id": uid,
        "role": (role or "").strip(),
        "school_id": (school_id or "").strip() or None,
    })


def current_identity() -> dict:
    """当前请求的身份；无身份时返回空 dict（**不是 None** —— 调用方只需判空）。"""
    return _current_identity.get() or {}


def current_teacher() -> str:
    """当前身份的 user_id；无身份时空串。"""
    return current_identity().get("user_id", "")


def set_current_teacher(teacher_id: str) -> None:
    """**兼容入口**：只注入 user_id 的旧写法（main 侧的工具与测试仍在用）。

    新代码用 `set_current_identity()` —— ADR-0014 要 role / school_id 才算得出
    数据范围。只带 user_id 时，接缝（`agent/tools/data_scope.py`）会拿它去
    `resolve_identity()` 反查账户补齐 role，行为与 main 的 `_caller_scope` 一致。
    空串 = 清除身份（无身份 → 接缝 fail-closed）。
    """
    tid = (teacher_id or "").strip()
    if not tid:
        _current_identity.set(None)
        return
    _current_identity.set({**current_identity(), "user_id": tid})


_current_student: contextvars.ContextVar[str] = contextvars.ContextVar(
    "chemai_current_student", default=""
)


def set_current_student(student_id: str) -> None:
    """学生端会话由 channel 注入；空串表示非学生上下文。"""
    _current_student.set((student_id or "").strip())


def current_student() -> str:
    """当前请求上下文中的学生ID（无则空串）。服务端身份优先于模型输入。"""
    return _current_student.get()

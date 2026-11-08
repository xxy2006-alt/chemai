"""Agent 工具层的数据范围校验 —— ADR-0014。

与 HTTP 侧的 `app/middleware/scope.py` 是**同一套规则的另一个应用点**：
范围的**计算**只有 `RequestScope` 一个家，这里只负责
「把工具收到的参数解析成 ID → 问 RequestScope 在不在范围内」。

为什么 agent 侧还需要一次（HTTP 侧 router 不是已经校验过了吗）：
agent 工具**进程内直调 service、不走 HTTP**，那 232 个端点的权限与范围对它们完全无效。

规则来自 `TOOL_META` 的 `scope` 声明（参数名 → 维度）：
    weekly_report: {..., "scope": {"student_id": "student", "student_name": "student",
                                   "class_name": "class"}}

三种维度，三种判法：
  - `student`  学号 or 姓名 → `RequestScope.allows_student`
  - `class`    班级 id or 名称 → `RequestScope.allows_class`
  - `teacher`  教师 id → 本人、或校级管理员（与 HTTP 侧 `ScopeGuard(kind="teacher")` 同规则）

**姓名一律「在范围内搜」**，不是「先全库搜再校验」——后者会泄漏「这个学生存在但你看不到」。
搜不到就当作不存在（沿用 `ScopeGuard` 的「不泄漏存在性」惯例）。
"""
from typing import Optional

from sqlalchemy import text

from agent.tools.context import current_identity
from app.middleware.scope import RequestScope, _SCHOOL_WIDE, resolve_identity

# 身份类参数的维度 → 用户可读的名词（报错文案用）
_KIND_NOUN = {"student": "学生", "class": "班级", "teacher": "教师"}


def _session():
    from app.models.database import get_db
    return next(get_db())


def _tool_scope(tool) -> dict:
    """该工具声明的范围规则；没声明则空 dict（= 不校验）。"""
    from agent.tools import TOOL_META
    return (TOOL_META.get(tool) or {}).get("scope") or {}


def _match_students(session, name: str) -> list:
    rows = session.execute(
        text("SELECT student_id, name FROM students WHERE name LIKE :n"), {"n": f"%{name}%"}
    ).fetchall()
    return [(r[0], r[1]) for r in rows]


def _match_classes(session, name: str) -> list:
    rows = session.execute(
        text("SELECT class_id, name FROM classes WHERE name LIKE :n"), {"n": f"%{name}%"}
    ).fetchall()
    return [(r[0], r[1]) for r in rows]


def _resolve(kind: str, value: str, scope: RequestScope):
    """把「ID 或姓名」解析成 ID —— 姓名**只在调用者范围内搜**。

    返回 `(status, payload)`：
      `("ok", id)` · `("none", None)` 查不到 · `("many", [(id, name), ...])` 多个匹配

    ⚠️ 范围过滤必须在**这里**做，不能等后面再判：先全库搜再筛，那些范围外的
    行已经进了 `many` 的候选列表，等于把全校学生的姓名 + 学号报给调用者
    （2026-09-14 实测踩到：家长搜「周」拿到全校 7 个学生）。搜不到一律当不存在，
    与 `ScopeGuard` 的「不泄漏存在性」同惯例。
    """
    v = str(value or "").strip()
    if not v:
        return "none", None
    if v.isdigit() or v.startswith("class_") or v.startswith("teacher_"):
        return "ok", v                      # 形态上就是 ID，交给范围判定去筛
    session = scope.db                              # 复用范围那一次会话，别开第二个
    rows = _match_students(session, v) if kind == "student" else _match_classes(session, v)
    allowed = scope.student_ids() if kind == "student" else scope.class_ids()
    rows = [r for r in rows if r[0] in allowed]
    if not rows:
        return "none", None
    if len(rows) > 1:
        return "many", rows
    return "ok", rows[0][0]


def check_tool_scope(tool, kwargs: dict) -> Optional[dict]:
    """校验并**就地改写** kwargs 里的身份参数。

    返回 `None` 表示放行；返回 dict 表示拒绝，调用方直接把它当工具结果返回。
    **fail-closed**：没有身份（评测之外不会有这情况）时，声明了范围的工具一律拒绝。
    """
    scope_spec = _tool_scope(tool)
    if not scope_spec:
        return None

    identity = current_identity()
    if not identity:
        return {
            "error": "缺少调用者身份，无法校验数据范围（ADR-0014 fail-closed）",
            "scope_denied": True,
        }

    session = _session()
    try:
        # 身份只带 user_id 时（`set_current_teacher` 的旧写法），按 user_id 反查账户
        # 补齐 role / school_id —— 与 main 侧 `_caller_scope` 的做法一致，两套注入
        # 方式共用同一条范围计算。查不到 = 空角色 = 空范围 = 拒绝，仍是 fail-closed。
        if not identity.get("role"):
            identity = resolve_identity(session, identity.get("user_id", ""))
        scope = RequestScope.from_user(identity, session)

        for param, kind in scope_spec.items():
            raw = str(kwargs.get(param) or "").strip()

            if kind == "teacher":
                # teacher_id 缺失时回填服务端身份（原先的行为），有一律以服务端身份为准
                if not raw or raw != identity["user_id"]:
                    if identity.get("role") in _SCHOOL_WIDE:
                        if not raw:
                            kwargs[param] = identity["user_id"]
                        continue                      # 校级管理员可看全校教师
                    if raw and raw != identity["user_id"]:
                        return {"error": "无权访问其他教师的数据", "scope_denied": True}
                    kwargs[param] = identity["user_id"]
                continue

            if not raw:
                continue                              # 参数没给，不校验（工具自己兜底）

            status, payload = _resolve(kind, raw, scope)

            if status == "none":
                return {
                    "error": f"未找到名为 '{raw}' 的{_KIND_NOUN[kind]}",
                    "hint": "请确认名称是否正确，或提供 ID 查询",
                    "_route": {"navigate": False},
                }
            if status == "many":
                # 沿用工具原有的多匹配交互；候选**只列范围内的**
                return {
                    "multiple_matches": [{"student_id": i, "name": n} for i, n in payload]
                    if kind == "student" else
                    [{"class_id": i, "name": n} for i, n in payload],
                    "hint": f"找到多个匹配{_KIND_NOUN[kind]}，请提供完整 ID",
                    "_route": {"navigate": False},
                }

            allowed = scope.allows_student(payload) if kind == "student" else scope.allows_class(payload)
            if not allowed:
                # 与 ScopeGuard 同惯例：不泄漏存在性 —— 表现为「查不到」
                return {
                    "error": f"未找到名为 '{raw}' 的{_KIND_NOUN[kind]}",
                    "hint": "请确认名称是否正确，或提供 ID 查询",
                    "_route": {"navigate": False},
                }

            kwargs[param] = payload                   # 回填解析出的 ID，工具无需改
    finally:
        session.close()

    return None

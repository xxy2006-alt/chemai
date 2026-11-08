"""评测身份 —— persona 映射到**真实账号**（ADR-0014）。

评测此前跑在**无身份**下，而那是线上不存在的状态：agent 接缝（`agent/guard.py`）
对收身份参数的工具是 fail-closed 的，没有身份就一律拒绝。所以每个 persona 必须
有个真实身份，否则评测测的不是产品的行为。

**不写死账号**：演示数据 2026-09-14 被整体换过一轮，写死的 `teacher_hai` /
`202610201` / `lgh` 全部消失（连带一批引用旧学生名、旧班名的场景失效）。这里改成
**按角色从库里挑**，身份字段一律经 `app/api/auth.py:get_user_info()` 产出 ——
与登录下发 token 用的是同一个函数，不另起一份会漂的口径（`user_id` 到底是
account_id 还是 teacher_id，只由那一处决定）。

场景可用 `identity: {username: "..."}` 显式覆盖 —— 越权类 eval 要能声明
「我是谁、要越谁的权」。
"""
from typing import Optional

from sqlalchemy.orm import aliased

from app.api.auth import get_user_info
from app.models.database import Account, StudentParentBinding, get_db

# persona → 候选角色（按优先级）。teacher 优先学科组长，与 ADR-0014 原文一致
# （原先映射的 teacher_hai 就是学科组长，数据重建后由 zhou 接替）。
_PERSONA_ROLES = {
    "teacher": ("subject_lead", "teacher"),
    "tutor": ("student",),
    "student": ("student",),
    "parent": ("parent",),
}

PERSONAS = tuple(_PERSONA_ROLES)


def resolve(persona: str, override: Optional[dict] = None) -> dict:
    """解析该 persona 的身份 → `{user_id, role, school_id, name}`。

    解析不到**直接报错**，不退回「无身份」—— 静默无身份会让整个评测跑在一个
    假上下文里，而症状（工具全被 fail-closed 拒）离原因很远。
    """
    session = next(get_db())
    try:
        account = _pick(session, persona, override)
        info = get_user_info(account, session)
        return {
            "user_id": info.get("id") or "",
            "role": info.get("role") or "",
            "school_id": info.get("school_id"),
            "name": info.get("name") or account.username,
        }
    finally:
        session.close()


def _pick(session, persona: str, override: Optional[dict]):
    if override:
        username = (override or {}).get("username") or ""
        account = (
            session.query(Account)
            .filter(Account.username == username, Account.status == "active")
            .first()
        )
        if not account:
            raise RuntimeError(f"场景声明的 identity 账号不存在或已停用：{username!r}")
        return account

    roles = _PERSONA_ROLES.get(persona)
    if not roles:
        raise RuntimeError(f"未知 persona：{persona!r}（已知：{', '.join(PERSONAS)}）")

    for role in roles:
        account = _first_active(session, role)
        if account:
            return account
    raise RuntimeError(
        f"评测身份解析失败：库里没有 {persona} persona 需要的账号（角色 {' / '.join(roles)}）。"
        "演示数据被换过？先跑一遍造数，或在该场景上写 identity: {username: ...} 指定账号。"
    )


def _first_active(session, role: str):
    """该角色的账号，按 username 定序取第一个（不依赖建表顺序）。

    学生优先取**家长能登录**的那个（绑定关系有对应账号）—— 这样评测里 tutor（学生）
    与 parent 两个 persona 是同一家人，家长场景问自己孩子的报告才是「范围内」的那一半。
    """
    query = (
        session.query(Account)
        .filter(Account.role == role, Account.status == "active")
        .order_by(Account.username)
    )
    if role == "student":
        parent_account = aliased(Account)
        bound = (
            query.join(
                StudentParentBinding,
                StudentParentBinding.student_id == Account.student_id,
            )
            .join(
                parent_account,
                parent_account.parent_id == StudentParentBinding.parent_id,
            )
            .filter(StudentParentBinding.status == "active",
                    parent_account.status == "active")
            .first()
        )
        if bound:
            return bound
    return query.first()

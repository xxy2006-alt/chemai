"""会话归属判定 —— 阶段 4.6 批次 E。

`thread_id` 由客户端自报、格式是 `{prefix}{毫秒时间戳}`（**可枚举**），改造前没有
任何归属记录：任何登录用户都能列出、读取、删除任意会话。本模块是唯一的归属判定点。

**新会话**查 `conversation_owners` 表。**老会话**（本表上线前的）无法回溯归属，
按 thread_id 前缀兜底 —— 2026-09-12 与项目方确认的策略：

  - 员工角色认领 `t-` / `c` 开头的无主会话（教师端 + 兼容老前端的裸时间戳 id）
  - 本人角色（student / parent）对无主会话**一律拒绝**

这个取舍有实测依据：`chemai_checkpoints.db` 里 1316 个线程有 1208 个是 `eval` 前缀
（评测框架的，不是用户对话），真正的用户会话只有 `t-`(9) / `m-`(16) / `p-`(11)。
所以「本人角色读不到老会话」影响面很小，而教师那 9 条是主要演示面，必须保住。
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.conversation_owner import ConversationOwner
from app.middleware.scope import _SCHOOL_WIDE  # noqa: F401  (保持与数据范围同一套角色口径)

# 能使用 agent 会话的员工角色（与 ROLE_PERMISSIONS 的 agent 资源对齐）
STAFF_ROLES = ("super_admin", "admin", "academic_admin", "subject_lead", "teacher")

# 无主老会话里，员工角色可以认领的前缀
STAFF_LEGACY_PREFIXES = ("t-", "c")


def is_staff(user: dict) -> bool:
    return (user or {}).get("role") in STAFF_ROLES


def owns_conversation(db: Session, thread_id: str, user: dict) -> bool:
    """调用者是否有权读写这个会话。

    有归属记录 → 只认登记的那个人（员工也不例外：教师之间也不该互看会话）。
    无归属记录 → 老会话兜底，仅员工角色认领 `t-` / `c` 开头。
    """
    if not thread_id or not user or not user.get("user_id"):
        return False

    row = (
        db.query(ConversationOwner)
        .filter(ConversationOwner.thread_id == thread_id)
        .first()
    )
    if row:
        return row.user_id == user["user_id"]

    return is_staff(user) and thread_id.startswith(STAFF_LEGACY_PREFIXES)


def claim_conversation(db: Session, thread_id: str, user: dict) -> None:
    """登记会话归属（幂等）。已有归属则不覆盖 —— 否则后到的人能把别人的会话抢过来。"""
    if not thread_id or not user or not user.get("user_id"):
        return
    existing = (
        db.query(ConversationOwner)
        .filter(ConversationOwner.thread_id == thread_id)
        .first()
    )
    if existing:
        return
    db.add(ConversationOwner(
        thread_id=thread_id,
        user_id=user["user_id"],
        role=user.get("role") or "",
    ))
    db.commit()


def filter_owned(db: Session, thread_ids, user: dict) -> list:
    """按归属过滤一批 thread_id —— 给「列出我的会话」用。

    只看调用者**自己登记过**的会话，不走老会话兜底：列表是「我的」，
    不该把全校同角色的老对话都列出来。
    """
    if not thread_ids or not user or not user.get("user_id"):
        return []
    owned = {
        r[0] for r in
        db.query(ConversationOwner.thread_id)
        .filter(ConversationOwner.user_id == user["user_id"],
                ConversationOwner.thread_id.in_(list(thread_ids)))
        .all()
    }
    return [t for t in thread_ids if t in owned]


def require_owned(db: Session, thread_id: Optional[str], user: dict,
                  what: str = "会话") -> None:
    """不在归属范围内 → 403。

    判定顺序：
      1. 已有归属记录 → 只认登记的人
      2. 员工角色认领 `t-` / `c` 开头的**老**会话（见模块 docstring 的兜底策略）
      3. **库里的全新会话**（还没有 checkpoint）→ 当场认领给调用者

    第 3 条是为「自己本地造 thread_id 的客户端」留的：`frontend/m/parent.html`
    用 `'p-' + Date.now()` 在浏览器里生成 id，从不调 `/chat/new` —— 没有这一条，
    家长端第一次发消息就会 403。

    它**不放宽**老会话：判据是「库里有没有这个会话」，别人的老会话在库里躺着，
    照样走到 403。也不能靠抢注读别人的对话 —— 抢注只能占一个还不存在的 id，
    占不到任何已有内容。（理论代价：能猜到别人未来某毫秒 id 的人可以抢先占掉它，
    让对方 403 一次；需要猜中毫秒时间戳，且只造成困扰、不泄漏内容。）
    """
    from fastapi import HTTPException

    if not thread_id:
        raise HTTPException(status_code=403, detail=f"缺少{what} id")
    if owns_conversation(db, thread_id, user):
        return

    if not thread_exists(thread_id):
        # 登记后**必须复验**：claim_conversation 对「已有归属」是 no-op（防抢注），
        # 不复验就会把「已属他人、但 checkpoint 库里还没有内容」的会话放行给任何人。
        claim_conversation(db, thread_id, user)
        if owns_conversation(db, thread_id, user):
            return

    raise HTTPException(status_code=403, detail=f"无权访问该{what}")


def checkpoints_db_path() -> str:
    """checkpoint 库路径 —— 与 agent/channel/conversation.py 里用的是同一个。"""
    import os
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "chemai_checkpoints.db")


def thread_exists(thread_id: str) -> bool:
    """该 thread 在 checkpoint 库里有没有数据。

    这是「新会话」与「别人的老会话」的唯一判别点 —— 只有前者才允许首次认领。
    """
    import os
    import sqlite3

    db_path = checkpoints_db_path()
    if not os.path.exists(db_path):
        return False
    try:
        conn = sqlite3.connect(db_path)
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM checkpoints WHERE thread_id = ? LIMIT 1", (thread_id,))
            return cur.fetchone() is not None
        finally:
            conn.close()
    except sqlite3.Error:
        # 库读不了时按「已存在」处理 —— fail-closed，宁可让调用者报错
        return True

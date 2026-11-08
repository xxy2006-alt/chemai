"""会话归属 —— 阶段 4.6 批次 E。

改造前的状况：`thread_id` 是 `{prefix}{毫秒时间戳}`（**可枚举**），且不记录归属 ——
任何登录用户都能列出、读取、删除任意会话（`delete_conversation` 直接对 checkpoint
库 `DELETE`）。本文件钉住修好之后的行为。

⚠️ 这里**不碰真实的 `chemai_checkpoints.db`**（57MB，且 delete 会真删数据）。
所以断言集中在两类：
  1. 归属判定本身的单元测试（`middleware/conversation.py`，只用测试库）
  2. 「守卫在碰 checkpoint 库之前就拦下」的端点断言 —— 别人的 thread 一律 403，
     根本走不到读写 checkpoint 那一步
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from agent.channel import conversation as conversation_mod
from app.middleware import conversation as guard
from app.middleware.auth import create_access_token
from app.middleware.conversation import (
    claim_conversation, filter_owned, owns_conversation, require_owned,
)
from app.models.conversation_owner import ConversationOwner
from app.models.database import Base, get_db


@pytest.fixture(autouse=True)
def _no_real_checkpoint_db(monkeypatch):
    """默认把 `thread_exists` 钉死为 True（=「会话已存在」），且**永不打开真实的
    chemai_checkpoints.db**（57MB，且 delete 会真删数据）。

    这也让「老会话一律 403」这条断言是确定性的。要测「全新会话首次认领」的用例
    自己再 patch 成 False。
    """
    monkeypatch.setattr(guard, "thread_exists", lambda thread_id: True)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, expire_on_commit=False)()
    yield s
    s.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def client(db_session):
    app = FastAPI()
    app.include_router(conversation_mod.router, prefix="/api/agent")

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c


TEACHER = {"user_id": "T_chem", "role": "teacher", "school_id": "sch1"}
OTHER_TEACHER = {"user_id": "T_math", "role": "teacher", "school_id": "sch1"}
STUDENT = {"user_id": "S1", "role": "student"}
OTHER_STUDENT = {"user_id": "S2", "role": "student"}
PARENT = {"user_id": "P1", "role": "parent"}
OTHER_PARENT = {"user_id": "P2", "role": "parent"}


def hdr(user):
    return {"Authorization": f"Bearer {create_access_token(user['user_id'], user['role'])}"}


# ─────────────────────────────────────────────────────────────
# 归属判定
# ─────────────────────────────────────────────────────────────

def test_unowned_thread_is_denied_to_everyone(db_session):
    """没有归属记录、且不是员工可认领的前缀 → 谁都进不来（fail-closed）。"""
    assert owns_conversation(db_session, "m-1700000000000", STUDENT) is False
    assert owns_conversation(db_session, "m-1700000000000", TEACHER) is False


def test_claim_then_owner_can_access(db_session):
    claim_conversation(db_session, "t-1", TEACHER)
    assert owns_conversation(db_session, "t-1", TEACHER) is True


def test_claimed_thread_is_denied_to_others_even_same_role(db_session):
    """登记过的会话只认登记的那个人 —— 教师之间也不该互看。"""
    claim_conversation(db_session, "t-1", TEACHER)
    assert owns_conversation(db_session, "t-1", OTHER_TEACHER) is False


def test_claim_is_idempotent_and_does_not_steal(db_session):
    """幂等，且**不覆盖已有归属** —— 否则后到的人能把别人的会话抢过去。"""
    claim_conversation(db_session, "t-1", TEACHER)
    claim_conversation(db_session, "t-1", OTHER_TEACHER)   # 抢注尝试
    row = db_session.query(ConversationOwner).filter_by(thread_id="t-1").one()
    assert row.user_id == "T_chem"


def test_student_cannot_claim_anyone_elses_legacy_thread(db_session):
    """老会话兜底策略：本人角色对无主会话一律拒绝。

    这条是刻意的取舍（2026-09-12 与项目方确认）—— thread_id 可枚举，
    若允许「无主就认领」，学生猜到 id 就能把别人 16 条老会话认领走。
    """
    assert owns_conversation(db_session, "m-1700000000000", OTHER_STUDENT) is False
    assert owns_conversation(db_session, "p-1700000000000", PARENT) is False


def test_staff_can_still_reach_legacy_teacher_threads(db_session):
    """员工角色认领 `t-` / `c` 开头的无主老会话 —— 保住教师端已有的 9 条对话。"""
    assert owns_conversation(db_session, "t-1700000000000", TEACHER) is True
    assert owns_conversation(db_session, "c1783322579777", TEACHER) is True


def test_student_cannot_reach_legacy_teacher_threads(db_session):
    """老会话兜底不能变成学生读教师对话的旁路。"""
    assert owns_conversation(db_session, "t-1700000000000", STUDENT) is False


def test_require_owned_raises_403_for_existing_others_thread(db_session):
    """库里有这个会话 + 不归我 → 403（不放行首次认领）。"""
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as e:
        require_owned(db_session, "m-1", STUDENT)
    assert e.value.status_code == 403


def test_require_owned_rejects_empty_thread_id(db_session):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as e:
        require_owned(db_session, "", TEACHER)
    assert e.value.status_code == 403


def test_require_owned_claims_thread_that_does_not_exist_yet(db_session, monkeypatch):
    """**全新**会话（库里还没有）→ 首次使用即认领。

    这条是给 `frontend/m/parent.html` 那种「自己本地造 thread_id、从不调
    /chat/new」的客户端留的路 —— 没有它，家长端第一次发消息就 403。
    """
    monkeypatch.setattr(guard, "thread_exists", lambda thread_id: False)
    require_owned(db_session, "p-1700000000000", PARENT)
    row = db_session.query(ConversationOwner).filter_by(thread_id="p-1700000000000").one()
    assert row.user_id == "P1"


def test_claim_on_new_thread_does_not_apply_to_existing_ones(db_session, monkeypatch):
    """反例：同一个 id，只要库里已经有了，就不再放行首次认领。"""
    from fastapi import HTTPException
    monkeypatch.setattr(guard, "thread_exists", lambda thread_id: True)
    with pytest.raises(HTTPException):
        require_owned(db_session, "p-1700000000000", PARENT)
    assert db_session.query(ConversationOwner).count() == 0


def test_owned_but_nonexistent_thread_is_not_claimable_by_others(db_session, monkeypatch):
    """⚠️ 回归：**已有归属、但 checkpoint 库里还没有内容**的会话，不能被别人认领。

    这个洞是 2026-09-12 用 lgh 账号做验收时抓到的：`require_owned` 走到
    「库里没有 → 登记」这一支后**无条件放行**，而 `claim_conversation` 对已有归属
    是 no-op（防抢注），于是任何调用者都被放行了。
    实际场景：家长端本地造一个 id、发第一条消息（归属已登记但 checkpoint 还没落盘），
    另一个家长猜到该 id 就能读。
    """
    from fastapi import HTTPException

    # 归属已登记，但库里没有内容
    claim_conversation(db_session, "p-1700000000000", PARENT)
    monkeypatch.setattr(guard, "thread_exists", lambda thread_id: False)

    with pytest.raises(HTTPException) as e:
        require_owned(db_session, "p-1700000000000", OTHER_PARENT)
    assert e.value.status_code == 403

    # 归属没被抢走
    row = db_session.query(ConversationOwner).filter_by(thread_id="p-1700000000000").one()
    assert row.user_id == "P1"


def test_filter_owned_only_returns_own_and_ignores_staff_fallback(db_session):
    """列表是「我的」—— 不走老会话前缀兜底，否则会把同角色的老对话全列出来。"""
    claim_conversation(db_session, "t-1", TEACHER)
    claim_conversation(db_session, "t-2", OTHER_TEACHER)
    got = filter_owned(db_session, ["t-1", "t-2", "t-1700000000000"], TEACHER)
    assert got == ["t-1"]


# ─────────────────────────────────────────────────────────────
# 端点：守卫在碰 checkpoint 库之前就拦下
# ─────────────────────────────────────────────────────────────

def test_new_conversation_registers_ownership(client, db_session):
    """`/chat/new` 是归属的唯一登记点。"""
    r = client.post("/api/agent/chat/new?prefix=t-", headers=hdr(TEACHER))
    assert r.status_code == 200
    tid = r.json()["thread_id"]
    assert tid.startswith("t-")
    row = db_session.query(ConversationOwner).filter_by(thread_id=tid).one()
    assert row.user_id == "T_chem"


def test_history_of_others_thread_is_403(client, db_session):
    """别人的会话直接 403 —— 不会走到读 checkpoint。"""
    claim_conversation(db_session, "t-99", OTHER_TEACHER)
    r = client.get("/api/agent/chat/history/t-99", headers=hdr(TEACHER))
    assert r.status_code == 403


def test_delete_of_others_thread_is_403(client, db_session):
    """删除别人的会话 403 —— 改造前任何登录用户都能删。"""
    claim_conversation(db_session, "t-99", OTHER_TEACHER)
    r = client.delete("/api/agent/chat/conversations/t-99", headers=hdr(TEACHER))
    assert r.status_code == 403
    # 归属记录仍在（没被权限层误删）
    assert db_session.query(ConversationOwner).filter_by(thread_id="t-99").count() == 1


def test_student_cannot_delete_legacy_teacher_thread(client, db_session):
    r = client.delete("/api/agent/chat/conversations/t-1700000000000", headers=hdr(STUDENT))
    assert r.status_code == 403


def test_agent_endpoints_reject_anonymous(client):
    assert client.get("/api/agent/chat/history/t-1").status_code == 401
    assert client.post("/api/agent/chat/new").status_code == 401
    assert client.delete("/api/agent/chat/conversations/t-1").status_code == 401

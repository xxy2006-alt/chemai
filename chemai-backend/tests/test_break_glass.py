"""break-glass 提权 —— ADR-0011。

超管的跨校访问**不是常驻权限**：默认数据范围为空，需要排查时开一次限时提权，
用完即掉、全程留审计。本文件钉住三件事（也是 tasks.md 7.4 的三个验证项）：
  1. 超管默认看不到任何学校数据
  2. 提权生效期间可见，且**有审计记录**
  3. 到点自动失效

判定是**读时**做的（看 `expires_at`），所以「自动失效」在这里用「把过期时间
改到过去」来模拟 —— 不需要等真的到点，也不需要定时任务。
"""
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import break_glass as bg_api
from app.middleware.auth import create_access_token
from app.middleware.break_glass import MAX_MINUTES, active_session, start_session
from app.middleware.scope import RequestScope
from app.models.break_glass import BreakGlassSession
from app.models.database import (
    Base, Class, Grade, OperationLog, School, get_db,
)


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
def seeded(db_session):
    """两所学校各一个班 —— 用来验证「默认空集 / 提权后跨校可见」。"""
    db_session.add_all([
        School(school_id="sch1", name="一中"),
        School(school_id="sch2", name="二中"),
        Grade(grade_id="g1", school_id="sch1", name="高一", year=2025),
        Grade(grade_id="g2", school_id="sch2", name="高一", year=2025),
        Class(class_id="c1", name="一班", grade="高一", grade_id="g1", subject="化学"),
        Class(class_id="c2", name="二班", grade="高一", grade_id="g2", subject="化学"),
    ])
    db_session.commit()
    return db_session


@pytest.fixture
def client(db_session):
    app = FastAPI()
    app.include_router(bg_api.router, prefix="/api/break-glass")

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c


SUPER = ("super_admin", "acc_super")
ADMIN = ("admin", "acc_admin")


def hdr(role_ctx):
    return {"Authorization": f"Bearer {create_access_token(role_ctx[1], role_ctx[0])}"}


def scope_of(db, role_ctx):
    role, uid = role_ctx
    return RequestScope(role=role, user_id=uid, school_id=None, db=db)


# ── 验证项 1：超管默认看不到任何学校数据 ──

def test_super_admin_has_empty_scope_by_default(seeded):
    assert scope_of(seeded, SUPER).class_ids() == set(), (
        "ADR-0011：默认空范围。跨校访问要靠 break-glass，不是常驻权限"
    )
    assert scope_of(seeded, SUPER).allows_class("c1") is False


def test_super_admin_without_school_id_is_not_an_accident(seeded):
    """超管不挂 school_id 是设计，不是漏配 —— 挂上就等于常驻跨校可见。"""
    assert scope_of(seeded, ("super_admin", "acc_super")).school_id is None


# ── 提权生效期间可见 ──

def test_break_glass_opens_up_all_schools(seeded):
    start_session(seeded, "acc_super", "排查一中成绩同步问题", minutes=15)
    ids = scope_of(seeded, SUPER).class_ids()
    assert ids == {"c1", "c2"}, "提权期间应能看到**所有学校**的班（两校各一个）"


def test_other_roles_are_unaffected_by_break_glass(seeded):
    """提权只对开它的人生效，不是全局开关。"""
    start_session(seeded, "acc_super", "排查", minutes=15)
    # admin 本来按本校取数，不受影响
    assert RequestScope(role="admin", user_id="acc_admin",
                        school_id="sch1", db=seeded).class_ids() == {"c1"}
    # 另一个超管没开提权，仍是空集
    assert scope_of(seeded, ("super_admin", "acc_super_2")).class_ids() == set()


# ── 验证项 3：到点自动失效 ──

def test_expired_break_glass_loses_access(seeded):
    """把过期时间改到过去 = 到点。**读时判定**，无需定时任务。"""
    s = start_session(seeded, "acc_super", "排查", minutes=15)
    s.expires_at = datetime.utcnow() - timedelta(seconds=1)
    seeded.commit()

    assert active_session(seeded, "acc_super") is None
    assert scope_of(seeded, SUPER).class_ids() == set()


def test_ended_break_glass_loses_access(seeded):
    """提前结束（用完即掉）也应立刻失效。"""
    s = start_session(seeded, "acc_super", "排查", minutes=15)
    s.ended_at = datetime.utcnow()
    seeded.commit()

    assert active_session(seeded, "acc_super") is None
    assert scope_of(seeded, SUPER).class_ids() == set()


# ── 端点 ──

def test_only_super_admin_can_start(client, seeded):
    for role_ctx in (ADMIN, ("teacher", "t1"), ("student", "s1"), ("parent", "p1")):
        r = client.post("/api/break-glass", json={"reason": "试试"}, headers=hdr(role_ctx))
        assert r.status_code == 403, f"{role_ctx[0]} 不该能开提权"


def test_break_glass_requires_a_reason(client, seeded):
    """没理由的提权事后等于没留痕 —— 必须挡住。"""
    r = client.post("/api/break-glass", json={"reason": "   "}, headers=hdr(SUPER))
    assert r.status_code == 400
    assert "理由" in r.json()["detail"]


def test_break_glass_duration_is_capped(client, seeded):
    r = client.post("/api/break-glass", json={"reason": "排查", "minutes": MAX_MINUTES + 1},
                    headers=hdr(SUPER))
    assert r.status_code == 400


def test_start_and_revoke_via_api(client, seeded):
    r = client.post("/api/break-glass", json={"reason": "排查一中"},
                    headers=hdr(SUPER))
    assert r.status_code == 200
    session = r.json()["session"]
    assert session["reason"] == "排查一中"
    assert session["remaining_seconds"] > 0

    # 生效中
    assert scope_of(seeded, SUPER).class_ids() == {"c1", "c2"}
    got = client.get("/api/break-glass/active", headers=hdr(SUPER)).json()
    assert got["session"]["session_id"] == session["session_id"]

    # 提前结束
    assert client.delete("/api/break-glass", headers=hdr(SUPER)).status_code == 200
    assert client.get("/api/break-glass/active", headers=hdr(SUPER)).json()["session"] is None
    assert scope_of(seeded, SUPER).class_ids() == set(), "用完即掉"


def test_starting_twice_does_not_stack(client, seeded):
    """同一时刻只保留一条生效中的提权 —— 否则「还开着哪一条」说不清。"""
    a = client.post("/api/break-glass", json={"reason": "第一次"}, headers=hdr(SUPER)).json()
    b = client.post("/api/break-glass", json={"reason": "第二次"}, headers=hdr(SUPER)).json()
    assert a["session"]["session_id"] == b["session"]["session_id"]
    assert seeded.query(BreakGlassSession).count() == 1


# ── 验证项 2：有审计记录 ──

def test_break_glass_writes_audit_log(client, seeded):
    """ADR-0011 的「全程留痕」：谁、什么时候、为什么、开了多久，都查得到。"""
    client.post("/api/break-glass", json={"reason": "排查一中成绩同步", "minutes": 20},
                headers=hdr(SUPER))

    start = seeded.query(OperationLog).filter_by(action="break_glass_start").one()
    assert start.user_id == "acc_super"
    assert start.target_type == "break_glass"
    assert start.detail["reason"] == "排查一中成绩同步"
    assert "expires_at" in start.detail

    client.delete("/api/break-glass", headers=hdr(SUPER))
    end = seeded.query(OperationLog).filter_by(action="break_glass_end").one()
    assert end.target_id == start.target_id  # 同一次提权
    assert end.detail["ended_at"] is not None


def test_audit_records_each_break_glass_separately(client, seeded):
    """两次提权 = 两条审计，各自独立可追溯。"""
    client.post("/api/break-glass", json={"reason": "第一次"}, headers=hdr(SUPER))
    client.delete("/api/break-glass", headers=hdr(SUPER))
    client.post("/api/break-glass", json={"reason": "第二次"}, headers=hdr(SUPER))

    starts = seeded.query(OperationLog).filter_by(action="break_glass_start").all()
    assert [s.detail["reason"] for s in starts] == ["第一次", "第二次"]


def test_break_glass_needs_a_token(client, seeded):
    assert client.post("/api/break-glass", json={"reason": "x"}).status_code == 401
    assert client.get("/api/break-glass/active").status_code == 401
    assert client.delete("/api/break-glass").status_code == 401

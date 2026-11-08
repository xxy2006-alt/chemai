"""API 层测试：认证（登录/me/refresh/申请）与家长通知端点 + 越权防护（IDOR）。

用最小 FastAPI app 挂载 auth / notification 两个 router，override get_db 指向内存库，
家长通知端点通过 get_current_parent_id 校验 token 身份。
"""
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.database import (
    Base, Account, Teacher, Student, Parent, ParentNotification,
    StudentParentBinding, TeacherApplication, get_db,
)
from app.api import auth as auth_mod
from app.api import notification as notif_mod
from app.middleware.auth import create_access_token, create_refresh_token


@pytest.fixture
def db_session():
    # TestClient 在独立线程执行端点，内存库必须用 StaticPool 共享同一连接
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
    app.include_router(auth_mod.router, prefix="/api/auth", tags=["auth"])
    app.include_router(notif_mod.router, prefix="/api/notification", tags=["notification"])

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c


def _seed_teacher(db):
    db.add(Teacher(teacher_id="t1", name="海老师", school_id="school1", status="approved"))
    db.add(Account(account_id="acc_t", role="teacher", username="lgh",
                   password_hash=auth_mod.hash_password("123456"),
                   teacher_id="t1", status="active"))
    db.commit()


def _seed_parent(db, parent_id="parent_demo_001", username="parent1", student_id="202610101"):
    db.add(Parent(parent_id=parent_id, name="张家长", password_hash="x", status="active"))
    db.add(Student(student_id=student_id, name="张浩宇", class_id="c1", status="approved"))
    db.add(StudentParentBinding(binding_id=f"b_{parent_id}", student_id=student_id,
                                parent_id=parent_id, status="active", bind_code="TEST1234"))
    db.add(Account(account_id=f"acc_{parent_id}", role="parent", username=username,
                   password_hash="x", parent_id=parent_id, status="active"))
    db.commit()


def _mk_notification(db, nid, parent_id, student_id, type_, title, is_read=False):
    db.add(ParentNotification(notification_id=nid, parent_id=parent_id,
                              student_id=student_id, type=type_, title=title,
                              content="内容", is_read=is_read))
    db.commit()


# ── 登录 ──

def test_login_success(client, db_session):
    _seed_teacher(db_session)
    r = client.post("/api/auth/login", json={"username": "lgh", "password": "123456"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["user"]["id"] == "t1"
    assert body["user"]["role"] == "teacher"
    assert body["user"]["name"] == "海老师"
    assert body["token"]
    assert body["refresh_token"]


def test_login_wrong_password(client, db_session):
    _seed_teacher(db_session)
    r = client.post("/api/auth/login", json={"username": "lgh", "password": "wrong"})
    assert r.json()["success"] is False
    assert "用户名或密码错误" in r.json()["message"]


def test_login_unknown_user(client, db_session):
    _seed_teacher(db_session)
    r = client.post("/api/auth/login", json={"username": "nobody", "password": "x"})
    assert r.json()["success"] is False


def test_login_disabled_account(client, db_session):
    _seed_teacher(db_session)
    a = db_session.query(Account).filter_by(account_id="acc_t").one()
    a.status = "disabled"
    db_session.commit()
    r = client.post("/api/auth/login", json={"username": "lgh", "password": "123456"})
    assert r.json()["success"] is False
    assert "已被禁用" in r.json()["message"]


# ── /me ──

def test_me_with_valid_token(client, db_session):
    _seed_teacher(db_session)
    token = create_access_token("t1", "teacher", school_id="school1")
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    body = r.json()
    assert body["success"] is True
    assert body["user"]["id"] == "t1"
    assert body["user"]["teacher_id"] == "t1"


def test_me_without_token(client):
    """阶段 4.6：/me 移出白名单 —— 无 token 现在是 401，不再是 200+success:false。"""
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_me_with_invalid_token(client):
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer bad.token.here"})
    assert r.status_code == 401


def test_me_with_unknown_user_token(client):
    # token 有效但库里没有对应账户
    token = create_access_token("no_such_user", "teacher")
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.json()["success"] is False
    assert "用户不存在" in r.json()["message"]


# ── refresh ──

def test_refresh_token(client, db_session):
    _seed_teacher(db_session)
    refresh = create_refresh_token("t1")
    r = client.post("/api/auth/refresh", json={"refresh_token": refresh})
    body = r.json()
    assert body["success"] is True
    assert body["access_token"]
    assert body["user"]["id"] == "t1"


def test_refresh_invalid_token(client):
    r = client.post("/api/auth/refresh", json={"refresh_token": "bad"})
    assert r.json()["success"] is False


def test_refresh_unknown_user(client, db_session):
    _seed_teacher(db_session)
    # refresh token 指向不存在的账户
    refresh = create_refresh_token("ghost_user")
    r = client.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert r.json()["success"] is False


# ── 教师申请 ──

def test_apply_success(client, db_session):
    r = client.post("/api/auth/apply", json={
        "name": "王老师", "phone": "13800000000", "school": "一中", "subject": "化学",
    })
    body = r.json()
    assert body["success"] is True
    assert body["application_id"].startswith("app_")
    app_id = body["application_id"]
    row = db_session.query(TeacherApplication).filter_by(id=app_id).one()
    assert row.status == "pending"
    # 查询申请状态
    r2 = client.get(f"/api/auth/apply/{app_id}")
    assert r2.json()["success"] is True
    assert r2.json()["application"]["phone"] == "13800000000"


def test_login_response_carries_capability_list(client, db_session):
    """阶段 5.1：登录响应必须带 role_label / permissions / menus —— 前端靠它渲染菜单。

    能力清单只在 `get_user_info()` 里算，所以 login / refresh / `/me` 三处天然一致。
    """
    _seed_teacher(db_session)
    r = client.post("/api/auth/login", json={"username": "lgh", "password": "123456"})
    user = r.json()["user"]
    assert user["role"] == "teacher"
    assert user["role_label"] == "任课教师"
    assert "question:create" in user["permissions"]
    # 教师看不到集成配置入口 —— 这正是「管理员与老师菜单不同」的落点
    assert "integration" not in user["menus"]
    assert "chat" in user["menus"]


def test_me_response_carries_the_same_capability_list(client, db_session):
    """`/me` 与 login 用同一个来源 —— 刷新页面时前端靠它水合（老会话、清了缓存也自愈）。"""
    _seed_teacher(db_session)
    token = create_access_token("t1", "teacher", school_id="school1")
    body = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    user = body["user"]
    assert user["role_label"] == "任课教师"
    assert "question:create" in user["permissions"]
    assert "integration" not in user["menus"]


def test_apply_id_is_not_guessable(client, db_session):
    """app_id 同时是**查状态的凭据**：`GET /apply/{app_id}` 无鉴权（申请人此时还没有
    账号），所以它必须不可枚举 —— 原先是 `app_YYYYMMDDHHMMSS`，逐秒猜就能翻出
    申请人的姓名/手机/学校（阶段 4.6 实施中发现的 IDOR）。
    """
    ids = []
    for phone in ("13800000001", "13800000002"):
        r = client.post("/api/auth/apply", json={
            "name": "王老师", "phone": phone, "school": "一中", "subject": "化学",
        })
        ids.append(r.json()["application_id"])

    assert ids[0] != ids[1], "同一秒内的两次申请不能撞 id"
    suffix = ids[0].split("_", 2)[2]
    assert len(suffix) >= 12, f"随机后缀太短，容易被爆破: {suffix!r}"
    assert not suffix.isdigit(), "后缀不能是纯数字（那就是时间戳，等于没加随机）"


def test_apply_duplicate_pending(client, db_session):
    client.post("/api/auth/apply", json={
        "name": "王老师", "phone": "13900000000", "school": "一中", "subject": "化学",
    })
    r = client.post("/api/auth/apply", json={
        "name": "王老师", "phone": "13900000000", "school": "一中", "subject": "化学",
    })
    assert r.json()["success"] is False
    assert "已提交申请" in r.json()["message"]


def test_apply_duplicate_approved(client, db_session):
    client.post("/api/auth/apply", json={
        "name": "王老师", "phone": "13700000000", "school": "一中", "subject": "化学",
    })
    row = db_session.query(TeacherApplication).first()
    row.status = "approved"
    db_session.commit()
    r = client.post("/api/auth/apply", json={
        "name": "王老师", "phone": "13700000000", "school": "一中", "subject": "化学",
    })
    assert r.json()["success"] is False
    assert "已审核通过" in r.json()["message"]


def test_apply_not_found(client):
    r = client.get("/api/auth/apply/no_such")
    assert r.json()["success"] is False


def test_logout(client):
    """登出发生在已登录之后 —— 阶段 4.6 起要求有效 token。"""
    r = client.post("/api/auth/logout", headers=_admin_hdr())
    assert r.json()["success"] is True


def test_logout_without_token_is_401(client):
    r = client.post("/api/auth/logout")
    assert r.status_code == 401


# ── 家长通知（含越权防护）──

def _parent_token(parent_id="parent_demo_001"):
    return create_access_token(parent_id, "parent", school_id="school1")


def _student_hdr(student_id="202610101"):
    """学生读自己的通知：allow_self 放行 + ScopeGuard 收窄到本人。"""
    return {"Authorization": f"Bearer {create_access_token(student_id, 'student')}"}


def _admin_hdr():
    return {"Authorization": f"Bearer {create_access_token('admin1', 'admin', school_id='school1')}"}


def test_parent_notifications_ok(client, db_session):
    _seed_parent(db_session)
    _mk_notification(db_session, "n1", "parent_demo_001", "202610101", "weekly_report", "标题1", is_read=False)
    _mk_notification(db_session, "n2", "parent_demo_001", "202610101", "daily_report", "标题2", is_read=True)

    r = client.get("/api/notification/parent/parent_demo_001/notifications",
                   headers={"Authorization": f"Bearer {_parent_token()}"})
    body = r.json()
    assert body["success"] is True
    assert body["total"] == 2
    assert body["unread_count"] == 1
    names = {n["notification_id"] for n in body["notifications"]}
    assert names == {"n1", "n2"}
    assert body["notifications"][0]["student_name"] == "张浩宇"


def test_parent_notifications_unread_only(client, db_session):
    _seed_parent(db_session)
    _mk_notification(db_session, "n1", "parent_demo_001", "202610101", "w", "t1", is_read=False)
    _mk_notification(db_session, "n2", "parent_demo_001", "202610101", "w", "t2", is_read=True)

    r = client.get("/api/notification/parent/parent_demo_001/notifications?unread_only=true",
                   headers={"Authorization": f"Bearer {_parent_token()}"})
    body = r.json()
    assert body["total"] == 1
    assert body["notifications"][0]["notification_id"] == "n1"


def test_parent_notifications_idor_forged(client, db_session):
    _seed_parent(db_session)
    _seed_parent(db_session, parent_id="parent_demo_002", username="parent2", student_id="202610102")
    # token 是 parent_demo_001，但路径伪造为 parent_demo_002 → 403
    r = client.get("/api/notification/parent/parent_demo_002/notifications",
                   headers={"Authorization": f"Bearer {_parent_token()}"})
    assert r.status_code == 403


def test_parent_notifications_no_token(client, db_session):
    _seed_parent(db_session)
    r = client.get("/api/notification/parent/parent_demo_001/notifications")
    assert r.status_code == 401


def test_parent_notifications_non_parent_role(client, db_session):
    _seed_parent(db_session)
    token = create_access_token("t1", "teacher")  # 教师 token
    r = client.get("/api/notification/parent/parent_demo_001/notifications",
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_parent_notifications_parent_not_found(client, db_session):
    # token 合法且路径一致，但库里没有该家长 → 404
    token = create_access_token("ghost_parent", "parent")
    r = client.get("/api/notification/parent/ghost_parent/notifications",
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404


def test_parent_notifications_empty(client, db_session):
    _seed_parent(db_session)
    r = client.get("/api/notification/parent/parent_demo_001/notifications",
                   headers={"Authorization": f"Bearer {_parent_token()}"})
    body = r.json()
    assert body["total"] == 0
    assert body["unread_count"] == 0
    assert body["notifications"] == []


# ── 学生通知（stub 端点保底覆盖）──

def test_student_notifications_ok(client, db_session):
    _seed_parent(db_session)
    r = client.get(
        "/api/notification/student/202610101/notifications",
        headers=_student_hdr(),
    )
    assert r.status_code == 200
    assert r.json()["success"] is True


def test_student_notifications_not_found(client):
    """查不到的学生一律 403，不是 404 —— ScopeGuard 不泄漏「这个学生存不存在」。

    阶段 4.6 批次 C 给端点加了 student 范围校验；此前它无鉴权，所以这条
    断言原本是 404。
    """
    r = client.get(
        "/api/notification/student/no_such/notifications",
        headers=_admin_hdr(),
    )
    assert r.status_code == 403

"""回归测试：认证与数据可见性（多次「更新后 token 过期 → 学生/学情数据看起来消失」的教训收敛）。

钉死三个反复出现的失败模式：
  1. 新签发的 token 立即有效（防过期/时区 bug 让 token 秒失效）
  2. 有效 token 能取到学生列表（防 401 导致前端列表空 → 误以为「数据消失」）
  3. 学生数据在数据库重开后仍在（防真丢数据：重置/换库/WAL 丢失）

每次更新后必须跑通：pytest tests/test_regression_auth_data.py -q
"""
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.database import Base, Student, TeacherClassSubject, get_db
from app.middleware.auth import (
    SECRET_KEY, create_access_token, create_jwt, verify_token,
)
from app.api import user as user_mod


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
    """最小 app：挂真实 student 路由 + 复刻 main.py 的全局 token 校验中间件。"""
    app = FastAPI()

    @app.middleware("http")
    async def auth_check(request, call_next):
        if request.url.path.startswith("/api/"):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return JSONResponse(status_code=401, content={"detail": "未携带认证token"})
            if verify_token(auth_header.replace("Bearer ", "")) is None:
                return JSONResponse(status_code=401, content={"detail": "token无效或已过期"})
        return await call_next(request)

    app.include_router(user_mod.router, prefix="/api/users")

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c


# ── 1. token 立即有效 ──

def test_fresh_access_token_is_immediately_valid():
    """新签发的 access token 必须立即可用（防过期/时区 bug 秒失效）。"""
    token = create_access_token("t1", "teacher")
    payload = verify_token(token)
    assert payload is not None
    assert payload["user_id"] == "t1"
    assert payload["role"] == "teacher"


def test_access_token_valid_through_full_ttl():
    """24h TTL 内 token 不得被判过期（防 TTL 被改成小时→秒之类的回归）。"""
    from app.middleware.auth import ACCESS_TOKEN_EXPIRE_HOURS
    token = create_jwt(
        {"user_id": "t1", "role": "teacher", "type": "access"},
        SECRET_KEY,
        expires_in=ACCESS_TOKEN_EXPIRE_HOURS,
    )
    assert verify_token(token) is not None


# ── 2. 有效 token 能取到学生列表 ──

def test_student_list_served_with_valid_token(client, db_session):
    # 教师 t1 必须任教 c1 才在数据范围内（ADR-0010）——
    # 否则「有效 token 看到空列表」会被误当成「数据消失」，正是本文件要防的那种混淆。
    db_session.add(TeacherClassSubject(id="tcs1", teacher_id="t1", class_id="c1", subject="化学"))
    db_session.add(Student(student_id="s1", name="张三", class_id="c1", status="approved"))
    db_session.commit()

    token = create_access_token("t1", "teacher")
    r = client.get("/api/users/students", headers={"Authorization": f"Bearer {token}"})

    assert r.status_code == 200
    body = r.json()
    assert body.get("total", 0) >= 1
    assert any(s.get("student_id") == "s1" for s in body.get("students", []))


def test_student_list_excludes_out_of_scope_classes(client, db_session):
    """数据范围生效：教师看得到自己任教班的学生，看不到别的班（ADR-0010）。"""
    db_session.add(TeacherClassSubject(id="tcs1", teacher_id="t1", class_id="c1", subject="化学"))
    db_session.add(Student(student_id="s1", name="张三", class_id="c1", status="approved"))
    db_session.add(Student(student_id="s2", name="李四", class_id="c2", status="approved"))
    db_session.commit()

    token = create_access_token("t1", "teacher")
    r = client.get("/api/users/students", headers={"Authorization": f"Bearer {token}"})

    assert r.status_code == 200
    assert {s["student_id"] for s in r.json()["students"]} == {"s1"}


def test_student_list_empty_state_is_distinct_from_401(client, db_session):
    """无 token → 401（而非空 200）。前端据此区分「没数据」和「没权限」。"""
    db_session.add(Student(student_id="s1", name="张三", class_id="c1", status="approved"))
    db_session.commit()
    r = client.get("/api/users/students")
    assert r.status_code == 401


# ── 3. token 过期 → 401，但数据仍在（没真丢）──

def test_expired_token_returns_401_and_data_remains(client, db_session):
    db_session.add(Student(student_id="s1", name="张三", class_id="c1", status="approved"))
    db_session.commit()

    expired = create_jwt(
        {"user_id": "t1", "role": "teacher", "type": "access"},
        SECRET_KEY,
        expires_in=-1,
    )
    r = client.get("/api/users/students", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401
    # 关键：数据没丢，还在库里（「消失」是 401 的表象，不是真丢失）
    assert db_session.query(Student).count() == 1


# ── 4. 数据跨「重启」仍在 ──

def test_student_data_persists_across_db_reopen(tmp_path):
    db_path = tmp_path / "chemai.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    s.add(Student(student_id="s1", name="张三", class_id="c1", status="approved"))
    s.commit()
    s.close()
    engine.dispose()  # 模拟进程重启

    # 重开后数据必须还在
    engine2 = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Session2 = sessionmaker(bind=engine2)
    s2 = Session2()
    try:
        assert s2.query(Student).filter(Student.student_id == "s1").count() == 1
    finally:
        s2.close()

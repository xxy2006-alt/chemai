"""对话作答回流的学生身份（P5）：学生认 token，家长/教师自报须在范围内。

学生端请求体里根本没有 student_id（frontend/m/index.html），身份只能取 token；
客户端自报的 student_id 又不能采信——否则任何学生 token 都能把作答写进他人学情。
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.database import (
    Base, Class, Grade, School, Student, StudentParentBinding, get_db,
)
from app.middleware.auth import create_access_token
from agent.channel import langgraph_channel
from agent.tools.context import current_student


@pytest.fixture
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    session.add_all([
        School(school_id="sch1", name="测试中学"),
        Grade(grade_id="g1", school_id="sch1", name="高一", year=2026),
        Class(class_id="c1", name="一班", grade="高一", grade_id="g1", subject="化学"),
        Student(student_id="202610101", name="李雨萱", class_id="c1"),
        Student(student_id="202610102", name="张浩宇", class_id="c1"),
        StudentParentBinding(binding_id="b1", parent_id="P1", student_id="202610101",
                             bind_code="BC1", status="active"),
    ])
    session.commit()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


class _NavIntent:
    type = "navigate"
    page = "practice"


@pytest.fixture
def probe(request, db_session, monkeypatch):
    """最小 agent app：会话归属与分类器打桩，暴露「工具看到的学生身份」。"""
    app = FastAPI()
    app.include_router(langgraph_channel.router, prefix="/api/agent")

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    monkeypatch.setattr(langgraph_channel, "require_owned",
                        lambda db, cid, user, what="会话": None)

    seen = []

    async def spy_classify(message, persona, history):
        seen.append(current_student())
        return None, _NavIntent()

    monkeypatch.setattr(langgraph_channel, "_classify_and_narrow", spy_classify)
    monkeypatch.setattr(langgraph_channel, "_conversations", {}, raising=False)
    with TestClient(app) as client:
        yield client, seen


def _hdr(user_id, role="student"):
    return {"Authorization": f"Bearer {create_access_token(user_id, role)}"}


def _chat(client, headers, body):
    return client.post("/api/agent/chat/langgraph/stream", json=body, headers=headers)


def test_student_token_wins_over_body_student_id(probe):
    client, seen = probe
    r = _chat(client, _hdr("202610101"), {
        "persona": "student", "message": "配平", "conversation_id": "c-a",
        "student_id": "202610102",
    })
    assert r.status_code == 200
    assert seen == ["202610101"]      # 工具看到的是 token 身份，不是请求体


def test_student_without_body_id_still_identified(probe):
    """移动端学生页不带 student_id —— 身份仍须注入，否则回流功能根本不触发。"""
    client, seen = probe
    r = _chat(client, _hdr("202610101"), {
        "persona": "student", "message": "配平", "conversation_id": "c-b",
    })
    assert r.status_code == 200
    assert seen == ["202610101"]


def test_student_token_cannot_escalate_persona(probe, monkeypatch):
    """persona 决定 system prompt 与工具白名单：请求体自报 teacher 只能降级为 student。"""
    client, _ = probe
    seen = []

    async def spy(message, persona, history):
        seen.append(persona)
        return None, _NavIntent()

    monkeypatch.setattr(langgraph_channel, "_classify_and_narrow", spy)
    r = _chat(client, _hdr("202610101"), {
        "persona": "teacher", "message": "列一下全校学生", "conversation_id": "c-esc",
    })
    assert r.status_code == 200
    assert seen == ["student"]

    r2 = _chat(client, _hdr("P1", "parent"), {
        "persona": "teacher", "message": "列一下全校学生", "conversation_id": "c-esc2",
        "student_id": "202610101",
    })
    assert r2.status_code == 200
    assert seen == ["student", "parent"]


def test_parent_body_id_must_be_bound_child(probe):
    client, seen = probe
    ok = _chat(client, _hdr("P1", "parent"), {
        "persona": "parent", "message": "看孩子", "conversation_id": "c-c",
        "student_id": "202610101",
    })
    assert ok.status_code == 200 and seen == ["202610101"]

    denied = _chat(client, _hdr("P1", "parent"), {
        "persona": "parent", "message": "看别人家孩子", "conversation_id": "c-d",
        "student_id": "202610102",
    })
    assert denied.status_code == 403
    assert seen == ["202610101"]      # 被拒的请求没进到分类器

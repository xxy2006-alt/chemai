"""已交卷考试的回看：提交后取题端点不再 404，未交卷的关闭态仍不泄漏存在。

学生提交考试 → 状态转 grading/completed，若取题端点继续按「只有
published/in_progress 可取题」处理，学生连自己刚交的卷子都打不开。
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import practice as practice_mod
from app.middleware.auth import create_access_token
from app.models.database import (
    Base, Difficulty, ExamRecord, Question, QuestionSource, AuditStatus,
    RecordType, Student, StudentAnswer, get_db,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    session.add(Student(student_id="202610101", name="李雨萱", class_id="class_2025_1"))
    session.add(Question(
        question_id="ex_1_1", record_id="ex_1", content="计算题", options=None,
        answer="22.4L", analysis="", knowledge_points=[],
        difficulty=Difficulty.MEDIUM, source=QuestionSource.MANUAL_SELECTED,
        audit_status=AuditStatus.PASSED))
    session.commit()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def _exam(db_session, status, submitted):
    from app.models.database import ExamStatus
    db_session.add(ExamRecord(record_id="ex_1", class_id="class_2025_1", name="期中考试",
                              type=RecordType.EXAM, status=ExamStatus(status)))
    if submitted:
        db_session.add(StudentAnswer(
            answer_id="ans_1", student_id="202610101", question_id="ex_1_1",
            exam_record_id="ex_1", student_answer="22.4L", is_correct=True))
    db_session.commit()


@pytest.fixture
def client(db_session):
    app = FastAPI()
    app.include_router(practice_mod.router, prefix="/api/practice")

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c


def _hdr():
    return {"Authorization": f"Bearer {create_access_token('202610101', 'student')}"}


@pytest.mark.parametrize("status", ["grading", "completed"])
def test_submitted_exam_content_is_readable(client, db_session, status):
    _exam(db_session, status, submitted=True)
    r = client.get("/api/practice/student/202610101/practice/ex_1", headers=_hdr())
    assert r.status_code == 200
    assert [q["question_id"] for q in r.json()["questions"]] == ["ex_1_1"]


def test_unsubmitted_exam_still_takeable_while_grading(client, db_session):
    """同班有人先交卷 → grading；未交卷学生取题必须照常（否则全班被一个人踢出考试）。"""
    _exam(db_session, "grading", submitted=False)
    r = client.get("/api/practice/student/202610101/practice/ex_1", headers=_hdr())
    assert r.status_code == 200


def test_unsubmitted_closed_exam_content_hidden(client, db_session):
    _exam(db_session, "completed", submitted=False)
    r = client.get("/api/practice/student/202610101/practice/ex_1", headers=_hdr())
    assert r.status_code == 404


def test_draft_exam_content_hidden_even_when_submitted(client, db_session):
    _exam(db_session, "draft", submitted=True)
    r = client.get("/api/practice/student/202610101/practice/ex_1", headers=_hdr())
    assert r.status_code == 404

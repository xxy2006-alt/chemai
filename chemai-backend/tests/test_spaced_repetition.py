"""SpacedRepetitionEngine 间隔重复复习引擎测试。

覆盖艾宾浩斯节点计算、任务创建/去重、到期筛选、升级降级、掌握(done)状态、
复习任务生成与错题同步。
"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.database import Student, Question, StudentAnswer, Base
from app.models.review_task import (
    ReviewTask, calculate_next_review_date, SPIRAL_REVIEW_DAYS,
)
import app.services.spaced_repetition as sr_mod


@pytest.fixture
def db_session():
    """覆盖 conftest：服务在 commit 后立即 close session，
    默认 expire_on_commit=True 会让返回对象属性过期抛 DetachedInstanceError。
    这里关闭自动过期，专注验证业务逻辑本身。"""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, expire_on_commit=False)()
    yield s
    s.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def sr(monkeypatch, db_session):
    """把引擎内的 get_db 指向测试会话，避免写真实 chemai.db。"""
    def fake_get_db():
        yield db_session

    monkeypatch.setattr(sr_mod, "get_db", fake_get_db)
    return sr_mod.sre


@pytest.fixture
def student(db_session):
    s = Student(student_id="s_review", name="测试学生", class_id="c1", status="approved")
    db_session.add(s)
    db_session.commit()
    return s


def _mk_question(db, qid, content="测试题目内容", kps=None):
    q = Question(question_id=qid, content=content, knowledge_points=kps or ["氧化还原"])
    db.add(q)
    db.commit()
    return q


# ── 艾宾浩斯节点 ──

def test_calculate_next_review_date_by_level():
    for level, days in SPIRAL_REVIEW_DAYS.items():
        if days is None:
            assert calculate_next_review_date(level) is None
        else:
            nxt = calculate_next_review_date(level)
            assert nxt is not None
            # 允许秒级误差
            assert abs((nxt - (datetime.utcnow() + timedelta(days=days))).total_seconds()) < 60


def test_spiral_days_monotonic():
    """复习间隔应随级别递增。"""
    days = [SPIRAL_REVIEW_DAYS[l] for l in range(5)]
    assert days == sorted(days)
    assert days[0] == 1


# ── 任务创建 / 去重 ──

def test_create_review_task(sr, student):
    task = sr.create_review_task(student.student_id, "q1")
    assert task.task_id.startswith("review_")
    assert task.review_level == 0
    assert task.status == "pending"
    assert task.consecutive_correct == 0


def test_create_review_task_dedup(sr, student):
    t1 = sr.create_review_task(student.student_id, "q1")
    t2 = sr.create_review_task(student.student_id, "q1")
    assert t1.task_id == t2.task_id


# ── 到期筛选 ──

def test_get_due_review_tasks(sr, student, db_session):
    past = ReviewTask(
        task_id="due_1", student_id=student.student_id, question_id="q1",
        review_level=1, status="pending",
        next_review_at=datetime.utcnow() - timedelta(days=1),
    )
    future = ReviewTask(
        task_id="due_2", student_id=student.student_id, question_id="q2",
        review_level=0, status="pending",
        next_review_at=datetime.utcnow() + timedelta(days=10),
    )
    done = ReviewTask(
        task_id="due_3", student_id=student.student_id, question_id="q3",
        review_level=5, status="done",
        next_review_at=datetime.utcnow() - timedelta(days=1),
    )
    db_session.add_all([past, future, done])
    db_session.commit()

    due = sr.get_due_review_tasks(student.student_id)
    ids = {t.task_id for t in due}
    assert ids == {"due_1"}


# ── 升级 / 降级 / 掌握 ──

def test_complete_review_correct_level_up(sr, student):
    t = sr.create_review_task(student.student_id, "q1")
    # 第 1 次答对：连续正确=1，不升级
    t = sr.complete_review(t.task_id, True)
    assert t.consecutive_correct == 1
    assert t.review_level == 0
    # 第 2 次答对：连续正确=2，升级
    t = sr.complete_review(t.task_id, True)
    assert t.review_level == 1
    assert t.consecutive_correct == 0


def test_complete_review_wrong_downgrades(sr, student):
    t = sr.create_review_task(student.student_id, "q1")
    sr.complete_review(t.task_id, True)
    t = sr.complete_review(t.task_id, True)  # level 1
    assert t.review_level == 1
    t = sr.complete_review(t.task_id, False)  # 答错 → 降回 0
    assert t.review_level == 0
    # 已在 0 级时答错不再降
    t = sr.complete_review(t.task_id, False)
    assert t.review_level == 0


def test_complete_review_reaches_done(sr, student):
    """连续答对 10 次到达 level 5 → 标记 done、不再安排复习。"""
    t = sr.create_review_task(student.student_id, "q1")
    for _ in range(10):
        t = sr.complete_review(t.task_id, True)
    assert t.review_level == 5
    assert t.next_review_at is None
    assert t.status == "done"
    assert len(t.review_history or []) == 10


def test_complete_review_missing_task(sr):
    assert sr.complete_review("no_such_task", True) is None


def test_review_history_records_level_before(sr, student):
    t = sr.create_review_task(student.student_id, "q1")
    t = sr.complete_review(t.task_id, True)
    assert t.review_history[-1]["level_before"] == 0
    assert t.review_history[-1]["is_correct"] is True


# ── 复习任务生成 / 错题同步 ──

def test_generate_review_for_student(sr, student, db_session):
    _mk_question(db_session, "q_gen", content="配平 Fe2O3 + CO = Fe + CO2")
    t = sr.create_review_task(student.student_id, "q_gen")
    items = sr.generate_review_for_student(student.student_id, limit=10)
    assert len(items) == 1
    assert items[0]["question_id"] == "q_gen"
    assert items[0]["content"] == "配平 Fe2O3 + CO = Fe + CO2"
    assert items[0]["task_id"] == t.task_id


def test_generate_review_for_student_empty(sr, student):
    assert sr.generate_review_for_student(student.student_id) == []


def test_sync_from_wrong_answers(sr, student, db_session):
    _mk_question(db_session, "q_wrong")
    db_session.add(StudentAnswer(
        answer_id="a1", student_id=student.student_id, question_id="q_wrong",
        is_correct=False, answered_at=datetime.utcnow(),
    ))
    db_session.commit()

    sr.sync_review_tasks_from_wrong_answers(student.student_id)
    tasks = sr.get_due_review_tasks(student.student_id)
    assert {t.question_id for t in tasks} == {"q_wrong"}

    # 再次同步不产生重复任务
    sr.sync_review_tasks_from_wrong_answers(student.student_id)
    assert len(sr.get_due_review_tasks(student.student_id)) == 1

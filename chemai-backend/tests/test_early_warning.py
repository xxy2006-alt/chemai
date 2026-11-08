"""EarlyWarningService 学情预警服务测试。

覆盖：连续未登录（从未登录 / 登录时间过久）、成绩下滑（级别/临界）、错题率过高、
预警去重、处理预警、待处理列表、按学生查询、check_all_warnings 全量遍历。
"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.database import (
    Base, Student, StudentAnswer, ExamRecord, StudentParentBinding, RecordType,
)
from app.models.warning_log import WarningLog
import app.services.early_warning as ew_mod


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, expire_on_commit=False)()
    yield s
    s.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def ews(monkeypatch, db_session):
    def fake_get_db():
        yield db_session

    monkeypatch.setattr(ew_mod, "get_db", fake_get_db)
    # 阻止真实发送家长通知（其内部使用真实 chemai.db）
    monkeypatch.setattr(
        ew_mod.notification_service, "send_warning_notification",
        lambda **kwargs: 0,
    )
    return ew_mod.ews


def _mk_student(db, sid="s_w", name="测试生", created_days_ago=0, last_exercise_days_ago=None):
    created = datetime.utcnow() - timedelta(days=created_days_ago)
    last = datetime.utcnow() - timedelta(days=last_exercise_days_ago) if last_exercise_days_ago is not None else None
    s = Student(student_id=sid, name=name, class_id="c1", status="approved",
                created_at=created, last_exercise_at=last)
    db.add(s)
    db.commit()
    return s


def _mk_exam(db, record_id, class_id, avg_score, exam_date, rtype=RecordType.EXAM):
    r = ExamRecord(record_id=record_id, class_id=class_id, type=rtype,
                   avg_score=avg_score, exam_date=exam_date, name="月考")
    db.add(r)
    db.commit()
    return r


# ── 连续未登录 ──

def test_no_login_warning_never_logged_in(ews, db_session):
    _mk_student(db_session, "s1", created_days_ago=4, last_exercise_days_ago=None)
    s = db_session.query(Student).filter_by(student_id="s1").one()
    w = ews.check_no_login_warning(db_session, s)
    assert w is not None
    assert w.warning_type == "no_login"
    assert "已连续4天未学习" in w.title
    assert "从未登录" in w.content
    assert w.data == {"days": 4}


def test_no_login_warning_recent_no_warning(ews, db_session):
    _mk_student(db_session, "s2", created_days_ago=1, last_exercise_days_ago=None)
    s = db_session.query(Student).filter_by(student_id="s2").one()
    assert ews.check_no_login_warning(db_session, s) is None


def test_no_login_warning_last_exercise_old(ews, db_session):
    _mk_student(db_session, "s3", created_days_ago=0, last_exercise_days_ago=5)
    s = db_session.query(Student).filter_by(student_id="s3").one()
    w = ews.check_no_login_warning(db_session, s)
    assert w is not None
    assert "已连续5天未学习" in w.title


def test_no_login_warning_recent_exercise_no_warning(ews, db_session):
    _mk_student(db_session, "s4", created_days_ago=0, last_exercise_days_ago=1)
    s = db_session.query(Student).filter_by(student_id="s4").one()
    assert ews.check_no_login_warning(db_session, s) is None


# ── 成绩下滑 ──

def test_score_drop_warning_levels(ews, db_session):
    _mk_student(db_session, "sd1")
    _mk_exam(db_session, "r1", "c1", 80, datetime.utcnow() - timedelta(days=10))
    _mk_exam(db_session, "r2", "c1", 70, datetime.utcnow())  # 下滑 12.5%
    s = db_session.query(Student).filter_by(student_id="sd1").one()
    w = ews.check_score_drop_warning(db_session, s)
    assert w is not None
    assert w.warning_type == "score_drop"
    assert w.level == "warning"  # < 0.2


def test_score_drop_critical(ews, db_session):
    _mk_student(db_session, "sd2")
    _mk_exam(db_session, "r1", "c1", 100, datetime.utcnow() - timedelta(days=10))
    _mk_exam(db_session, "r2", "c1", 60, datetime.utcnow())  # 下滑 40%
    s = db_session.query(Student).filter_by(student_id="sd2").one()
    w = ews.check_score_drop_warning(db_session, s)
    assert w.level == "critical"
    assert w.data["drop_rate"] == pytest.approx(0.4)


def test_score_drop_no_warning(ews, db_session):
    _mk_student(db_session, "sd3")
    _mk_exam(db_session, "r1", "c1", 80, datetime.utcnow() - timedelta(days=10))
    _mk_exam(db_session, "r2", "c1", 79, datetime.utcnow())  # 下滑 1.25%
    s = db_session.query(Student).filter_by(student_id="sd3").one()
    assert ews.check_score_drop_warning(db_session, s) is None


def test_score_drop_insufficient_records(ews, db_session):
    _mk_student(db_session, "sd4")
    _mk_exam(db_session, "r1", "c1", 80, datetime.utcnow())
    s = db_session.query(Student).filter_by(student_id="sd4").one()
    assert ews.check_score_drop_warning(db_session, s) is None


def test_score_drop_previous_zero(ews, db_session):
    _mk_student(db_session, "sd5")
    _mk_exam(db_session, "r1", "c1", 0, datetime.utcnow() - timedelta(days=10))
    _mk_exam(db_session, "r2", "c1", 50, datetime.utcnow())
    s = db_session.query(Student).filter_by(student_id="sd5").one()
    assert ews.check_score_drop_warning(db_session, s) is None


# ── 错题率过高 ──

def _seed_answers(db, record_id, sid, wrong, right):
    n = 0
    for _ in range(wrong):
        db.add(StudentAnswer(
            answer_id=f"a_{record_id}_{n}", student_id=sid,
            question_id="q", exam_record_id=record_id,
            is_correct=False, answered_at=datetime.utcnow(),
        ))
        n += 1
    for _ in range(right):
        db.add(StudentAnswer(
            answer_id=f"a_{record_id}_{n}", student_id=sid,
            question_id="q", exam_record_id=record_id,
            is_correct=True, answered_at=datetime.utcnow(),
        ))
        n += 1
    db.commit()


def test_high_error_rate_warning(ews, db_session):
    _mk_student(db_session, "er1")
    _mk_exam(db_session, "rr1", "c1", 70, datetime.utcnow())
    _seed_answers(db_session, "rr1", "er1", wrong=2, right=2)  # 50%
    s = db_session.query(Student).filter_by(student_id="er1").one()
    w = ews.check_high_error_rate_warning(db_session, s)
    assert w is not None
    assert w.warning_type == "high_error_rate"
    assert w.level == "info"  # < 0.7
    assert w.data["error_rate"] == pytest.approx(0.5)


def test_high_error_rate_warning_severe(ews, db_session):
    _mk_student(db_session, "er2")
    _mk_exam(db_session, "rr2", "c1", 70, datetime.utcnow())
    _seed_answers(db_session, "rr2", "er2", wrong=3, right=1)  # 75%
    s = db_session.query(Student).filter_by(student_id="er2").one()
    w = ews.check_high_error_rate_warning(db_session, s)
    assert w.level == "warning"


def test_high_error_rate_no_warning(ews, db_session):
    _mk_student(db_session, "er3")
    _mk_exam(db_session, "rr3", "c1", 70, datetime.utcnow())
    _seed_answers(db_session, "rr3", "er3", wrong=1, right=4)  # 20%
    s = db_session.query(Student).filter_by(student_id="er3").one()
    assert ews.check_high_error_rate_warning(db_session, s) is None


def test_high_error_rate_no_record(ews, db_session):
    _mk_student(db_session, "er4")
    s = db_session.query(Student).filter_by(student_id="er4").one()
    assert ews.check_high_error_rate_warning(db_session, s) is None


def test_high_error_rate_no_answers(ews, db_session):
    _mk_student(db_session, "er5")
    _mk_exam(db_session, "rr5", "c1", 70, datetime.utcnow())
    s = db_session.query(Student).filter_by(student_id="er5").one()
    assert ews.check_high_error_rate_warning(db_session, s) is None


# ── 去重 / 处理 / 列表 ──

def test_create_warning_dedup_pending(ews, db_session):
    _mk_student(db_session, "dd1", created_days_ago=4)
    s = db_session.query(Student).filter_by(student_id="dd1").one()
    w1 = ews.check_no_login_warning(db_session, s)
    w2 = ews.check_no_login_warning(db_session, s)
    assert w1.warning_id == w2.warning_id
    assert db_session.query(WarningLog).count() == 1


def test_process_warning(ews, db_session):
    _mk_student(db_session, "pw1", created_days_ago=4)
    s = db_session.query(Student).filter_by(student_id="pw1").one()
    w = ews.check_no_login_warning(db_session, s)
    res = ews.process_warning(db_session, w.warning_id, processed_by="t1", note="已联系家长")
    assert res.status == "processed"
    assert res.processed_by == "t1"
    assert res.processed_note == "已联系家长"
    assert res.processed_at is not None


def test_process_warning_missing(ews, db_session):
    assert ews.process_warning(db_session, "nope", processed_by="t1") is None


def test_get_pending_warnings_by_class(ews, db_session):
    _mk_student(db_session, "gp1", created_days_ago=4)
    s = db_session.query(Student).filter_by(student_id="gp1").one()
    ews.check_no_login_warning(db_session, s)
    # 同班 → 能查到
    assert len(ews.get_pending_warnings(db_session, class_id="c1")) == 1
    # 其他班 → 查不到
    assert ews.get_pending_warnings(db_session, class_id="c9") == []
    # 不限班级 → 能查到
    assert len(ews.get_pending_warnings(db_session)) == 1


def test_get_warnings_by_student(ews, db_session):
    _mk_student(db_session, "gw1", created_days_ago=4)
    s = db_session.query(Student).filter_by(student_id="gw1").one()
    ews.check_no_login_warning(db_session, s)
    ws = ews.get_warnings_by_student(db_session, "gw1")
    assert len(ws) == 1
    assert ews.get_warnings_by_student(db_session, "no_such") == []


# ── check_all_warnings 全量遍历 ──

def test_check_all_warnings(ews, db_session):
    _mk_student(db_session, "ca1", created_days_ago=4)  # 触发 no_login
    _mk_student(db_session, "ca2", created_days_ago=0, last_exercise_days_ago=1)  # 正常
    created = ews.check_all_warnings()
    assert len(created) == 1
    assert created[0].warning_type == "no_login"
    assert created[0].student_id == "ca1"

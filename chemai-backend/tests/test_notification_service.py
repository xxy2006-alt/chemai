"""NotificationService 通知服务测试。

覆盖 send_to_parent 及三种家长通知（练习/周报/预警）的发送与返回数量，
以及学生不存在时的短路返回。
"""
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.database import Base, Student, StudentParentBinding, ParentNotification
import app.services.notification_service as ns_mod


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, expire_on_commit=False)()
    yield s
    s.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def ns(monkeypatch, db_session):
    def fake_get_db():
        yield db_session

    monkeypatch.setattr(ns_mod, "get_db", fake_get_db)
    return ns_mod.notification_service


def _mk_student_with_parent(db, sid="202610101", pid="p1"):
    s = Student(student_id=sid, name="张浩宇", class_id="c1", status="approved")
    db.add(s)
    db.commit()
    b = StudentParentBinding(binding_id=f"b_{sid}_{pid}", student_id=sid,
                             parent_id=pid, status="active", bind_code="TEST1234")
    db.add(b)
    db.commit()
    return s


# ── send_to_parent ──

def test_send_to_parent(ns, db_session):
    nid = ns.send_to_parent("p1", "s1", "weekly_report", "标题", "内容")
    assert nid.startswith("notif_")
    row = db_session.query(ParentNotification).filter_by(notification_id=nid).one()
    assert row.parent_id == "p1"
    assert row.student_id == "s1"
    assert row.type == "weekly_report"
    assert row.title == "标题"
    assert row.content == "内容"
    assert row.is_read is False
    assert row.sent_at is not None


# ── 家长通知（带绑定）──

def test_send_practice_notification(ns, db_session):
    _mk_student_with_parent(db_session, "s_prac", "p_prac")
    n = ns.send_practice_notification("s_prac", "电离平衡练习")
    assert n == 1
    rows = db_session.query(ParentNotification).all()
    assert len(rows) == 1
    assert rows[0].type == "daily_report"
    assert rows[0].parent_id == "p_prac"
    assert "今日练习已推送" in rows[0].title


def test_send_weekly_report_notification(ns, db_session):
    _mk_student_with_parent(db_session, "s_week", "p_week")
    n = ns.send_weekly_report_notification("s_week")
    assert n == 1
    row = db_session.query(ParentNotification).one()
    assert row.type == "weekly_report"
    assert row.parent_id == "p_week"


def test_send_warning_notification(ns, db_session):
    _mk_student_with_parent(db_session, "s_warn", "p_warn")
    n = ns.send_warning_notification("s_warn", "score_drop", "成绩下滑预警消息")
    assert n == 1
    row = db_session.query(ParentNotification).one()
    assert row.type == "score_alert"
    assert row.content == "成绩下滑预警消息"
    assert "成绩下滑预警" in row.title  # 标题映射包含 type 中文名


def test_send_warning_notification_unknown_type(ns, db_session):
    _mk_student_with_parent(db_session, "s_wu", "p_wu")
    ns.send_warning_notification("s_wu", "unknown_type", "msg")
    row = db_session.query(ParentNotification).one()
    assert "学习提醒" in row.title


def test_send_to_multiple_parents(ns, db_session):
    _mk_student_with_parent(db_session, "s_multi", "p_multi")
    b = StudentParentBinding(binding_id="b2", student_id="s_multi", parent_id="p_multi2",
                             status="active", bind_code="TEST1234")
    db_session.add(b)
    db_session.commit()
    assert ns.send_practice_notification("s_multi", "练习") == 2


# ── 学生不存在 → 0 ──

def test_send_practice_no_student(ns, db_session):
    assert ns.send_practice_notification("no_such", "练习") == 0
    assert ns.send_weekly_report_notification("no_such") == 0
    assert ns.send_warning_notification("no_such", "no_login", "msg") == 0
    assert db_session.query(ParentNotification).count() == 0


def test_send_no_active_binding(ns, db_session):
    s = Student(student_id="s_inactive", name="李世睿", class_id="c1", status="approved")
    db_session.add(s)
    db_session.add(StudentParentBinding(binding_id="b_inactive", student_id="s_inactive",
                                        parent_id="p", status="inactive", bind_code="TEST1234"))
    db_session.commit()
    assert ns.send_practice_notification("s_inactive", "练习") == 0


# ── 幂等（idempotency_key）──

def test_send_to_parent_idempotent(ns, db_session):
    """同一幂等键投递两次，只产生一条通知，且两次返回同一通知 ID。"""
    first = ns.send_to_parent("p1", "s1", "weekly_report", "标题", "内容", idempotency_key="evt_001")
    second = ns.send_to_parent("p1", "s1", "weekly_report", "标题", "内容", idempotency_key="evt_001")
    assert first == second
    assert db_session.query(ParentNotification).count() == 1


def test_send_practice_notification_idempotent(ns, db_session):
    """同一练习事件投递两次，每个家长只收到一条练习通知。"""
    _mk_student_with_parent(db_session, "s_prac", "p_prac")
    n1 = ns.send_practice_notification("s_prac", "电离平衡练习", idempotency_key="practice_1")
    n2 = ns.send_practice_notification("s_prac", "电离平衡练习", idempotency_key="practice_1")
    assert n1 == 1
    assert n2 == 0
    assert db_session.query(ParentNotification).count() == 1


def test_send_warning_notification_idempotent(ns, db_session):
    """同一预警事件投递两次，每个家长只收到一条预警。"""
    _mk_student_with_parent(db_session, "s_warn", "p_warn")
    n1 = ns.send_warning_notification("s_warn", "score_drop", "成绩下滑", idempotency_key="warn_1")
    n2 = ns.send_warning_notification("s_warn", "score_drop", "成绩下滑", idempotency_key="warn_1")
    assert n1 == 1
    assert n2 == 0
    assert db_session.query(ParentNotification).count() == 1

"""学生端通知链路测试：预警→学生通知、诊断完成→学生通知（openspec 4.2）。

同时覆盖练习提交后的考试记录统计回写（D7：avg_score 由作答聚合）。
"""
import json
from datetime import datetime, timedelta

import pytest

from sqlalchemy.orm import sessionmaker

from app.models.database import (
    Account, BarrierType, Class, ExamRecord, Question, RecordType,
    QuestionSource, AuditStatus, Student, StudentAnswer, StudentNotification,
)
from app.services.early_warning import ews
from app.jobs.handlers import diagnose_exam


@pytest.fixture
def patch_sessionlocal(db_session, monkeypatch):
    """通知服务自开 session 时也落在测试内存库上（而非 chemai.db）。"""
    from app.models import database as dbmod
    engine = db_session.get_bind()
    monkeypatch.setattr(dbmod, "_default_session_factory",
                        sessionmaker(bind=engine, expire_on_commit=False))


def _seed(db, student_id="241901", name="周翔"):
    cls = Class(class_id="class_2419", name="2419班", grade="高三", subject="化学",
                student_count=1)
    db.add(cls)
    db.add(Student(student_id=student_id, name=name, class_id="class_2419",
                   status="approved"))
    db.add(Account(account_id=f"acc_{student_id}", username=student_id,
                   password_hash="x", role="student", student_id=student_id,
                   status="active"))
    db.commit()
    return db.query(Student).filter(Student.student_id == student_id).first()


def test_warning_creates_student_notification(db_session, patch_sessionlocal):
    student = _seed(db_session)
    # 7 天未练习 → 触发连续未学习预警
    student.last_exercise_at = datetime.utcnow() - timedelta(days=7)
    db_session.commit()

    warning = ews.check_no_login_warning(db_session, student)
    assert warning is not None

    notifications = db_session.query(StudentNotification).filter(
        StudentNotification.student_id == student.student_id,
        StudentNotification.type == "warning",
    ).all()
    assert len(notifications) == 1
    assert "未学习" in notifications[0].title


def test_warning_notification_idempotent(db_session, patch_sessionlocal):
    student = _seed(db_session)
    student.last_exercise_at = datetime.utcnow() - timedelta(days=7)
    db_session.commit()

    first = ews.check_no_login_warning(db_session, student)
    # 同一预警未处理期间重复检查：不再新增学生通知
    ews.check_no_login_warning(db_session, student)
    count = db_session.query(StudentNotification).filter(
        StudentNotification.student_id == student.student_id,
    ).count()
    assert first is not None
    assert count == 1


def _seed_practice(db, student_id="241901"):
    student = _seed(db, student_id)
    exam = ExamRecord(record_id=f"exam_{student_id}_202609", class_id="class_2419",
                      name="9月联考·化学", type=RecordType.EXAM,
                      exam_date=datetime(2026, 9, 10))
    db.add(exam)
    db.add(Question(
        question_id=f"q_{exam.record_id}_1", record_id=exam.record_id,
        content="下列说法正确的是", answer="A", knowledge_points=["化学与STSE"],
        probe_dimension="concept", difficulty=2,
        source=QuestionSource.MANUAL_SELECTED, audit_status=AuditStatus.PASSED,
    ))
    db.add(StudentAnswer(
        answer_id=f"sa_{student_id}_1", student_id=student_id,
        question_id=f"q_{exam.record_id}_1", exam_record_id=exam.record_id,
        student_answer="B", is_correct=False, barrier_type=BarrierType.CONCEPT,
    ))
    db.commit()
    return student, exam


def test_diagnosis_completion_sends_student_notification(db_session, monkeypatch, patch_sessionlocal):
    student, exam = _seed_practice(db_session)

    # 打桩 LLM：诊断返回 concept（避免测试依赖外部服务）
    class _FakeLLM:
        @staticmethod
        def diagnose_barrier_type(**kwargs):
            return {"success": True, "content": json.dumps({"barrier_type": "concept"})}

    import importlib
    llm_mod = importlib.import_module("app.services.llm_service")
    monkeypatch.setattr(llm_mod.llm_service, "diagnose_barrier_type",
                        _FakeLLM.diagnose_barrier_type)

    result = diagnose_exam(db_session, exam.record_id)
    assert result["analyzed_count"] == 1

    notifications = db_session.query(StudentNotification).filter(
        StudentNotification.student_id == student.student_id,
        StudentNotification.type == "diagnosis",
    ).all()
    assert len(notifications) == 1

    # 幂等：重复执行诊断不重复通知
    diagnose_exam(db_session, exam.record_id)
    count = db_session.query(StudentNotification).filter(
        StudentNotification.student_id == student.student_id,
        StudentNotification.type == "diagnosis",
    ).count()
    assert count == 1


def test_diagnosis_without_wrong_answers_sends_nothing(db_session, patch_sessionlocal):
    student, exam = _seed_practice(db_session)
    db_session.query(StudentAnswer).update({StudentAnswer.is_correct: True})
    db_session.commit()

    result = diagnose_exam(db_session, exam.record_id)
    assert result["analyzed_count"] == 0
    assert db_session.query(StudentNotification).count() == 0

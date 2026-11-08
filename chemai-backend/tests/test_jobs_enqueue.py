"""入队面（enqueue_job）测试：eager 模式验证投递→任务→处理器；broker 不可达验证降级同步执行。"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.database import Base, Student, ExamRecord, Question, StudentAnswer


def _fake_barrier(*args, **kwargs):
    return {"success": True, "content": '{"barrier_type": "concept"}'}


def _seed_diagnosis(tmp_path):
    """造一份含一道错题的考试数据，返回 Session 工厂。"""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    seed = Session()
    seed.add(Student(student_id="s1", name="张三", class_id="c1", status="approved"))
    seed.add(ExamRecord(record_id="exam_1", class_id="c1", name="月考"))
    seed.add(Question(question_id="q1", content="题目", answer="答案"))
    seed.add(StudentAnswer(
        answer_id="ans_1", student_id="s1", question_id="q1",
        exam_record_id="exam_1", is_correct=False, student_answer="错误作答",
    ))
    seed.commit()
    seed.close()
    return Session


def _mock_deps(monkeypatch, Session):
    def fake_get_db():
        yield Session()

    monkeypatch.setattr("app.jobs.handlers.get_db", fake_get_db)
    from app.services.llm_service import LLMService
    monkeypatch.setattr(LLMService, "diagnose_barrier_type", _fake_barrier)


def _assert_diagnosed(Session):
    check = Session()
    try:
        student = check.query(Student).filter_by(student_id="s1").one()
        assert student.barrier_type == {"concept": 1.0, "reading": 0.0, "expression": 0.0}
    finally:
        check.close()


def test_enqueue_diagnosis_runs_in_eager_mode(monkeypatch, tmp_path):
    from app.jobs.celery_app import celery_app
    monkeypatch.setattr(celery_app.conf, "task_always_eager", True)
    monkeypatch.setattr(celery_app.conf, "task_eager_propagates", True)

    Session = _seed_diagnosis(tmp_path)
    _mock_deps(monkeypatch, Session)

    from app.jobs import enqueue_job
    enqueue_job("diagnosis", {"exam_record_id": "exam_1"})

    _assert_diagnosed(Session)


def test_enqueue_falls_back_when_broker_unreachable(monkeypatch, tmp_path):
    """broker（Redis）不可达时，enqueue_job 降级为同步执行，不拖垮请求。"""
    import kombu.exceptions
    from app.jobs.tasks import diagnosis_task

    def fake_delay(exam_record_id):
        raise kombu.exceptions.OperationalError("cannot connect to redis")

    monkeypatch.setattr(diagnosis_task, "delay", fake_delay)

    Session = _seed_diagnosis(tmp_path)
    _mock_deps(monkeypatch, Session)

    from app.jobs import enqueue_job
    enqueue_job("diagnosis", {"exam_record_id": "exam_1"})

    _assert_diagnosed(Session)


def test_enqueue_unknown_job_type_raises():
    from app.jobs import enqueue_job
    with pytest.raises(ValueError):
        enqueue_job("no_such_job", {})


def test_diagnosis_student_defers_to_background_thread(monkeypatch):
    """broker 不可达时学生级诊断不在请求线程里跑 LLM（ADR-0013），交后台线程补跑。"""
    import threading
    import time

    import kombu.exceptions
    from app.jobs.tasks import diagnosis_student_task

    def fake_delay(student_id):
        raise kombu.exceptions.OperationalError("cannot connect to redis")

    monkeypatch.setattr(diagnosis_student_task, "delay", fake_delay)

    seen = {}

    def fake_handle(student_id):
        seen["thread"] = threading.current_thread()
        seen["student_id"] = student_id
        return {"ok": True}

    monkeypatch.setattr("app.jobs.handlers.handle_diagnosis_student", fake_handle)

    from app.jobs import enqueue_job
    out = enqueue_job("diagnosis_student", {"student_id": "s1"})
    assert out.get("deferred") == "thread"

    for _ in range(100):
        if "thread" in seen:
            break
        time.sleep(0.02)
    assert seen.get("student_id") == "s1"
    assert seen["thread"] is not threading.main_thread()

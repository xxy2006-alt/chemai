"""诊断作业 handler 幂等测试。

打在「作业调度边界」的处理器面：直接同步调用 handle_diagnosis，
不碰队列/线程。用文件型 SQLite 保证跨会话持久。
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.database import Base, Student, ExamRecord, Question, StudentAnswer


def _fake_barrier(*args, **kwargs):
    return {"success": True, "content": '{"barrier_type": "concept"}'}


def test_diagnosis_job_is_idempotent(monkeypatch, tmp_path):
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

    def fake_get_db():
        yield Session()

    monkeypatch.setattr("app.jobs.handlers.get_db", fake_get_db)
    from app.services.llm_service import LLMService
    monkeypatch.setattr(LLMService, "diagnose_barrier_type", _fake_barrier)

    from app.jobs.handlers import handle_diagnosis

    first = handle_diagnosis("exam_1")
    second = handle_diagnosis("exam_1")

    assert first["analyzed_count"] == 1
    assert second["analyzed_count"] == 1

    check = Session()
    try:
        # 幂等：不会重复插入答案
        assert check.query(StudentAnswer).count() == 1
        # 聚合从头重算，重复执行不漂移
        student = check.query(Student).filter_by(student_id="s1").one()
        assert student.barrier_type == {"concept": 1.0, "reading": 0.0, "expression": 0.0}
    finally:
        check.close()

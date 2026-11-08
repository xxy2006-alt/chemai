"""Test save_grading_results contract: real ExamRecord + Question linking, counting, idempotency."""
import asyncio
import json
import pytest


def _build_exam(db_session, exam_id="exam_save_001"):
    from app.models.database import (
        ExamRecord, RecordType, Question, Difficulty, QuestionSource, AuditStatus,
    )
    db_session.add(ExamRecord(
        record_id=exam_id, class_id="c1", name="测试考试",
        type=RecordType.EXAM, total_students=1, present_students=1,
    ))
    db_session.add(Question(
        question_id=f"{exam_id}_1", record_id=exam_id,
        content="题目1", answer="B", knowledge_points=["电解质"],
        difficulty=Difficulty.MEDIUM, source=QuestionSource.MANUAL_SELECTED,
        audit_status=AuditStatus.PASSED,
    ))
    db_session.commit()


def _make_task(task_id="ocr_save_1", sid="202610101", student_name="张三",
               q_numbers=(1,), is_correct=(True,)):
    from app.models.ocr_task import OCRTask
    from datetime import datetime
    return OCRTask(
        task_id=task_id, teacher_id="t1", batch_id="b1",
        image_path="/data/x.jpg", status="done",
        student_id=sid, student_name=student_name,
        grading_result={"questions": [
            {"q_number": q, "student_answer": "B", "correct_answer": "B", "is_correct": c}
            for q, c in zip(q_numbers, is_correct)
        ]},
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def grading_db(db_session, monkeypatch):
    """Point save_grading_results' get_db at the in-memory fixture session and stub diagnosis."""
    def _gen():
        yield db_session
    monkeypatch.setattr("app.models.database.get_db", _gen)

    async def _noop_diagnosis(exam_record_id, db):
        return None
    monkeypatch.setattr("app.api.diagnosis.run_llm_barrier_diagnosis", _noop_diagnosis)
    return db_session


def _save(batch_id="b1", exam_id="exam_save_001"):
    from agent.tools.ocr_grading import save_grading_results
    return json.loads(asyncio.run(
        save_grading_results(teacher_id="t1", batch_id=batch_id, exam_id=exam_id)
    ))


class TestGradeAnswerSheets:
    def _run(self, batch_id="b1", exam_id="", correct_answers=""):
        from agent.tools.ocr_grading import grade_answer_sheets
        return json.loads(asyncio.run(
            grade_answer_sheets(teacher_id="t1", batch_id=batch_id,
                                exam_id=exam_id, correct_answers=correct_answers)
        ))

    def test_missing_answer_source_returns_error_not_crash(self, grading_db, db_session):
        """无答案来源时逐卡返回可读错误，summary 构建不崩溃。"""
        from app.models.ocr_task import OCRTask
        from datetime import datetime
        db_session.add(OCRTask(
            task_id="ocr_no_src", teacher_id="t1", batch_id="b1",
            image_path="/data/x.jpg", status="done",
            student_id="202610101", student_name="张三",
            ocr_result={"answers": [{"q_number": 1, "answer": "B"}]},
            created_at=datetime.utcnow(),
        ))
        db_session.commit()

        out = self._run()
        assert "批改完成" in out["message"]
        assert len(out["results"]) == 1
        assert "缺少正确答案" in out["results"][0]["error"]

    def test_teacher_answers_json_parse_error(self, grading_db, db_session):
        """correct_answers 不是合法 JSON 时返回可读错误。"""
        from app.models.ocr_task import OCRTask
        from datetime import datetime
        db_session.add(OCRTask(
            task_id="ocr_bad_json", teacher_id="t1", batch_id="b1",
            image_path="/data/x.jpg", status="done",
            student_id="202610101", student_name="张三",
            ocr_result={"answers": [{"q_number": 1, "answer": "B"}]},
            created_at=datetime.utcnow(),
        ))
        db_session.commit()
        out = self._run(correct_answers="not-json")
        assert "不是合法 JSON" in out["error"]


class TestSaveGradingResults:
    def test_missing_exam_id(self, grading_db):
        out = _save(exam_id="")
        assert "缺少 exam_id" in out["error"]

    def test_exam_not_found(self, grading_db):
        out = _save(exam_id="exam_not_exist")
        assert "考试记录不存在" in out["error"]

    def test_save_with_real_contract(self, grading_db, db_session):
        """写入的行必须指向真实 ExamRecord 与 Question，不再伪造 ID。"""
        from app.models.database import Student, StudentAnswer, ExamRecord, Question
        _build_exam(db_session)
        db_session.add(Student(student_id="202610101", name="张三", class_id="c1", status="approved"))
        db_session.add(_make_task())
        db_session.commit()

        out = _save()
        assert out["saved_count"] == 1
        assert out["skipped_no_student"] == 0
        assert out["question_missing"] == 0

        ans = db_session.query(StudentAnswer).filter(
            StudentAnswer.exam_record_id == "exam_save_001",
            StudentAnswer.student_id == "202610101").first()
        assert ans is not None
        assert ans.exam_record_id == "exam_save_001"          # 真实考试
        assert ans.question_id == "exam_save_001_1"           # 真实题目
        assert db_session.query(Question).filter(Question.question_id == ans.question_id).first() is not None
        assert db_session.query(ExamRecord).filter(ExamRecord.record_id == ans.exam_record_id).first() is not None
        # exercises_completed 每题 +1
        assert db_session.query(Student).filter(Student.student_id == "202610101").first().exercises_completed == 1

    def test_student_mismatch_counted_not_silent(self, grading_db, db_session):
        """学生学号与 roster 不匹配时计数返回，而不是静默 "已保存 0 位"。"""
        from app.models.database import Student
        _build_exam(db_session)
        db_session.add(Student(student_id="202610101", name="张三", class_id="c1", status="approved"))
        # 学生学号是 API 生成的 student_<ts>，与 OCR 数字学号不匹配
        db_session.add(_make_task(sid="202699999"))
        db_session.commit()

        out = _save()
        assert out["saved_count"] == 0
        assert out["skipped_no_student"] == 1
        assert any("学生不存在" in d.get("reason", "") for d in out["details"])

    def test_question_missing_counted(self, grading_db, db_session):
        """grading 引用了不存在的题号时计数，不写伪造 question_id。"""
        from app.models.database import StudentAnswer, Student
        _build_exam(db_session)
        db_session.add(Student(student_id="202610101", name="张三", class_id="c1", status="approved"))
        db_session.add(_make_task(q_numbers=(1, 2), is_correct=(True, False)))  # 题2不存在
        db_session.commit()

        out = _save()
        assert out["saved_count"] == 1
        assert out["question_missing"] == 1
        # 题2 没有被写入
        assert db_session.query(StudentAnswer).filter(StudentAnswer.answer_id == "ocr_ocr_save_1_2").first() is None

    def test_idempotent_resave(self, grading_db, db_session):
        """重复保存同一 batch：answer_id 已存在则跳过，exercises_completed 不重复累加。"""
        from app.models.database import Student, StudentAnswer
        _build_exam(db_session)
        db_session.add(Student(student_id="202610101", name="张三", class_id="c1", status="approved"))
        db_session.add(_make_task())
        db_session.commit()

        first = _save()
        second = _save()
        assert first["saved_count"] == 1
        assert second["saved_count"] == 0
        assert second["skipped_duplicate"] == 1
        # 重复保存不重复累加
        assert db_session.query(Student).filter(Student.student_id == "202610101").first().exercises_completed == 1
        assert db_session.query(StudentAnswer).count() == 1


@pytest.fixture(autouse=True)
def as_teacher_t1(db_session):
    """判卷工具的身份取服务端上下文：本文件统一以 t1（任教 c1）的会话执行。"""
    from agent.tools.context import set_current_teacher
    from app.models.database import Account, TeacherClassSubject

    db_session.add(Account(account_id="acc_t1", username="t1_user", role="teacher",
                           teacher_id="t1", password_hash="x"))
    db_session.add(TeacherClassSubject(id="tcs_scope", teacher_id="t1",
                                       class_id="c1", subject="化学"))
    db_session.commit()
    set_current_teacher("t1")
    yield
    set_current_teacher("")

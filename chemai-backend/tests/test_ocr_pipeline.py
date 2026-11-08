"""Test OCR task pipeline: task creation, status transitions, teacher isolation, retry."""
import pytest
from datetime import datetime


@pytest.fixture
def sample_task(db_session):
    from app.models.ocr_task import OCRTask
    task = OCRTask(
        task_id="ocr_test_001", teacher_id="teacher_test", batch_id="batch_test_01",
        image_path="/data/answer_sheets/test.jpg", title="答题卡_01",
        created_at=datetime.utcnow(),
    )
    db_session.add(task)
    db_session.commit()
    return task


class TestOCRTaskModel:
    def test_default_status_is_pending(self, sample_task):
        assert sample_task.status == "pending"
        assert sample_task.progress == 0
        assert sample_task.confirmed == False

    def test_status_transition(self, db_session, sample_task):
        sample_task.status = "processing"
        sample_task.progress = 30
        db_session.commit()
        assert sample_task.status == "processing"
        assert sample_task.progress == 30

    def test_complete_transition(self, db_session, sample_task):
        sample_task.status = "done"
        sample_task.progress = 100
        sample_task.student_id = "202610101"
        sample_task.student_name = "test"
        sample_task.ocr_result = {"answers": [{"q_number": 1, "answer": "B"}]}
        db_session.commit()
        assert sample_task.ocr_result["answers"][0]["answer"] == "B"


class TestTeacherIsolation:
    def test_different_teachers_independent(self, db_session):
        from app.models.ocr_task import OCRTask
        t1 = OCRTask(task_id="t1", teacher_id="teacher_A", batch_id="b1",
                     image_path="/data/a.jpg", created_at=datetime.utcnow())
        t2 = OCRTask(task_id="t2", teacher_id="teacher_B", batch_id="b2",
                     image_path="/data/b.jpg", created_at=datetime.utcnow())
        db_session.add_all([t1, t2])
        db_session.commit()

        a_tasks = db_session.query(OCRTask).filter(OCRTask.teacher_id == "teacher_A").all()
        b_tasks = db_session.query(OCRTask).filter(OCRTask.teacher_id == "teacher_B").all()
        assert len(a_tasks) == 1
        assert len(b_tasks) == 1
        assert a_tasks[0].teacher_id != b_tasks[0].teacher_id


class TestRetry:
    def test_retry_resets_status(self, db_session, sample_task):
        sample_task.status = "failed"
        sample_task.error_message = "OCR error"
        db_session.commit()

        sample_task.status = "pending"
        sample_task.progress = 0
        sample_task.error_message = ""
        db_session.commit()

        assert sample_task.status == "pending"
        assert sample_task.error_message == ""

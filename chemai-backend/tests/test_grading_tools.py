"""判卷中心 Agent 工具薄壳测试 — 只测「转发正确 + 返回 JSON 形状」。

业务逻辑在 app/services/grading_center 已覆盖（test_grading_center.py）；
这里验证工具层不持有业务逻辑、正确委托 service（ADR-0012）。
"""
import json
from datetime import datetime

import pytest

from agent.tools.ocr_grading import query_grading_queue, save_grading_results


@pytest.fixture(autouse=True)
def as_teacher_t1(db_session):
    """判卷工具的身份取服务端上下文：本文件统一以 t1（任教 class_2025_1）的会话执行。"""
    from agent.tools.context import set_current_teacher
    from app.models.database import Account, TeacherClassSubject

    db_session.add(Account(account_id="acc_t1", username="t1_user", role="teacher",
                           teacher_id="t1", password_hash="x"))
    db_session.add(TeacherClassSubject(id="tcs_scope", teacher_id="t1",
                                       class_id="class_2025_1", subject="化学"))
    db_session.commit()
    set_current_teacher("t1")
    yield
    set_current_teacher("")


@pytest.fixture
def ocr_exam(db_session):
    from app.models.database import (
        ExamRecord, Question, RecordType, Difficulty, QuestionSource, AuditStatus, Student,
    )
    from app.models.ocr_task import OCRTask

    db_session.add(Student(student_id="202610101", name="李雨萱", class_id="class_2025_1"))
    db_session.add(ExamRecord(
        record_id="tool_exam_1", class_id="class_2025_1", name="工具薄壳卷",
        type=RecordType.EXAM, total_students=1, present_students=1,
        exam_date=datetime.utcnow(),
    ))
    db_session.add(Question(
        question_id="tool_exam_1_1", record_id="tool_exam_1", content="题1",
        options=["A", "B", "C", "D"], answer="B", analysis="",
        knowledge_points=[], difficulty=Difficulty.MEDIUM,
        source=QuestionSource.MANUAL_SELECTED, audit_status=AuditStatus.PASSED,
    ))
    db_session.add(OCRTask(
        task_id="ocr_tool_t1", teacher_id="t1", batch_id="tool_batch_1",
        image_path="/tmp/t.jpg", title="薄壳测试卡",
        student_id="202610101", student_name="李雨萱", status="done",
        ocr_result={"answers": [{"q_number": 1, "answer": "B"}]},
        grading_result={"questions": [
            {"q_number": 1, "student_answer": "B", "is_correct": True},
        ]},
    ))
    db_session.commit()
    return db_session


@pytest.mark.asyncio
async def test_save_tool_delegates_and_reports(ocr_exam, monkeypatch):
    monkeypatch.setattr("app.models.database.get_db", lambda: iter([ocr_exam]))

    out = json.loads(await save_grading_results(
        teacher_id="t1", batch_id="tool_batch_1", exam_id="tool_exam_1",
    ))

    assert out["saved_count"] == 1
    assert out["diagnosis"] in ("已触发", "触发失败: ", "未触发") or out["diagnosis"]
    assert "details" in out


@pytest.mark.asyncio
async def test_save_tool_missing_exam_error(ocr_exam, monkeypatch):
    monkeypatch.setattr("app.models.database.get_db", lambda: iter([ocr_exam]))

    out = json.loads(await save_grading_results(
        teacher_id="t1", batch_id="tool_batch_1", exam_id="ghost_exam",
    ))
    assert "error" in out


@pytest.mark.asyncio
async def test_queue_tool_lists_pending_batch(ocr_exam, monkeypatch):
    """已批改未确认的批次出现在待确认队列。"""
    monkeypatch.setattr("app.models.database.get_db", lambda: iter([ocr_exam]))

    out = json.loads(await query_grading_queue(teacher_id="t1"))

    assert out["pending_confirm"], "tool_batch_1 已批改未确认，应在队列"
    assert out["pending_confirm"][0]["batch_id"] == "tool_batch_1"
    assert "_route" in out

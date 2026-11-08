"""Agent 判卷工具的班级范围（ADR-0010 第二层权限）：身份取 token，不看模型传参。

query_grading_queue / confirm_exam_grades 决定「哪些成绩能被看到、能被生效」，
必须与 HTTP 侧同一口径收窄；学生 token（persona 由请求体自报）一律拿不到范围。
"""
import json
from datetime import datetime

import pytest

from agent.tools.context import set_current_teacher
from agent.tools.ocr_grading import confirm_exam_grades, query_grading_queue


@pytest.fixture
def seeded(db_session):
    from app.models.database import (
        Account, AnswerSource, AuditStatus, Class, Difficulty, ExamRecord, Grade,
        Question, QuestionSource, RecordType, School, Student, StudentAnswer,
        TeacherClassSubject,
    )

    db_session.add(School(school_id="sch1", name="测试中学"))
    db_session.add(Grade(grade_id="g1", school_id="sch1", name="高一", year=2026))
    db_session.add(Class(class_id="class_2025_1", name="一班", grade="高一",
                         grade_id="g1", subject="化学"))
    db_session.add(Student(student_id="202610101", name="李雨萱", class_id="class_2025_1"))
    db_session.add(Student(student_id="202610909", name="别班同学", class_id="c_other"))
    db_session.add(ExamRecord(record_id="ex_mine", class_id="class_2025_1", name="本班考试",
                              type=RecordType.PRACTICE, exam_date=datetime.utcnow()))
    db_session.add(ExamRecord(record_id="ex_other", class_id="c_other", name="别班考试",
                              type=RecordType.PRACTICE, exam_date=datetime.utcnow()))
    for qid, rec in (("q_mine", "ex_mine"), ("q_other", "ex_other")):
        db_session.add(Question(
            question_id=qid, record_id=rec, content="题", answer="A", options=None,
            analysis="", knowledge_points=[], difficulty=Difficulty.MEDIUM,
            source=QuestionSource.MANUAL_SELECTED, audit_status=AuditStatus.PASSED))
    for aid, sid, qid, rec in (("ans_mine", "202610101", "q_mine", "ex_mine"),
                               ("ans_other", "202610909", "q_other", "ex_other")):
        db_session.add(StudentAnswer(
            answer_id=aid, student_id=sid, question_id=qid, exam_record_id=rec,
            student_answer="B", is_correct=False, confirmed=False, source=AnswerSource.ONLINE))

    # T_chem 教 class_2025_1；学生账户用来验证「自报 persona 也拿不到范围」
    db_session.add(TeacherClassSubject(id="tcs_chem", teacher_id="T_chem",
                                       class_id="class_2025_1", subject="化学"))
    db_session.add(Account(account_id="acc_chem", username="chem", role="teacher",
                           teacher_id="T_chem", password_hash="x"))
    db_session.add(Account(account_id="acc_stu", username="stu", role="student",
                           student_id="202610101", password_hash="x"))

    # 答题卡批次：T_chem 自己的一批 + 别班老师的一批（批改/保存/查成绩都要挡住后者）
    from app.models.ocr_task import OCRTask
    db_session.add(Question(
        question_id="ex_mine_1", record_id="ex_mine", content="题1", answer="A",
        options=["A", "B"], analysis="", knowledge_points=[],
        difficulty=Difficulty.MEDIUM, source=QuestionSource.MANUAL_SELECTED,
        audit_status=AuditStatus.PASSED))
    db_session.add(OCRTask(
        task_id="t_mine", teacher_id="T_chem", batch_id="b_mine", title="我的卡",
        image_path="/tmp/m.jpg", student_id="202610101", student_name="李雨萱",
        status="done", ocr_result={"answers": [{"q_number": 1, "answer": "B"}]},
        grading_result={"questions": [{"q_number": 1, "student_answer": "B", "is_correct": False}]},
    ))
    db_session.add(OCRTask(
        task_id="t_other", teacher_id="T_other", batch_id="b_other", title="别班的卡",
        image_path="/tmp/o.jpg", student_id="202610909", student_name="别班同学",
        status="done", ocr_result={"answers": [{"q_number": 1, "answer": "B"}]},
        grading_result={"questions": [{"q_number": 1, "student_answer": "B", "is_correct": False}]},
    ))
    db_session.commit()
    return db_session


@pytest.fixture
def wired(seeded, monkeypatch):
    import app.models.database as db_mod
    monkeypatch.setattr(db_mod, "get_db", lambda: iter([seeded]))
    monkeypatch.setattr("app.jobs.enqueue_job", lambda t, p: None)
    yield seeded
    set_current_teacher("")


@pytest.mark.asyncio
async def test_queue_only_lists_own_class_exams(wired):
    set_current_teacher("T_chem")
    out = json.loads(await query_grading_queue())
    assert [e["exam_record_id"] for e in out["unconfirmed_exams"]] == ["ex_mine"]


@pytest.mark.asyncio
async def test_confirm_own_class_exam(wired):
    set_current_teacher("T_chem")
    out = json.loads(await confirm_exam_grades("ex_mine"))
    assert out["confirmed"] == 1


@pytest.mark.asyncio
async def test_confirm_other_class_exam_denied(wired):
    from app.models.database import StudentAnswer

    set_current_teacher("T_chem")
    out = json.loads(await confirm_exam_grades("ex_other"))
    assert "无权" in out["error"]
    assert wired.query(StudentAnswer).filter_by(answer_id="ans_other").one().confirmed is False


@pytest.mark.asyncio
async def test_student_token_gets_no_scope(wired):
    """persona 由请求体自报，身份不能：学生身份确认不了任何成绩。"""
    from app.models.database import StudentAnswer

    set_current_teacher("202610101")
    out = json.loads(await confirm_exam_grades("ex_mine"))
    assert "无权" in out["error"]
    assert wired.query(StudentAnswer).filter_by(answer_id="ans_mine").one().confirmed is False


@pytest.mark.asyncio
async def test_model_supplied_teacher_id_is_not_trusted(wired):
    """模型传参不采信：换个 teacher_id 参数也只看 token 身份的范围。"""
    set_current_teacher("T_nobody")
    out = json.loads(await query_grading_queue(teacher_id="T_chem"))
    assert out["unconfirmed_exams"] == []


# ── OCR 判卷写/读侧：同一失败链的其余 adapter（批次归属 + 考试班级）──

@pytest.mark.asyncio
async def test_ocr_progress_lists_only_own_batches(wired):
    from agent.tools.ocr_grading import query_ocr_progress
    set_current_teacher("T_chem")
    out = json.loads(await query_ocr_progress())
    assert set(out["batches"]) == {"b_mine"}


@pytest.mark.asyncio
async def test_ocr_progress_rejects_other_batch(wired):
    from agent.tools.ocr_grading import query_ocr_progress
    set_current_teacher("T_chem")
    out = json.loads(await query_ocr_progress(batch_id="b_other"))
    assert "无权" in out["error"]


@pytest.mark.asyncio
async def test_batch_grades_rejects_other_batch(wired):
    from agent.tools.ocr_grading import query_batch_grades
    set_current_teacher("T_chem")
    out = json.loads(await query_batch_grades(batch_id="b_other"))
    assert "无权" in out["error"]


@pytest.mark.asyncio
async def test_batch_grades_rejects_other_class_exam(wired):
    from agent.tools.ocr_grading import query_batch_grades
    set_current_teacher("T_chem")
    out = json.loads(await query_batch_grades(exam_id="ex_other"))
    assert "无权" in out["error"]


@pytest.mark.asyncio
async def test_batch_grades_reads_own_batch(wired):
    from agent.tools.ocr_grading import query_batch_grades
    set_current_teacher("T_chem")
    out = json.loads(await query_batch_grades(batch_id="b_mine"))
    assert out["saved"] is False and len(out["results"]) == 1


@pytest.mark.asyncio
async def test_grade_answer_sheets_rejects_other_batch(wired):
    from agent.tools.ocr_grading import grade_answer_sheets
    set_current_teacher("T_chem")
    out = json.loads(await grade_answer_sheets(batch_id="b_other", exam_id="ex_other"))
    assert "无权" in out["error"]


@pytest.mark.asyncio
async def test_grade_answer_sheets_refuses_other_class_exam_as_key_source(wired):
    from agent.tools.ocr_grading import grade_answer_sheets
    set_current_teacher("T_chem")
    out = json.loads(await grade_answer_sheets(batch_id="b_mine", exam_id="ex_other"))
    assert "无权" in out["error"]


@pytest.mark.asyncio
async def test_save_grading_results_rejects_other_batch(wired):
    from agent.tools.ocr_grading import save_grading_results
    set_current_teacher("T_chem")
    out = json.loads(await save_grading_results(batch_id="b_other", exam_id="ex_mine"))
    assert "无权" in out["error"]


@pytest.mark.asyncio
async def test_save_grading_results_rejects_other_class_exam(wired):
    from app.models.database import StudentAnswer
    from agent.tools.ocr_grading import save_grading_results
    before = wired.query(StudentAnswer).filter_by(exam_record_id="ex_other").count()
    set_current_teacher("T_chem")
    out = json.loads(await save_grading_results(batch_id="b_mine", exam_id="ex_other"))
    assert "无权" in out["error"]
    assert wired.query(StudentAnswer).filter_by(exam_record_id="ex_other").count() == before


@pytest.mark.asyncio
async def test_list_teacher_exams_uses_token_scope(wired):
    """模型传 teacher_id 无效：列出的只能是 token 持有者范围里的班。"""
    from agent.tools.ocr_grading import list_teacher_exams
    set_current_teacher("T_chem")
    out = json.loads(await list_teacher_exams(teacher_id="T_other"))
    assert [c["class_id"] for c in out["classes"]] == ["class_2025_1"]
    assert [e["record_id"] for c in out["classes"] for e in c["exams"]] == ["ex_mine"]


@pytest.mark.asyncio
async def test_student_identity_denied_across_grading_tools(wired):
    """学生身份（persona 自报）在整条判卷链上都拿不到东西。"""
    from agent.tools.ocr_grading import (
        grade_answer_sheets, list_teacher_exams, query_batch_grades,
        query_ocr_progress, save_grading_results,
    )
    set_current_teacher("202610101")
    assert "error" in json.loads(await query_ocr_progress())
    assert "error" in json.loads(await query_batch_grades(batch_id="b_mine"))
    assert "error" in json.loads(await list_teacher_exams())
    assert "无权" in json.loads(await grade_answer_sheets(batch_id="b_mine", exam_id="ex_mine"))["error"]
    assert "无权" in json.loads(await save_grading_results(batch_id="b_mine", exam_id="ex_mine"))["error"]


@pytest.mark.asyncio
async def test_diagnosis_tools_scope_model_supplied_ids(wired):
    """诊断/报告工具按服务端身份收窄：模型自报的 student_id 越界一律拒绝。"""
    from agent.tools.diagnosis import diagnose_barrier, show_students, weekly_report

    set_current_teacher("T_chem")                 # 教 class_2025_1
    ok = json.loads(await diagnose_barrier(student_id="202610101"))
    assert ok["student_id"] == "202610101"
    assert "无权" in json.loads(await diagnose_barrier(student_id="202610909"))["error"]
    assert "无权" in json.loads(await weekly_report(student_id="202610909"))["error"]

    # 别班学生不出现在姓名搜索结果里（原来按姓名全库搜人）
    found = json.loads(await show_students(student_name="别班同学"))
    assert found.get("student_count", 0) == 0

    set_current_teacher("202610101")              # 学生身份：只能看自己
    assert "无权" in json.loads(await diagnose_barrier(student_id="202610909"))["error"]

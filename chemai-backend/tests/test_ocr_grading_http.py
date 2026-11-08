"""b2/b3 回归测试 — 判分 HTTP 端点 + 标准答案确定性解析 + mimo 语义判分降级链。"""
import asyncio
import json
import pytest
from datetime import datetime

from fastapi import HTTPException

from app.services.llm_grading import parse_correct_answers


class TestParseCorrectAnswers:
    """老师粘贴标准答案的确定性解析（不走 LLM）。"""

    def test_choice_lines(self):
        assert parse_correct_answers("1.A 2.B 3.C") == [
            {"q_number": 1, "answer": "A"},
            {"q_number": 2, "answer": "B"},
            {"q_number": 3, "answer": "C"},
        ]

    def test_mixed_choice_free(self):
        text = ("1.A 2.C\n"
                "13. Cu + 2H2SO4(浓) 加热生成 CuSO4 + SO2气体 + 2H2O\n"
                "14. 化合价升高的是还原剂")
        out = {a["q_number"]: a["answer"] for a in parse_correct_answers(text)}
        assert out[1] == "A"
        assert out[13] == "Cu + 2H2SO4(浓) 加热生成 CuSO4 + SO2气体 + 2H2O"
        assert out[14] == "化合价升高的是还原剂"

    def test_lowercase_choice_uppercased(self):
        assert parse_correct_answers("1.a 2.b")[0]["answer"] == "A"

    def test_choice_glued_no_separator(self):
        assert parse_correct_answers("1A 2B") == [
            {"q_number": 1, "answer": "A"}, {"q_number": 2, "answer": "B"},
        ]

    def test_chemical_numbers_not_confused_with_q(self):
        """化学式里的数字 2（如 2H2）不误判为题号。"""
        out = parse_correct_answers("13. 2H2 + O2 = 2H2O")
        assert [a["q_number"] for a in out] == [13]

    def test_empty_input(self):
        assert parse_correct_answers("") == []
        assert parse_correct_answers("   ") == []


class TestSemanticJudgeFallback:
    def test_mimo_primary_fallback_auto(self, db_session, monkeypatch):
        """语义判定先走 provider=mimo，失败降级 auto（dashscope/deepseek）。"""
        from app.models.ocr_task import OCRTask
        from app.services.llm_grading import grade_batch_answers
        from app.services.llm_service import llm_service

        calls = []
        def fake_generate_text(prompt, **kw):
            calls.append(kw.get("provider"))
            if len(calls) == 1:
                return {"success": False, "error": "mimo 不可用"}
            return {
                "success": True,
                "content": '[{"q": 1, "equivalent": true, "reason": "OCR 0/O 混淆不计错"}]',
            }
        monkeypatch.setattr(llm_service, "generate_text", fake_generate_text)

        task = OCRTask(
            task_id="ocr_fallback", teacher_id="t1", batch_id="b1",
            image_path="/data/x.jpg", status="done",
            ocr_result={"answers": [{"q_number": 1, "answer": "Cu + 2H2S04(浓) 加热生成 CuS04 + S02"}]},
            created_at=datetime.utcnow(),
        )
        db_session.add(task)
        db_session.commit()

        correct = [{"q_number": 1, "answer": "Cu + 2H2SO4(浓) 加热生成 CuSO4 + SO2"}]
        results = grade_batch_answers([task], correct_answers=correct, db=db_session)
        assert calls == ["mimo", "auto"]      # mimo 优先，失败回退 auto
        q1 = results[0]["questions"][0]
        assert q1["is_correct"] is True       # 0/O 混淆语义判对
        assert "LLM 语义判定" in q1["reason"]


@pytest.fixture
def grading_db(db_session, monkeypatch):
    """Point get_db at the in-memory fixture session and stub diagnosis."""
    def _gen():
        yield db_session
    monkeypatch.setattr("app.models.database.get_db", _gen)

    async def _noop_diagnosis(exam_record_id, db):
        return None
    monkeypatch.setattr("app.api.diagnosis.run_llm_barrier_diagnosis", _noop_diagnosis)
    return db_session


@pytest.fixture(autouse=True)
def as_teacher_t1(db_session):
    """判卷工具的身份取服务端上下文：本文件统一以 t1（任教 c1）的会话执行。

    工具不再采信模型/前端自报的 teacher_id，端点也要显式拿 current_user。
    """
    from agent.tools.context import set_current_teacher
    from app.models.database import Account, TeacherClassSubject

    db_session.add(Account(account_id="acc_t1", username="t1_user", role="teacher",
                           teacher_id="t1", password_hash="x"))
    db_session.add(TeacherClassSubject(id="tcs_scope", teacher_id="t1",
                                       class_id="c1", subject="化学"))
    db_session.commit()
    set_current_teacher("t1")
    yield {"role": "teacher", "user_id": "t1", "school_id": None}
    set_current_teacher("")


def _make_done_task(db, task_id, batch_id, sid, name, answers):
    from app.models.ocr_task import OCRTask
    db.add(OCRTask(
        task_id=task_id, teacher_id="t1", batch_id=batch_id,
        image_path="/data/x.jpg", status="done",
        student_id=sid, student_name=name,
        ocr_result={"answers": answers},
        created_at=datetime.utcnow(),
    ))
    db.commit()


class TestGradeEndpoint:
    def test_missing_answer_source_400(self, as_teacher_t1):
        from app.api.ocr_sheets import GradeRequest, grade_batch
        with pytest.raises(HTTPException) as e:
            asyncio.run(grade_batch(GradeRequest(batch_id="b1"),
                                    current_user=as_teacher_t1))
        assert e.value.status_code == 400

    def test_text_answers_grade(self, grading_db, db_session, as_teacher_t1):
        """粘贴文本答案 → 确定性解析 → 逐卡判分（选择题不走 LLM）。"""
        _make_done_task(db_session, "ocr_http_1", "b_http", "202610101", "张三",
                        [{"q_number": 1, "answer": "A"}, {"q_number": 2, "answer": "B"}])
        from app.api.ocr_sheets import GradeRequest, grade_batch

        out = asyncio.run(grade_batch(GradeRequest(
            batch_id="b_http", teacher_id="t1", correct_answers="1.A 2.C"),
            current_user=as_teacher_t1))
        assert out["message"].startswith("批改完成")
        r = out["results"][0]
        assert r["student_name"] == "张三"
        assert r["score"] == 1        # Q1 A✓ Q2 B vs C ✗
        assert r["questions"][0]["is_correct"] is True
        assert r["questions"][1]["is_correct"] is False
        # grading_result 已写回任务供保存
        from app.models.ocr_task import OCRTask
        task = db_session.query(OCRTask).filter(OCRTask.task_id == "ocr_http_1").first()
        assert task.grading_result["score"] == 1

    def test_json_answers_grade(self, grading_db, db_session, as_teacher_t1):
        _make_done_task(db_session, "ocr_http_2", "b_http2", "202610102", "李四",
                        [{"q_number": 1, "answer": "B"}])
        from app.api.ocr_sheets import GradeRequest, grade_batch

        out = asyncio.run(grade_batch(GradeRequest(
            batch_id="b_http2", teacher_id="t1",
            correct_answers=[{"q_number": 1, "answer": "B"}]),
            current_user=as_teacher_t1))
        assert out["results"][0]["score"] == 1


class TestSaveEndpoint:
    def test_missing_exam_id_400(self, grading_db, as_teacher_t1):
        from app.api.ocr_sheets import SaveRequest, save_grading
        with pytest.raises(HTTPException) as e:
            asyncio.run(save_grading(SaveRequest(batch_id="b1", exam_id=""),
                                     current_user=as_teacher_t1))
        assert e.value.status_code == 400
        assert "exam_id" in str(e.value.detail)


class TestGradeToolAcceptsRawText:
    """006 — grade_answer_sheets 工具层内迁答案解析：吃原始文本而非仅 JSON。"""

    def test_raw_text_answers_grade(self, grading_db, db_session):
        """老师贴原始文本（非 JSON）→ 工具内解析 → 判分。"""
        from agent.tools.ocr_grading import grade_answer_sheets
        _make_done_task(db_session, "ocr_tool_raw", "b_tool", "202610103", "王五",
                        [{"q_number": 1, "answer": "A"}, {"q_number": 2, "answer": "B"}])

        out = json.loads(asyncio.run(grade_answer_sheets(
            teacher_id="t1", batch_id="b_tool",
            correct_answers="1.A 2.C")))
        assert out["message"].startswith("批改完成")
        r = out["results"][0]
        assert r["score"] == 1        # Q1 A✓ Q2 B vs C ✗
        assert r["questions"][0]["is_correct"] is True

    def test_raw_text_chemical_free_answer(self, grading_db, db_session):
        """自由作答含 0/O 混淆的原始文本能被解析判分（q13）。"""
        from agent.tools.ocr_grading import grade_answer_sheets
        _make_done_task(db_session, "ocr_tool_free", "b_tool2", "202610104", "赵六",
                        [{"q_number": 13, "answer": "Cu + 2H2S04(浓) 加热生成 CuS04 + S02气体"}])

        out = json.loads(asyncio.run(grade_answer_sheets(
            teacher_id="t1", batch_id="b_tool2",
            correct_answers="13. Cu + 2H2SO4(浓) 加热生成 CuSO4 + SO2气体")))
        assert out["message"].startswith("批改完成")
        r = out["results"][0]
        assert r["questions"][0]["correct_answer"] == "Cu + 2H2SO4(浓) 加热生成 CuSO4 + SO2气体"

    def test_invalid_answers_error(self, grading_db, db_session):
        """既非 JSON 又解析不出题号 → 明确报错，不静默。"""
        from agent.tools.ocr_grading import grade_answer_sheets
        _make_done_task(db_session, "ocr_tool_bad", "b_tool3", "202610105", "孙七",
                        [{"q_number": 1, "answer": "A"}])

        out = json.loads(asyncio.run(grade_answer_sheets(
            teacher_id="t1", batch_id="b_tool3",
            correct_answers="这不是答案")))
        # 解析结果为空 → grade_batch_answers 报"缺少正确答案"
        assert "error" in out or "缺少正确答案" in out.get("message", "")


class TestQueryBatchGrades:
    """007 — query_batch_grades 双入参：batch_id→grading_result，exam_id→StudentAnswer。"""

    def test_batch_id_returns_grading_result(self, grading_db, db_session):
        """传 batch_id → 查该批 OCRTask.grading_result（批改未保存），标注来源。"""
        from agent.tools.ocr_grading import query_batch_grades
        _make_done_task(db_session, "ocr_qb1", "b_q", "202610103", "王五",
                        [{"q_number": 1, "answer": "A"}])
        from app.models.ocr_task import OCRTask
        task = db_session.query(OCRTask).filter(OCRTask.task_id == "ocr_qb1").first()
        task.grading_result = {
            "task_id": "ocr_qb1", "student_id": "202610103", "student_name": "王五",
            "score": 1, "total": 1,
            "questions": [{"q_number": 1, "is_correct": True}],
        }
        db_session.commit()

        out = json.loads(asyncio.run(query_batch_grades(batch_id="b_q")))
        assert "批改结果" in out.get("source", "") or out.get("saved", False) is False
        assert any(r["task_id"] == "ocr_qb1" for r in out.get("results", []))

    def test_exam_id_returns_saved_answers(self, grading_db, db_session):
        """传 exam_id → 查 StudentAnswer（已保存成绩），按学生聚合。"""
        from agent.tools.ocr_grading import query_batch_grades
        from app.models.database import ExamRecord, StudentAnswer, Question

        exam = ExamRecord(record_id="exam_qb", class_id="c1", name="月考", exam_date=datetime.utcnow())
        db_session.add(exam)
        db_session.commit()
        db_session.add(Question(
            question_id="exam_qb_1", content="Q1", answer="A",
        ))
        db_session.commit()
        db_session.add(StudentAnswer(
            answer_id="a1", student_id="202610103", question_id="exam_qb_1",
            exam_record_id="exam_qb", student_answer="A", is_correct=True,
        ))
        db_session.commit()

        out = json.loads(asyncio.run(query_batch_grades(exam_id="exam_qb")))
        assert out.get("saved", False) is True
        assert out["exam_id"] == "exam_qb"
        assert any(r["student_id"] == "202610103" and r["score"] == 1 for r in out.get("results", []))


class TestListTeacherExams:
    """007 — list_teacher_exams 封装老师班级→考试两级查询。"""

    def test_returns_exams_by_class(self, grading_db, db_session):
        from agent.tools.ocr_grading import list_teacher_exams
        from app.models.database import Class, ExamRecord, TeacherClassSubject

        db_session.add(Class(class_id="c1", name="2419班", grade="高三"))
        db_session.commit()
        db_session.add(ExamRecord(record_id="exam_t1", class_id="c1", name="月考", exam_date=datetime.utcnow()))
        db_session.add(ExamRecord(record_id="exam_t2", class_id="c1", name="期中", exam_date=datetime.utcnow()))
        db_session.commit()
        db_session.add(TeacherClassSubject(
            id="tcs1", teacher_id="t1", class_id="c1", subject="化学", is_class_teacher=True,
        ))
        db_session.commit()

        out = json.loads(asyncio.run(list_teacher_exams(teacher_id="t1")))
        assert out.get("total", 0) >= 1
        exam_ids = [e["record_id"] for c in out.get("classes", []) for e in c.get("exams", [])]
        assert "exam_t1" in exam_ids and "exam_t2" in exam_ids

    def test_no_exams_empty_state(self, grading_db, db_session):
        from agent.tools.ocr_grading import list_teacher_exams
        from app.models.database import Class, TeacherClassSubject

        db_session.add(Class(class_id="c2", name="高二(2)班", grade="高二"))
        db_session.commit()
        db_session.add(TeacherClassSubject(
            id="tcs2", teacher_id="t1", class_id="c2", subject="化学", is_class_teacher=False,
        ))
        db_session.commit()

        out = json.loads(asyncio.run(list_teacher_exams(teacher_id="t1")))
        assert out.get("total", 0) == 0
        assert "0 场考试" in out.get("message", "")


class TestPastedChoiceAnswersStayDeterministic:
    """老师粘贴的标准答案没有 options：回退双边形态启发式，字母对字母不当主观题送 LLM。"""

    def test_letter_mismatch_judged_without_llm(self, grading_db, db_session, monkeypatch):
        from app.services.llm_service import llm_service
        from agent.tools.ocr_grading import grade_answer_sheets

        calls = []
        monkeypatch.setattr(llm_service, "generate_text",
                            lambda *a, **k: calls.append(k.get("provider")) or
                            {"success": False, "error": "不该被调用"})
        _make_done_task(db_session, "ocr_choice", "b_choice", "202610101", "张三",
                        [{"q_number": 2, "answer": "B"}])

        out = json.loads(asyncio.run(grade_answer_sheets(
            batch_id="b_choice", correct_answers="2.C")))
        q = out["results"][0]["questions"][0]
        assert q["is_correct"] is False
        assert q["reason"] == "与标准答案不一致"
        assert calls == []

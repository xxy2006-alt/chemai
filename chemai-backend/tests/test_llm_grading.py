"""Test LLM grading: answer comparison, source resolution, result generation."""


class TestAnswerComparison:
    def test_exact_match(self):
        from app.services.llm_grading import _compare_answers
        assert _compare_answers("B", "B") is True
        assert _compare_answers("A", "B") is False

    def test_case_insensitive(self):
        from app.services.llm_grading import _compare_answers
        assert _compare_answers("b", "B") is True
        assert _compare_answers("c", "C") is True

    def test_whitespace_normalized(self):
        from app.services.llm_grading import _compare_answers
        assert _compare_answers(" B ", "B") is True

    def test_empty_handling(self):
        from app.services.llm_grading import _compare_answers
        assert _compare_answers("", "B") is False
        assert _compare_answers("A", "") is False

    def test_chemical_formula_normalization(self):
        """LaTeX/unicode/纯文本三种化学式形态归一后应相等。"""
        from app.services.llm_grading import _compare_answers
        assert _compare_answers("H_{2}O", "H2O") is True
        assert _compare_answers("CaCO_{3}", "CaCO3") is True
        assert _compare_answers("Fe^{3+}", "Fe3+") is True
        assert _compare_answers("2H_{2}+O_{2}", "2H2 + O2") is True

    def test_choice_vs_non_choice(self):
        from app.services.llm_grading import _is_choice
        assert _is_choice("B") is True
        assert _is_choice("AB") is True
        assert _is_choice("CaCO3") is False
        assert _is_choice("2H2+O2=2H2O") is False
        assert _is_choice("") is False


class TestGradingPipeline:
    def test_grade_batch_with_answers(self, db_session):
        from app.models.ocr_task import OCRTask
        from app.services.llm_grading import grade_batch_answers
        from datetime import datetime
        task = OCRTask(
            task_id="ocr_grade_test", teacher_id="t1", batch_id="b1",
            image_path="/data/x.jpg", status="done",
            student_id="202610101", student_name="test",
            ocr_result={"answers": [
                {"q_number": 1, "answer": "B"}, {"q_number": 2, "answer": "A"}
            ]},
            created_at=datetime.utcnow(),
        )
        db_session.add(task)
        db_session.commit()

        correct = [{"q_number": 1, "answer": "B"}, {"q_number": 2, "answer": "C"}]
        results = grade_batch_answers([task], correct_answers=correct)
        assert len(results) == 1
        assert results[0]["student_name"] == "test"
        assert results[0]["score"] == 1  # Q1 correct, Q2 wrong
        assert results[0]["questions"][0]["is_correct"] is True
        assert results[0]["questions"][1]["is_correct"] is False

    def test_grade_empty_ocr(self):
        from app.models.ocr_task import OCRTask
        from app.services.llm_grading import grade_batch_answers
        from datetime import datetime
        task = OCRTask(
            task_id="ocr_empty", teacher_id="t1", batch_id="b1",
            image_path="/data/x.jpg", status="done",
            ocr_result=None,
            created_at=datetime.utcnow(),
        )
        results = grade_batch_answers([task], correct_answers=[])
        assert results[0].get("error") is not None

    def test_grade_no_answer_source(self):
        """没有正确答案来源（无老师答案、无 exam_id）→ 可读错误，不再全判错。"""
        from app.models.ocr_task import OCRTask
        from app.services.llm_grading import grade_batch_answers
        from datetime import datetime
        task = OCRTask(
            task_id="ocr_no_src", teacher_id="t1", batch_id="b1",
            image_path="/data/x.jpg", status="done",
            ocr_result={"answers": [{"q_number": 1, "answer": "B"}]},
            created_at=datetime.utcnow(),
        )
        results = grade_batch_answers([task], correct_answers=None, exam_id=None)
        assert results[0]["task_id"] == "ocr_no_src"
        assert "缺少正确答案" in results[0]["error"]
        assert "score" not in results[0]

    def test_grade_exam_bank_source(self, db_session):
        """exam_id 关联真实 ExamRecord+Question 时从题库取标准答案。"""
        from app.models.database import (
            ExamRecord, RecordType, Question, Difficulty, QuestionSource, AuditStatus,
        )
        from app.models.ocr_task import OCRTask
        from app.services.llm_grading import grade_batch_answers
        from datetime import datetime

        exam_id = "exam_test_001"
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

        task = OCRTask(
            task_id="ocr_exam", teacher_id="t1", batch_id="b1",
            image_path="/data/x.jpg", status="done",
            ocr_result={"answers": [{"q_number": 1, "answer": "B"}]},
            created_at=datetime.utcnow(),
        )
        results = grade_batch_answers([task], correct_answers=None, exam_id=exam_id, db=db_session)
        assert results[0]["score"] == 1
        assert results[0]["questions"][0]["is_correct"] is True

    def test_semantic_judgment_for_non_choice(self, db_session, monkeypatch):
        """非选择题归一化后不一致 → 批量 LLM 语义判定（mock llm_service）。"""
        from app.models.ocr_task import OCRTask
        from app.services.llm_grading import grade_batch_answers
        from datetime import datetime

        def fake_generate_text(prompt, **kw):
            return {
                "success": True,
                "content": (
                    '[{"q": 1, "equivalent": true, "reason": "等价"}, '
                    '{"q": 2, "equivalent": false, "reason": "系数不同"}]'
                ),
            }
        # llm_service 在 app/services/__init__.py 是包级实例，遮蔽了同名子模块，
        # 直接 patch 实例方法（判卷中心的语义判定引用同一实例）。
        from app.services.llm_service import llm_service
        monkeypatch.setattr(llm_service, "generate_text", fake_generate_text)

        task = OCRTask(
            task_id="ocr_semantic", teacher_id="t1", batch_id="b1",
            image_path="/data/x.jpg", status="done",
            ocr_result={"answers": [
                {"q_number": 1, "answer": "3OH- + Fe3+ = Fe(OH)3↓"},
                {"q_number": 2, "answer": "2H2 + O2 = H2O"},
            ]},
            created_at=datetime.utcnow(),
        )
        # q1 左右翻转但化学等价（归一化不匹配 → 需 LLM）；q2 配平错误。
        correct = [
            {"q_number": 1, "answer": "Fe^{3+} + 3OH^{-} = Fe(OH)_{3}↓"},
            {"q_number": 2, "answer": "2H_{2} + O_{2} = 2H_{2}O"},
        ]
        results = grade_batch_answers([task], correct_answers=correct)
        assert results[0]["score"] == 1  # q1 语义等价判对，q2 判错
        q1 = results[0]["questions"][0]
        assert q1["is_correct"] is True
        assert "LLM 语义判定" in q1["reason"]
        assert results[0]["questions"][1]["is_correct"] is False

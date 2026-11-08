"""判卷中心服务层测试 — 测试面 = grading_center 的 grade / save / override / finalize。

只断言外部行为：判对判错、落库与否、诊断触发与否、幂等与统计——
不测内部函数调用次序。LLM 语义判定以假 judge 注入。
"""
import pytest
from datetime import datetime

from app.services import grading_center


# ── 假语义判定器：记录调用次数，全部判等价 ──

def _fake_judge(equivalent=True, calls=None):
    def _judge(unresolved):
        if calls is not None:
            calls.append(len(unresolved))
        for q in unresolved:
            q["is_correct"] = equivalent
            q["reason"] = "fake 判定"
    return _judge


@pytest.fixture
def exam_record(db_session):
    """PRACTICE 记录 + 4 题（含 2 选择 + 2 主观）。"""
    from app.models.database import ExamRecord, Question, RecordType, Difficulty, QuestionSource, AuditStatus

    rec = ExamRecord(
        record_id="gc_exam_001", class_id="class_2025_1",
        name="判卷中心测试卷", type=RecordType.PRACTICE,
        total_students=1, present_students=1, exam_date=datetime.utcnow(),
    )
    db_session.add(rec)
    specs = [
        ("gc_q_1", "选择题A", ["A", "B", "C", "D"], "B"),
        ("gc_q_2", "选择题B", ["A", "B", "C", "D"], "A"),
        ("gc_q_3", "方程式题", None, "2Na+2H2O=2NaOH+H2↑"),
        ("gc_q_4", "计算题", None, "22.4L"),
    ]
    for qid, content, opts, ans in specs:
        db_session.add(Question(
            question_id=qid, record_id="gc_exam_001", content=content,
            options=opts, answer=ans, analysis="",
            knowledge_points=["kp"], difficulty=Difficulty.MEDIUM,
            source=QuestionSource.MANUAL_SELECTED, audit_status=AuditStatus.PASSED,
        ))
    db_session.commit()
    return rec


def _entries(*pairs):
    return [{"question_id": q, "answer": a} for q, a in pairs]


def _key(db, record_id):
    from app.models.database import Question
    return [
        {"question_id": q.question_id, "answer": q.answer}
        for q in db.query(Question).filter(Question.record_id == record_id).all()
    ]


class TestGrade:
    """分层判定：归一化精确匹配 + 可选批量语义判定。"""

    def test_choice_normalized_match(self, db_session, exam_record):
        r = grading_center.grade(
            _entries(("gc_q_1", "b"), ("gc_q_2", "A")), _key(db_session, "gc_exam_001"),
        )
        assert r["questions"][0]["is_correct"] is True   # 小写归一
        assert r["questions"][1]["is_correct"] is True
        assert r["pending_semantic"] == 0

    def test_choice_mismatch_no_semantic(self, db_session, exam_record):
        calls = []
        r = grading_center.grade(
            _entries(("gc_q_1", "C")), _key(db_session, "gc_exam_001"),
            judge=_fake_judge(calls=calls),
        )
        assert r["questions"][0]["is_correct"] is False
        assert r["pending_semantic"] == 0   # 选择题不进语义判定
        assert calls == []

    def test_semantic_judged_in_one_batch(self, db_session, exam_record):
        calls = []
        r = grading_center.grade(
            _entries(("gc_q_3", "Fe2O3+3CO=2Fe+3CO2"), ("gc_q_4", "33.6L")),
            _key(db_session, "gc_exam_001"),
            judge=_fake_judge(calls=calls),
        )
        assert calls == [2]                  # 两道主观题合并为 ≤1 次批量调用
        assert all(q["is_correct"] for q in r["questions"])
        assert r["pending_semantic"] == 0

    def test_semantic_false_returns_pending(self, db_session, exam_record):
        """线上提交路径：语义判定延迟到后台作业，主观题带 needs_semantic 返回。"""
        calls = []
        r = grading_center.grade(
            _entries(("gc_q_1", "B"), ("gc_q_3", "随便写的")),
            _key(db_session, "gc_exam_001"),
            semantic=False, judge=_fake_judge(calls=calls),
        )
        assert calls == []                   # 同步阶段零 LLM 调用
        by_id = {q["question_id"]: q for q in r["questions"]}
        assert by_id["gc_q_1"]["is_correct"] is True
        assert by_id["gc_q_3"]["needs_semantic"] is True
        assert by_id["gc_q_3"]["is_correct"] is False
        assert r["pending_semantic"] == 1

    def test_missing_answer_marked(self, db_session, exam_record):
        r = grading_center.grade(_entries(("gc_q_1", "B")), [{"question_id": "gc_q_x", "answer": ""}])
        assert r["questions"][0]["is_correct"] is False
        assert "缺少" in r["questions"][0]["reason"]


class TestSave:
    """单点落库：幂等、来源标记、练习即触发诊断。"""

    def test_save_practice_enqueues_diagnosis_once(self, db_session, exam_record, monkeypatch):
        from app.models.database import StudentAnswer
        enqueued = []
        monkeypatch.setattr("app.jobs.enqueue_job",
                            lambda t, p: enqueued.append((t, p["exam_record_id"])))

        graded = [
            {"question_id": "gc_q_1", "student_answer": "B", "is_correct": True},
            {"question_id": "gc_q_3", "student_answer": "2Na+2H2O=2NaOH+H2", "is_correct": False,
             "reason": "LLM 语义判定：不等价"},
        ]
        out = grading_center.save(db_session, graded, "202610101", "gc_exam_001", "online")
        db_session.commit()

        assert out["saved"] == 2
        rows = db_session.query(StudentAnswer).filter_by(exam_record_id="gc_exam_001").all()
        assert len(rows) == 2
        assert all(r.source.value == "online" for r in rows)
        assert rows[1].grade_reason == "LLM 语义判定：不等价"
        assert enqueued == [("diagnosis", "gc_exam_001")]

        # 重放幂等：同批作答再保存不产生新行、不重复触发诊断
        out2 = grading_center.save(db_session, graded, "202610101", "gc_exam_001", "online")
        db_session.commit()
        assert out2["saved"] == 0 and out2["skipped_duplicate"] == 2
        assert enqueued == [("diagnosis", "gc_exam_001")]

    def test_save_exam_type_no_auto_diagnosis(self, db_session, exam_record, monkeypatch):
        """考试记录：save 本身不触发诊断（由 confirm 路径负责）。"""
        from app.models.database import RecordType
        exam_record.type = RecordType.EXAM
        db_session.commit()

        enqueued = []
        monkeypatch.setattr("app.jobs.enqueue_job",
                            lambda t, p: enqueued.append((t, p["exam_record_id"])))
        grading_center.save(db_session, [
            {"question_id": "gc_q_1", "student_answer": "B", "is_correct": True},
        ], "202610101", "gc_exam_001", "online")
        db_session.commit()
        assert enqueued == []

    def test_save_missing_question_counted(self, db_session, exam_record):
        out = grading_center.save(db_session, [
            {"question_id": "gc_nope", "student_answer": "B", "is_correct": True},
        ], "202610101", "gc_exam_001", "online")
        db_session.commit()
        assert out["saved"] == 0 and out["question_missing"] == 1

    def test_save_unknown_record_still_persists(self, db_session, monkeypatch):
        """chat/训练作答无 exam_record_id：照常落库，不触发诊断。"""
        from app.models.database import Question, Student, Difficulty, QuestionSource, AuditStatus
        db_session.add(Student(student_id="202610101", name="李雨萱", class_id="class_2025_1"))
        db_session.add(Question(
            question_id="chat_q_1", record_id=None, content="步题",
            options=None, answer="O2", analysis="", knowledge_points=[],
            difficulty=Difficulty.MEDIUM, source=QuestionSource.MANUAL_SELECTED,
            audit_status=AuditStatus.PASSED,
        ))
        db_session.commit()

        enqueued = []
        monkeypatch.setattr("app.jobs.enqueue_job",
                            lambda t, p: enqueued.append((t, p["exam_record_id"])))
        out = grading_center.save(db_session, [
            {"question_id": "chat_q_1", "student_answer": "O2", "is_correct": True},
        ], "202610101", None, "chat")
        db_session.commit()
        assert out["saved"] == 1
        assert enqueued == []


class TestSaveBatchOcr:
    """OCR 批量确认保存（原 save_grading_results 落库体搬入）。"""

    def test_confirm_batch_saves_and_diagnoses(self, db_session, exam_record, monkeypatch):
        from app.models.database import (
            RecordType, Student, StudentAnswer, Question, Difficulty,
            QuestionSource, AuditStatus,
        )
        from app.models.ocr_task import OCRTask
        exam_record.type = RecordType.EXAM
        db_session.add(Student(student_id="202610101", name="李雨萱", class_id="class_2025_1"))
        # OCR 管线契约：题号按 question_id = f"{exam_id}_{题号}" 关联
        for n, ans in [(1, "B"), (3, "2Na+2H2O=2NaOH+H2↑")]:
            db_session.add(Question(
                question_id=f"gc_exam_001_{n}", record_id="gc_exam_001",
                content=f"题{n}", options=None, answer=ans, analysis="",
                knowledge_points=[], difficulty=Difficulty.MEDIUM,
                source=QuestionSource.MANUAL_SELECTED, audit_status=AuditStatus.PASSED,
            ))
        db_session.add(OCRTask(
            task_id="ocr_t1", teacher_id="t1", batch_id="gc_batch_1",
            image_path="/tmp/ocr_t1.jpg", title="判卷中心测试卡",
            student_id="202610101", student_name="李雨萱", status="done",
            ocr_result={"answers": []},
            grading_result={"questions": [
                {"q_number": 1, "student_answer": "B", "is_correct": True},
                {"q_number": 3, "student_answer": "X", "is_correct": False},
            ]},
        ))
        db_session.commit()

        enqueued = []
        monkeypatch.setattr("app.jobs.enqueue_job",
                            lambda t, p: enqueued.append((t, p["exam_record_id"])))
        out = grading_center.save_batch(
            db_session, batch_id="gc_batch_1", exam_id="gc_exam_001",
            scope=grading_center.CallerScope(caller_id="t1", class_ids={"class_2025_1"}),
        )
        db_session.commit()

        assert out["saved"] == 1
        assert out["diagnosis"] == "已触发"
        assert enqueued == [("diagnosis", "gc_exam_001")]
        rows = db_session.query(StudentAnswer).filter_by(exam_record_id="gc_exam_001").all()
        assert len(rows) == 2
        assert all(r.source.value == "ocr" for r in rows)
        assert any(r.answer_id.startswith("ocr_") for r in rows)

    def test_confirm_batch_requires_exam(self, db_session, exam_record):
        out = grading_center.save_batch(
            db_session, batch_id="b", exam_id="ghost",
            scope=grading_center.CallerScope(caller_id="t1", class_ids={"class_2025_1"}),
        )
        assert "error" in out

    def test_confirm_batch_rejects_foreign_exam_and_batch(self, db_session, exam_record):
        """越界的考试 / 别人的答题卡批次都不许写（成绩确认门的写侧）。"""
        from app.models.ocr_task import OCRTask
        db_session.add(OCRTask(
            task_id="ocr_t9", teacher_id="t_other", batch_id="gc_batch_9",
            image_path="/tmp/x.jpg", title="别人的卡", status="done",
            grading_result={"questions": [{"q_number": 1, "student_answer": "B", "is_correct": True}]},
        ))
        db_session.commit()
        mine = grading_center.CallerScope(caller_id="t1", class_ids={"class_2025_1"})
        other_class = grading_center.CallerScope(caller_id="t1", class_ids={"c_other"})

        assert grading_center.save_batch(
            db_session, batch_id="gc_batch_9", exam_id="gc_exam_001", scope=mine,
        ).get("denied") is True
        assert grading_center.save_batch(
            db_session, batch_id="gc_batch_9", exam_id="gc_exam_001", scope=other_class,
        ).get("denied") is True

    def test_school_wide_scope_is_limited_to_own_school(self, db_session, exam_record):
        """校级管理员的批次归属限本校：别校教师的批、无归属批都不能保存。"""
        from app.models.database import Teacher
        from app.models.ocr_task import OCRTask
        db_session.add(Teacher(teacher_id="T_away", name="别校老师", school_id="sch2"))
        for task_id, owner in (("ocr_away", "T_away"), ("ocr_orphan", "")):
            db_session.add(OCRTask(
                task_id=task_id, teacher_id=owner, batch_id=f"b_{task_id}",
                image_path="/tmp/x.jpg", title="卡", status="done",
                grading_result={"questions": [{"q_number": 1, "student_answer": "B", "is_correct": True}]},
            ))
        db_session.commit()
        admin = grading_center.CallerScope(
            caller_id="A1", class_ids={"class_2025_1"}, school_wide=True,
            school_id="sch1", db=db_session,
        )

        assert grading_center.save_batch(
            db_session, batch_id="b_ocr_away", exam_id="gc_exam_001", scope=admin,
        ).get("denied") is True
        assert grading_center.save_batch(
            db_session, batch_id="b_ocr_orphan", exam_id="gc_exam_001", scope=admin,
        ).get("denied") is True
        assert admin.allows_batch("T_away") is False
        assert admin.allows_batch("") is False


class TestOverrideAndFinalize:
    """教师改判 + finalize 真实统计。"""

    def _seed_answer(self, db_session, exam_record):
        from app.models.database import Student, StudentAnswer, AnswerSource
        db_session.add(Student(student_id="202610101", name="李雨萱", class_id="class_2025_1"))
        db_session.add(StudentAnswer(
            answer_id="ans_gc_1", student_id="202610101", question_id="gc_q_1",
            exam_record_id="gc_exam_001", student_answer="C", is_correct=False,
            source=AnswerSource.ONLINE,
        ))
        db_session.commit()

    def test_override_updates_and_retriggers(self, db_session, exam_record, monkeypatch):
        self._seed_answer(db_session, exam_record)
        enqueued = []
        monkeypatch.setattr("app.jobs.enqueue_job",
                            lambda t, p: enqueued.append((t, p["exam_record_id"])))

        out = grading_center.override(
            db_session, answer_id="ans_gc_1", is_correct=True,
            reason="老师确认等价", teacher_id="t1",
        )
        db_session.commit()

        assert out["updated"] is True
        from app.models.database import StudentAnswer
        row = db_session.query(StudentAnswer).filter_by(answer_id="ans_gc_1").first()
        assert row.is_correct is True
        assert "教师改判" in row.grade_reason and "老师确认等价" in row.grade_reason
        assert ("diagnosis", "gc_exam_001") in enqueued

    def test_override_unknown_answer(self, db_session, exam_record):
        out = grading_center.override(db_session, "ghost", True, "r", "t1")
        assert out["updated"] is False and "error" in out

    def test_finalize_real_stats(self, db_session, exam_record):
        from app.models.database import Student, StudentAnswer, AnswerSource
        db_session.add(Student(student_id="202610101", name="李雨萱", class_id="class_2025_1"))
        for i, (correct, ans) in enumerate([(True, "B"), (False, "C"), (True, "eq"), (False, "x")]):
            db_session.add(StudentAnswer(
                answer_id=f"ans_f_{i}", student_id="202610101",
                question_id=f"gc_q_{i+1}", exam_record_id="gc_exam_001",
                student_answer=ans, is_correct=correct, source=AnswerSource.ONLINE,
            ))
        db_session.commit()

        stats = grading_center.finalize(db_session, "gc_exam_001")
        assert stats["present_students"] == 1
        assert stats["answered_count"] == 4
        assert stats["accuracy"] == 0.5


class TestSemanticGradingJob:
    """主观题「落行+消费」扫描作业（ADR-0013）：PENDING 行判定覆盖，失败保留重扫。"""

    def _seed_pending(self, db_session):
        from app.models.database import Student, StudentAnswer, AnswerSource
        db_session.add(Student(student_id="202610101", name="李雨萱", class_id="class_2025_1"))
        db_session.add(StudentAnswer(
            answer_id="ans_scan_1", student_id="202610101", question_id="gc_q_3",
            exam_record_id="gc_exam_001", student_answer="Fe2O3+3CO=2Fe+3CO2",
            is_correct=False, grade_reason="PENDING_SEMANTIC", source=AnswerSource.ONLINE))
        db_session.commit()

    def test_scan_judges_and_diagnoses(self, db_session, exam_record, monkeypatch):
        from app.models.database import StudentAnswer
        from app.jobs import handlers
        self._seed_pending(db_session)
        monkeypatch.setattr("app.models.database.get_db", lambda: iter([db_session]))
        enqueued = []
        monkeypatch.setattr("app.jobs.enqueue_job",
                            lambda t, p: enqueued.append((t, p["exam_record_id"])))

        def fake_judge(unresolved):
            for q in unresolved:
                q["needs_semantic"] = False
                q["is_correct"] = True
                q["reason"] = "等价"
        monkeypatch.setattr(grading_center, "_semantic_judge_batch", fake_judge)
        # 扫描内联复用 diagnose_exam（本身已是后台作业，不再嵌套入队）
        diagnosed = []
        monkeypatch.setattr(handlers, "diagnose_exam",
                            lambda db, eid: diagnosed.append(eid) or {"analyzed_count": 0})

        out = handlers.scan_semantic_pending(db_session, "gc_exam_001")
        db_session.commit()

        assert out["judged"] == 1
        row = db_session.query(StudentAnswer).filter_by(answer_id="ans_scan_1").one()
        assert row.is_correct is True
        assert row.grade_reason != "PENDING_SEMANTIC"   # 覆盖落定
        assert "gc_exam_001" in diagnosed                # 判定落定后触发诊断

        # 重扫幂等：已判定行不再进扫描
        out2 = handlers.scan_semantic_pending(db_session, "gc_exam_001")
        assert out2["judged"] == 0

    def test_scan_failure_keeps_pending(self, db_session, exam_record, monkeypatch):
        """判定失败：行保留 PENDING 标记（不落错误判定、下轮重扫）。"""
        from app.models.database import StudentAnswer
        from app.jobs import handlers
        self._seed_pending(db_session)
        monkeypatch.setattr("app.models.database.get_db", lambda: iter([db_session]))

        def failing_judge(unresolved):
            for q in unresolved:
                q["needs_semantic"] = True   # 保留未决 = 失败
                q["reason"] = "LLM 判定失败，待重试"
        monkeypatch.setattr(grading_center, "_semantic_judge_batch", failing_judge)

        out = handlers.scan_semantic_pending(db_session, "gc_exam_001")
        db_session.commit()

        assert out["judged"] == 0
        row = db_session.query(StudentAnswer).filter_by(answer_id="ans_scan_1").one()
        assert row.grade_reason == "PENDING_SEMANTIC"   # 待判定态保留


class TestSemanticJudgmentPerRow:
    """同一批次里同题多行（整场考试的主观题逐生各一条）必须各判各的。

    判定结果若按题号引用，同题的后一条会覆盖前一条，最后一条判定被套给所有行——
    写对的学生被判错（顺序反过来则写错的被判对），且不报错。
    """

    def _seed_two_students_same_question(self, db_session):
        from app.models.database import Student, StudentAnswer, AnswerSource
        for sid, name in (("202610101", "李雨萱"), ("202610102", "张浩宇")):
            db_session.add(Student(student_id=sid, name=name, class_id="class_2025_1"))
        for answer_id, sid, ans in (("ans_row_ok", "202610101", "对"),
                                    ("ans_row_bad", "202610102", "错")):
            db_session.add(StudentAnswer(
                answer_id=answer_id, student_id=sid, question_id="gc_q_3",
                exam_record_id="gc_exam_001", student_answer=ans, is_correct=False,
                grade_reason="PENDING_SEMANTIC", source=AnswerSource.ONLINE))
        db_session.commit()

    def test_rows_keep_their_own_judgment(self, db_session, exam_record, monkeypatch):
        import json as _json
        import re as _re
        from app.models.database import StudentAnswer
        from app.jobs import handlers
        from app.services.llm_service import llm_service

        self._seed_two_students_same_question(db_session)

        def fake_generate(prompt, **kw):   # 实例补丁不绑定 self
            payload = _json.loads(_re.search(r"题目：(\[.*?\])\n", prompt, _re.S).group(1))
            return {"success": True, "content": _json.dumps([
                {"i": p["i"], "equivalent": p["student"] == "对", "reason": f"条目 {p['i']}"}
                for p in payload
            ], ensure_ascii=False)}

        monkeypatch.setattr(llm_service, "generate_text", fake_generate)
        monkeypatch.setattr(handlers, "diagnose_exam", lambda db, eid: {})

        out = handlers.scan_semantic_pending(db_session, "gc_exam_001")
        db_session.commit()

        assert out["judged"] == 2
        rows = {a.answer_id: a for a in db_session.query(StudentAnswer).filter(
            StudentAnswer.question_id == "gc_q_3").all()}
        assert rows["ans_row_ok"].is_correct is True     # 写对的不被判错
        assert rows["ans_row_bad"].is_correct is False   # 写错的也不被判对


class TestReviewFixes:
    """code-review 修正回归：双计/双触发/失败固化。"""

    def test_save_does_not_bump_exercises_completed(self, db_session, exam_record, sample_student):
        """练习完成数由提交路径 +1/次计，save 不再按题累加（消灭双计）。"""
        from app.models.database import Student
        student = db_session.query(Student).filter_by(student_id="202610101").first()
        before = student.exercises_completed or 0
        grading_center.save(db_session, [
            {"question_id": "gc_q_1", "student_answer": "B", "is_correct": True},
            {"question_id": "gc_q_2", "student_answer": "A", "is_correct": True},
        ], "202610101", "gc_exam_001", "online")
        db_session.commit()
        assert (student.exercises_completed or 0) == before

    def test_sync_save_with_pending_skips_diagnosis(self, db_session, exam_record, sample_student, monkeypatch):
        """两段式提交：同步段有主观题在途 → 不触发诊断，由异步收尾段触发一次。"""
        enqueued = []
        monkeypatch.setattr("app.jobs.enqueue_job",
                            lambda t, p: enqueued.append((t, p["exam_record_id"])))
        grading_center.save(db_session, [
            {"question_id": "gc_q_1", "student_answer": "B", "is_correct": True},
        ], "202610101", "gc_exam_001", "online", trigger_diagnosis=False)
        db_session.commit()
        assert enqueued == []

    def test_judge_failed_not_persisted_on_retry(self, db_session, exam_record, sample_student, monkeypatch):
        """语义判定失败：行保持 PENDING 待重试，不固化「判错」。"""
        from app.models.database import StudentAnswer, AnswerSource
        from app.jobs import handlers
        db_session.add(StudentAnswer(
            answer_id="ans_pending_1", student_id="202610101", question_id="gc_q_3",
            exam_record_id="gc_exam_001", student_answer="X", is_correct=False,
            grade_reason="PENDING_SEMANTIC", source=AnswerSource.ONLINE))
        db_session.commit()
        monkeypatch.setattr("app.models.database.get_db", lambda: iter([db_session]))
        enqueued = []
        monkeypatch.setattr("app.jobs.enqueue_job", lambda t, p: enqueued.append(t))

        def _fail_judge(unresolved):
            for q in unresolved:
                q["needs_semantic"] = True
                q["reason"] = "LLM 判定失败，待重试"
        monkeypatch.setattr(grading_center, "_semantic_judge_batch", _fail_judge)

        handlers.scan_semantic_pending(db_session, "gc_exam_001")
        db_session.commit()
        row = db_session.query(StudentAnswer).filter_by(answer_id="ans_pending_1").one()
        assert row.grade_reason == "PENDING_SEMANTIC"   # 失败判定未固化，重试可重新判定

    def test_training_prefix_isolates_sessions(self, db_session, exam_record, sample_student):
        """无记录归属的作答按会话前缀隔离幂等：不同会话同题各自成行。"""
        from app.models.database import StudentAnswer
        for prefix in ("train_s1", "train_s2"):
            grading_center.save(db_session, [
                {"question_id": "gc_q_1", "student_answer": "B", "is_correct": True},
            ], "202610101", None, "training", idempotency_prefix=prefix)
        db_session.commit()
        from app.models.database import AnswerSource
        rows = db_session.query(StudentAnswer).filter(
            StudentAnswer.student_id == "202610101",
            StudentAnswer.source == AnswerSource.TRAINING,
        ).all()
        assert len(rows) == 2
        assert {r.answer_id.split("_")[1] for r in rows} == {"s1", "s2"}


class TestConfirmGateCallers:
    """成绩确认门：待确认成绩可见 + 有调用方能确认（此前只有端点，成绩永久未生效）。"""

    def _seed_unconfirmed(self, db_session):
        from app.models.database import Student, StudentAnswer, AnswerSource
        db_session.add(Student(student_id="202610101", name="李雨萱", class_id="class_2025_1"))
        db_session.add(StudentAnswer(
            answer_id="ans_cf_1", student_id="202610101", question_id="gc_q_3",
            exam_record_id="gc_exam_001", student_answer="2Na+2H2O=2NaOH+H2↑",
            is_correct=True, confirmed=False, source=AnswerSource.ONLINE))
        db_session.commit()

    def _scope(self, *class_ids):
        return grading_center.CallerScope(caller_id="t1", class_ids=set(class_ids))

    def test_grading_queue_lists_unconfirmed_exams(self, db_session, exam_record):
        self._seed_unconfirmed(db_session)
        out = grading_center.grading_queue(db_session, self._scope("class_2025_1"))
        assert [e["exam_record_id"] for e in out["unconfirmed_exams"]] == ["gc_exam_001"]
        assert out["unconfirmed_exams"][0]["student_count"] == 1
        assert out["unconfirmed_exams"][0]["answers"] == 1

    def test_grading_queue_narrows_by_class_scope(self, db_session, exam_record):
        self._seed_unconfirmed(db_session)
        assert grading_center.grading_queue(db_session, self._scope("c_other"))["unconfirmed_exams"] == []
        assert grading_center.grading_queue(db_session, self._scope("class_2025_1"))["unconfirmed_exams"]

    def test_grading_queue_empty_scope_reads_nothing(self, db_session, exam_record):
        """无身份/空范围（学生 token 自报 teacher persona）读不到任何队列内容。"""
        self._seed_unconfirmed(db_session)
        out = grading_center.grading_queue(db_session, grading_center.CallerScope())
        assert out["unconfirmed_exams"] == [] and out["pending_confirm"] == []

    def test_confirm_makes_rows_effective_and_finalize_counts_them(
            self, db_session, exam_record, monkeypatch):
        from app.models.database import StudentAnswer
        monkeypatch.setattr("app.jobs.enqueue_job", lambda t, p: None)
        self._seed_unconfirmed(db_session)

        out = grading_center.confirm(db_session, "gc_exam_001")
        db_session.commit()

        assert out["confirmed"] == 1
        row = db_session.query(StudentAnswer).filter_by(answer_id="ans_cf_1").one()
        assert row.confirmed is True
        stats = grading_center.finalize(db_session, "gc_exam_001")
        assert stats["answered_count"] == 1 and stats["present_students"] == 1

    @pytest.mark.asyncio
    async def test_agent_tool_confirms_exam_grades(self, db_session, exam_record, monkeypatch):
        """Agent 确认入口：老师能通过对话把成绩确认生效（工具是薄 adapter）。

        身份取服务端上下文（token），并按考试所属班级收窄范围。
        """
        import json
        import app.models.database as db_mod
        from app.models.database import Account, TeacherClassSubject
        from agent.tools.context import set_current_teacher
        from agent.tools.ocr_grading import confirm_exam_grades
        monkeypatch.setattr(db_mod, "get_db", lambda: iter([db_session]))
        monkeypatch.setattr("app.jobs.enqueue_job", lambda t, p: None)
        db_session.add(Account(account_id="acc_chem", username="chem", role="teacher",
                               teacher_id="T_chem", password_hash="x"))
        db_session.add(TeacherClassSubject(id="tcs_chem", teacher_id="T_chem",
                                           class_id="class_2025_1", subject="化学"))
        db_session.commit()
        self._seed_unconfirmed(db_session)
        set_current_teacher("T_chem")
        try:
            out = json.loads(await confirm_exam_grades("gc_exam_001"))
        finally:
            set_current_teacher("")

        assert out["confirmed"] == 1
        assert "生效" in out["message"]


class TestChoiceMetadataRouting:
    """题型路由按 options 元数据（双边启发式只做兜底）：短化学式不再被当选择题判错。"""

    def test_answer_key_choice_uses_options(self):
        assert grading_center.answer_key_choice("B", ["A", "B", "C", "D"]) is True
        assert grading_center.answer_key_choice("Be", None) is False
        assert grading_center.answer_key_choice("Fe2O3+3CO=2Fe+3CO2", ["A", "B"]) is False

    def test_short_formula_with_metadata_goes_semantic(self, db_session, exam_record):
        """标准答案 Be / 学生写 Ba：带 choice=False 元数据时交语义判定，不被启发式判错。"""
        calls = []
        r = grading_center.grade(
            [{"question_id": "gc_q_3", "answer": "Ba"}],
            [{"question_id": "gc_q_3", "answer": "Be", "choice": False}],
            judge=_fake_judge(equivalent=True, calls=calls),
        )
        assert calls == [1], "非选择题应进入语义判定"
        assert r["questions"][0]["is_correct"] is True


class TestSemanticVerdictMustBeBoolean:
    """equivalent 是字符串时必须严格解析：'false' 不能按真值当成判对。"""

    def _seed_pending(self, db_session):
        from app.models.database import Student, StudentAnswer, AnswerSource
        db_session.add(Student(student_id="202610101", name="李雨萱", class_id="class_2025_1"))
        db_session.add(StudentAnswer(
            answer_id="ans_sb_1", student_id="202610101", question_id="gc_q_3",
            exam_record_id="gc_exam_001", student_answer="Fe2O3+3CO=2Fe+3CO2",
            is_correct=False, grade_reason="PENDING_SEMANTIC", source=AnswerSource.ONLINE))
        db_session.commit()

    def _stub_llm(self, monkeypatch, equivalent):
        import json as _json
        from app.services.llm_service import llm_service

        def fake_generate(prompt, **kw):
            return {"success": True, "content": _json.dumps(
                [{"i": 0, "equivalent": equivalent, "reason": "系数写错"}], ensure_ascii=False)}

        monkeypatch.setattr(llm_service, "generate_text", fake_generate)

    def test_string_false_is_not_a_pass(self, db_session, exam_record, monkeypatch):
        """'false' 必须判成「不通过」—— 此前 bool("false") 为 True，判错被写成判对。"""
        from app.models.database import StudentAnswer
        from app.jobs import handlers
        self._seed_pending(db_session)
        self._stub_llm(monkeypatch, "false")
        monkeypatch.setattr(handlers, "diagnose_exam", lambda db, eid: {})

        out = handlers.scan_semantic_pending(db_session, "gc_exam_001")
        db_session.commit()

        assert out["judged"] == 1
        row = db_session.query(StudentAnswer).filter_by(answer_id="ans_sb_1").one()
        assert row.is_correct is False
        assert row.grade_reason != "PENDING_SEMANTIC"

    def test_string_true_is_parsed_as_true(self, db_session, exam_record, monkeypatch):
        from app.models.database import StudentAnswer
        from app.jobs import handlers
        self._seed_pending(db_session)
        self._stub_llm(monkeypatch, "true")
        monkeypatch.setattr(handlers, "diagnose_exam", lambda db, eid: {})

        out = handlers.scan_semantic_pending(db_session, "gc_exam_001")
        db_session.commit()

        assert out["judged"] == 1
        row = db_session.query(StudentAnswer).filter_by(answer_id="ans_sb_1").one()
        assert row.is_correct is True and row.grade_reason != "PENDING_SEMANTIC"

    def test_unparsable_verdict_keeps_row_pending(self, db_session, exam_record, monkeypatch):
        """认不出的判定值不能被静默吞并：保留待判定，下轮重扫。"""
        from app.models.database import StudentAnswer
        from app.jobs import handlers
        self._seed_pending(db_session)
        self._stub_llm(monkeypatch, "maybe")

        out = handlers.scan_semantic_pending(db_session, "gc_exam_001")
        db_session.commit()

        assert out["judged"] == 0
        row = db_session.query(StudentAnswer).filter_by(answer_id="ans_sb_1").one()
        assert row.grade_reason == "PENDING_SEMANTIC"
        assert row.is_correct is False


class TestConfirmNotifiesStudents:
    """确认后学生应收到「判卷完成」通知（纯选择题考试没有 PENDING 行，只能靠确认补）。"""

    def _seed_unconfirmed(self, db_session):
        from app.models.database import Student, StudentAnswer, AnswerSource
        db_session.add(Student(student_id="202610101", name="李雨萱", class_id="class_2025_1"))
        db_session.add(StudentAnswer(
            answer_id="ans_nf_1", student_id="202610101", question_id="gc_q_1",
            exam_record_id="gc_exam_001", student_answer="B",
            is_correct=True, confirmed=False, source=AnswerSource.ONLINE))
        db_session.commit()

    def test_confirm_writes_grading_notification(self, db_session, exam_record, monkeypatch):
        from app.models.database import StudentNotification
        monkeypatch.setattr("app.jobs.enqueue_job", lambda t, p: None)
        self._seed_unconfirmed(db_session)

        out = grading_center.confirm(db_session, "gc_exam_001")
        db_session.commit()

        assert out["confirmed"] == 1
        notes = db_session.query(StudentNotification).filter_by(
            student_id="202610101", type="grading").all()
        assert len(notes) == 1

        grading_center.confirm(db_session, "gc_exam_001")   # 幂等：重放不重复通知
        db_session.commit()
        assert db_session.query(StudentNotification).filter_by(
            student_id="202610101", type="grading").count() == 1


class TestRecentSavedScope:
    """recent_saved 与 unconfirmed_exams 同一道闸：范围外考试一律 0。"""

    def _seed(self, db_session):
        from app.models.database import ExamRecord, RecordType, Student, StudentAnswer, AnswerSource
        db_session.add(Student(student_id="202610101", name="李雨萱", class_id="class_2025_1"))
        db_session.add(Student(student_id="202610909", name="别班同学", class_id="c_other"))
        db_session.add(ExamRecord(record_id="gc_exam_other", class_id="c_other", name="别班卷",
                                  type=RecordType.PRACTICE))
        for aid, sid, rec in (("ans_mine", "202610101", "gc_exam_001"),
                              ("ans_other", "202610909", "gc_exam_other")):
            db_session.add(StudentAnswer(
                answer_id=aid, student_id=sid, question_id="gc_q_3", exam_record_id=rec,
                student_answer="x", is_correct=False, source=AnswerSource.ONLINE))
        db_session.commit()

    def test_recent_saved_counts_only_in_scope_exams(self, db_session, exam_record):
        self._seed(db_session)
        scope = grading_center.CallerScope(caller_id="t1", class_ids={"class_2025_1"})

        assert grading_center.grading_queue(
            db_session, scope, exam_id="gc_exam_001")["recent_saved"] == 1
        assert grading_center.grading_queue(
            db_session, scope, exam_id="gc_exam_other")["recent_saved"] == 0

    def test_recent_saved_hidden_for_empty_scope(self, db_session, exam_record):
        self._seed(db_session)
        assert grading_center.grading_queue(
            db_session, grading_center.CallerScope(), exam_id="gc_exam_001")["recent_saved"] == 0


class TestJudgeFailureIsNotDefinitive:
    """LLM 判定失败 ≠ 判错：保留未决、不落生效行，交扫描作业重扫（ADR-0013）。"""

    def _failing_judge(self, unresolved):
        for q in unresolved:
            q["judge_failed"] = True
            q["reason"] = "LLM 判定失败，待重试"

    def test_grade_keeps_needs_semantic_on_failure(self, db_session, exam_record):
        r = grading_center.grade(
            _entries(("gc_q_3", "随便写的")), _key(db_session, "gc_exam_001"),
            judge=self._failing_judge,
        )
        q = r["questions"][0]
        assert q["is_correct"] is False
        assert q.get("needs_semantic") is True     # 未决没有被清掉
        assert r["pending_semantic"] == 1

    def test_chat_capture_failure_lands_pending_row(self, db_session, exam_record, monkeypatch):
        from app.models.database import StudentAnswer
        monkeypatch.setattr(grading_center, "_semantic_judge_batch", self._failing_judge)
        monkeypatch.setattr(grading_center, "_enqueue_student_diagnosis", lambda sid: "已屏蔽")

        out = grading_center.capture_chat_answer(
            db_session, tool_name="ionic_equation_tutor", problem="配平",
            student_input="H2+O2=H2O", expected_answer="2H2+O2=2H2O",
            student_id="202610101",
        )
        db_session.commit()

        assert out["pending"] is True and out["is_correct"] is None
        row = db_session.query(StudentAnswer).one()
        assert row.grade_reason == grading_center.PENDING_REASON   # 待判定，不是定论错答

    def test_ocr_failed_judgment_reported_as_unjudged(self, db_session, exam_record, monkeypatch):
        from app.models.ocr_task import OCRTask
        from app.services.llm_grading import grade_batch_answers
        from app.services.llm_service import llm_service

        monkeypatch.setattr(llm_service, "generate_text",
                            lambda *a, **k: {"success": False, "error": "限流"})
        task = OCRTask(
            task_id="ocr_fail", teacher_id="t1", batch_id="b_fail", status="done",
            image_path="/data/x.jpg",
            ocr_result={"answers": [{"q_number": 3, "answer": "Fe2O3+3CO=2Fe+3CO2"}]},
        )
        db_session.add(task)
        db_session.commit()

        results = grade_batch_answers(
            [task], correct_answers=[{"q_number": 3, "answer": "Fe2O3 + 3CO → 2Fe + 3CO2"}],
            db=db_session,
        )
        assert results[0]["unjudged"] == 1
        assert results[0]["questions"][0]["reason"] == grading_center.PENDING_REASON
        assert results[0]["questions"][0]["is_correct"] is False


class TestMissingAnswerKeyIsNotWrong:
    """没有标准答案 = 未判，不是答错：不计入成绩与学情。"""

    def test_missing_key_reason_and_excluded_from_stats(self, db_session, exam_record, monkeypatch):
        monkeypatch.setattr("app.jobs.enqueue_job", lambda t, p: None)
        graded = grading_center.grade(
            _entries(("gc_q_3", "随便写的")), [{"question_id": "gc_q_3", "answer": ""}],
        )
        q = graded["questions"][0]
        assert q["reason"] == grading_center.NO_KEY_REASON
        assert "缺少" in q["reason"]

        grading_center.save(db_session, graded["questions"], "202610101",
                            "gc_exam_001", "online")
        db_session.commit()

        stats = grading_center.finalize(db_session, "gc_exam_001")
        assert stats["answered_count"] == 0      # 未判的题不算作答/不算错

    def test_effective_conditions_excludes_unjudged_reasons(self, db_session, exam_record):
        from app.models.database import StudentAnswer
        from app.services.grading_center import effective_conditions
        for aid, reason in (("ans_pending", grading_center.PENDING_REASON),
                            ("ans_nokey", grading_center.NO_KEY_REASON),
                            ("ans_ok", None)):
            db_session.add(StudentAnswer(
                answer_id=aid, student_id="202610101", question_id="gc_q_3",
                exam_record_id="gc_exam_001", student_answer="x",
                is_correct=False, grade_reason=reason,
            ))
        db_session.commit()
        ids = {r.answer_id for r in db_session.query(StudentAnswer).filter(
            effective_conditions()).all()}
        assert ids == {"ans_ok"}


class TestSaveBatchConfirmationOrdering:
    """确认标记只在真正写入作答后落：匹配不上 roster 的卡不能从待确认队列消失。"""

    def _seed(self, db_session, exam_record):
        from app.models.database import RecordType
        from app.models.ocr_task import OCRTask
        exam_record.type = RecordType.EXAM
        db_session.add(OCRTask(
            task_id="ocr_nostu", teacher_id="t1", batch_id="b_nostu", status="done",
            image_path="/tmp/x.jpg", title="卡",
            student_id="20990101",           # roster 里没有这个学号
            grading_result={"questions": [
                {"q_number": 1, "student_answer": "B", "is_correct": True}]},
        ))
        db_session.commit()

    def test_unmatched_task_stays_unconfirmed(self, db_session, exam_record, monkeypatch):
        self._seed(db_session, exam_record)
        monkeypatch.setattr("app.jobs.enqueue_job", lambda t, p: None)
        scope = grading_center.CallerScope(caller_id="t1", class_ids={"class_2025_1"})

        out = grading_center.save_batch(
            db_session, batch_id="b_nostu", exam_id="gc_exam_001", scope=scope)
        db_session.commit()

        from app.models.ocr_task import OCRTask
        assert out["skipped_no_student"] == 1
        task = db_session.query(OCRTask).filter_by(task_id="ocr_nostu").one()
        assert task.confirmed is not True      # 没写入就还留在待确认队列


class TestSaveBatchScopeAndIdempotency:
    """写入键按 (考试, 学生, 题目) 派生、学号按考试班级校验（重传与混班都不许写重/写偏）。"""

    def _seed(self, db_session, exam_record, *, student_class="class_2025_1"):
        from app.models.database import (
            RecordType, Student, Question, Difficulty, QuestionSource, AuditStatus,
        )
        from app.models.ocr_task import OCRTask
        exam_record.type = RecordType.EXAM
        db_session.add(Student(student_id="202610101", name="李雨萱", class_id=student_class))
        db_session.add(Question(
            question_id="gc_exam_001_1", record_id="gc_exam_001", content="题1",
            answer="B", analysis="", knowledge_points=[], difficulty=Difficulty.MEDIUM,
            source=QuestionSource.MANUAL_SELECTED, audit_status=AuditStatus.PASSED,
        ))
        for task_id, batch_id in (("ocr_re1", "b_re1"), ("ocr_re2", "b_re2")):
            db_session.add(OCRTask(
                task_id=task_id, teacher_id="t1", batch_id=batch_id, status="done",
                image_path="/tmp/x.jpg", title="同一张卡", student_id="202610101",
                grading_result={"questions": [
                    {"q_number": 1, "student_answer": "B", "is_correct": True}]},
            ))
        db_session.commit()

    def test_resubmitted_sheet_does_not_duplicate_rows(self, db_session, exam_record, monkeypatch):
        """同一份答题卡隔天补传到新批次（新 task_id）不再写第二行、练习数也不重复加。"""
        from app.models.database import Student, StudentAnswer
        monkeypatch.setattr("app.jobs.enqueue_job", lambda t, p: None)
        self._seed(db_session, exam_record)
        scope = grading_center.CallerScope(caller_id="t1", class_ids={"class_2025_1"})

        first = grading_center.save_batch(db_session, batch_id="b_re1",
                                          exam_id="gc_exam_001", scope=scope)
        second = grading_center.save_batch(db_session, batch_id="b_re2",
                                           exam_id="gc_exam_001", scope=scope)
        db_session.commit()

        assert first["saved"] == 1
        assert second["saved"] == 0 and second["skipped_duplicate"] == 1
        assert db_session.query(StudentAnswer).filter_by(
            exam_record_id="gc_exam_001").count() == 1
        student = db_session.query(Student).filter_by(student_id="202610101").one()
        assert (student.exercises_completed or 0) == 1

    def test_foreign_class_student_is_not_written(self, db_session, exam_record, monkeypatch):
        """答题卡认出的学号不属于本场考试的班级 → 不写作答、不计统计、不发通知。"""
        from app.models.database import StudentAnswer
        monkeypatch.setattr("app.jobs.enqueue_job", lambda t, p: None)
        notified = []
        monkeypatch.setattr(grading_center, "notify_graded",
                            lambda db, sid, rid: notified.append(sid))
        self._seed(db_session, exam_record, student_class="class_other")
        scope = grading_center.CallerScope(caller_id="t1", class_ids={"class_2025_1"})

        out = grading_center.save_batch(db_session, batch_id="b_re1",
                                        exam_id="gc_exam_001", scope=scope)
        db_session.commit()

        assert out["saved"] == 0 and out["skipped_no_student"] == 1
        assert db_session.query(StudentAnswer).count() == 0
        assert notified == []


class TestFinalizeRequiresConfirmation:
    """先确认后统计：带未确认作答 finalize 会把统计固化成占位值。"""

    def _seed_unconfirmed(self, db_session, exam_record):
        from app.models.database import RecordType, Student, StudentAnswer, AnswerSource
        exam_record.type = RecordType.EXAM
        db_session.add(Student(student_id="202610101", name="李雨萱", class_id="class_2025_1"))
        db_session.add(StudentAnswer(
            answer_id="ans_nc_1", student_id="202610101", question_id="gc_q_1",
            exam_record_id="gc_exam_001", student_answer="B", is_correct=True,
            confirmed=False, source=AnswerSource.ONLINE,
        ))
        db_session.commit()

    def test_finalize_refused_until_confirmed(self, db_session, exam_record, monkeypatch):
        monkeypatch.setattr("app.jobs.enqueue_job", lambda t, p: None)
        self._seed_unconfirmed(db_session, exam_record)

        refused = grading_center.finalize(db_session, "gc_exam_001")
        assert "error" in refused
        assert exam_record.avg_score is None     # 没被写成占位值

        grading_center.confirm(db_session, "gc_exam_001")
        db_session.commit()
        stats = grading_center.finalize(db_session, "gc_exam_001")
        assert stats["answered_count"] == 1 and stats["present_students"] == 1
        assert stats["accuracy"] == 1.0

    def test_finalize_refused_while_pending_judgment(self, db_session, exam_record,
                                                     monkeypatch):
        """已确认但还没判定的主观题（OCR 批保存即 confirmed=True）同样不能统计：
        带着它们 finalize 会把均分/参与人数固化成缺题的版本，判定落定后没人再重算。"""
        from app.models.database import AnswerSource, RecordType, Student, StudentAnswer
        monkeypatch.setattr("app.jobs.enqueue_job", lambda t, p: None)
        exam_record.type = RecordType.EXAM
        db_session.add(Student(student_id="202610101", name="李雨萱",
                               class_id="class_2025_1"))
        db_session.add(StudentAnswer(
            answer_id="ans_pd_1", student_id="202610101", question_id="gc_q_4",
            exam_record_id="gc_exam_001", student_answer="22.4L", is_correct=False,
            confirmed=True, grade_reason=grading_center.PENDING_REASON,
            source=AnswerSource.OCR,
        ))
        db_session.commit()

        refused = grading_center.finalize(db_session, "gc_exam_001")
        assert "判定中" in refused["error"]
        assert exam_record.avg_score is None     # 没被写成缺题的统计


class TestSemanticScanMissingAnswerKey:
    """题库没有标准答案时不能拿空答案重判：那会落一个永久错判的伪定论。"""

    def test_pending_without_answer_key_stays_pending(self, db_session, exam_record):
        from app.models.database import (
            Student, StudentAnswer, Question, Difficulty, QuestionSource, AuditStatus,
            AnswerSource,
        )
        from app.jobs import handlers
        db_session.add(Student(student_id="202610101", name="李雨萱", class_id="class_2025_1"))
        db_session.add(Question(
            question_id="gc_q_nokey", record_id="gc_exam_001", content="主观题",
            answer="", analysis="", knowledge_points=[], difficulty=Difficulty.MEDIUM,
            source=QuestionSource.MANUAL_SELECTED, audit_status=AuditStatus.PASSED,
        ))
        db_session.add(StudentAnswer(
            answer_id="ans_nokey_1", student_id="202610101", question_id="gc_q_nokey",
            exam_record_id="gc_exam_001", student_answer="随便写的",
            is_correct=False, grade_reason=grading_center.PENDING_REASON,
            source=AnswerSource.ONLINE,
        ))
        db_session.commit()

        out = handlers.scan_semantic_pending(db_session, exam_record_id="gc_exam_001")

        assert out["judged"] == 0
        row = db_session.query(StudentAnswer).filter_by(answer_id="ans_nokey_1").one()
        assert row.grade_reason == grading_center.PENDING_REASON   # 保留待人工，不固化

    def test_rescan_uses_row_answer_key_not_stale_question_answer(
            self, db_session, exam_record, monkeypatch):
        """重判要拿落行时真正用的答案键（老师粘贴 > 题库），不能拿题库草稿重判。"""
        from app.models.database import AnswerSource, Student, StudentAnswer
        from app.jobs import handlers

        db_session.add(Student(student_id="202610101", name="李雨萱", class_id="class_2025_1"))
        # gc_q_4 的题库答案是 22.4L，但批改时老师粘贴的答案键是 33.6L
        db_session.add(StudentAnswer(
            answer_id="ans_key_1", student_id="202610101", question_id="gc_q_4",
            exam_record_id="gc_exam_001", student_answer="33.6L",
            is_correct=False, grade_reason=grading_center.PENDING_REASON,
            answer_key="33.6L", source=AnswerSource.OCR,
        ))
        db_session.commit()

        seen = []

        def _judge(unresolved):
            seen.extend(q["correct_answer"] for q in unresolved)
            for q in unresolved:
                q["is_correct"] = True
                q["reason"] = "LLM 语义判定：等价"
                q.pop("needs_semantic", None)     # 判定完成 = 不再未决（同真实判定器）

        monkeypatch.setattr(grading_center, "_semantic_judge_batch", _judge)
        monkeypatch.setattr("app.jobs.enqueue_job", lambda t, p: None)

        out = handlers.scan_semantic_pending(db_session, exam_record_id="gc_exam_001")

        assert seen == ["33.6L"]                 # 用的是行上持久化的键，不是题库的 22.4L
        assert out["judged"] == 1
        row = db_session.query(StudentAnswer).filter_by(answer_id="ans_key_1").one()
        assert row.is_correct is True

    def test_unjudgeable_rows_do_not_starve_the_scan_window(self, db_session, exam_record,
                                                            monkeypatch):
        """不可判的行不占扫描窗口：窗口是 LIMIT 50，占满会把新落的主观题永远饿死。"""
        from app.models.database import (
            AnswerSource, AuditStatus, Difficulty, Question, QuestionSource, Student,
            StudentAnswer,
        )
        from app.jobs import handlers

        db_session.add(Student(student_id="202610101", name="李雨萱", class_id="class_2025_1"))
        # 攒满一个扫描窗口（LIMIT 50）的不可判行：都排在窗口最前面
        for i in range(50):
            db_session.add(Question(
                question_id=f"gc_q_nokey_{i}", record_id="gc_exam_001", content="无答案主观题",
                answer="", analysis="", knowledge_points=[],
                difficulty=Difficulty.MEDIUM, source=QuestionSource.MANUAL_SELECTED,
                audit_status=AuditStatus.PASSED,
            ))
            db_session.add(StudentAnswer(
                answer_id=f"ans_starve_{i}", student_id="202610101",
                question_id=f"gc_q_nokey_{i}", exam_record_id="gc_exam_001",
                student_answer="作答", is_correct=False,
                grade_reason=grading_center.PENDING_REASON, source=AnswerSource.ONLINE,
                answered_at=datetime(2020, 1, 1),
            ))
        # 新落的主观题（题库有标准答案）必须仍然被扫到
        db_session.add(StudentAnswer(
            answer_id="ans_fresh", student_id="202610101", question_id="gc_q_4",
            exam_record_id="gc_exam_001", student_answer="33.6L", is_correct=False,
            grade_reason=grading_center.PENDING_REASON, source=AnswerSource.ONLINE,
        ))
        db_session.commit()

        def _judge(unresolved):
            for q in unresolved:
                q["is_correct"] = True
                q["reason"] = "判定"
                q.pop("needs_semantic", None)

        monkeypatch.setattr(grading_center, "_semantic_judge_batch", _judge)
        monkeypatch.setattr("app.jobs.enqueue_job", lambda t, p: None)
        monkeypatch.setattr(handlers, "diagnose_exam", lambda db, rid: {})

        out = handlers.scan_semantic_pending(db_session, exam_record_id="gc_exam_001")

        assert out["judged"] == 1
        assert db_session.query(StudentAnswer).filter_by(
            answer_id="ans_fresh").one().grade_reason == "判定"

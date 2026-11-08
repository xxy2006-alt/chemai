"""考试生命周期（exam-lifecycle）测试。

状态机：合法迁移放行 + 留痕、非法迁移拒绝、存量回填。
学生作答面：按状态可见、开考置态、提交一次性守卫、判卷中心 grading 握手。
"""
import pytest
from datetime import datetime

from app.models.database import (
    Base, ExamRecord, RecordType, Question, Difficulty, QuestionSource, AuditStatus, Student,
)
from app.services import exam_lifecycle as lc
from app.middleware.auth import create_access_token


@pytest.fixture
def exam(db_session):
    rec = ExamRecord(record_id="el_exam_1", class_id="class_2025_1",
                     name="期中考试", type=RecordType.EXAM,
                     total_students=1, present_students=1, exam_date=datetime.utcnow())
    db_session.add(rec)
    db_session.add(Question(
        question_id="el_q_1", record_id="el_exam_1", content="计算题",
        options=None, answer="22.4L", analysis="", knowledge_points=[],
        difficulty=Difficulty.MEDIUM, source=QuestionSource.MANUAL_SELECTED,
        audit_status=AuditStatus.PASSED))
    db_session.commit()
    return rec


class TestStatusMachine:
    """合法迁移放行 + 时间戳留痕；非法迁移拒绝。"""

    def test_legal_transition_sets_timestamp(self, db_session, exam):
        assert lc.transition(db_session, exam, "published") is True
        db_session.commit()
        assert exam.status.value == "published"
        assert exam.published_at is not None

    def test_illegal_transition_rejected(self, db_session, exam):
        lc.transition(db_session, exam, "published")
        db_session.commit()
        # published 态不能直接跳 in_progress 之外的状态机回退/跳跃
        assert lc.transition(db_session, exam, "archived") is False
        assert exam.status.value == "published"

        rec2 = ExamRecord(record_id="el_exam_2", class_id="c", name="x",
                          type=RecordType.EXAM, exam_date=datetime.utcnow())
        db_session.add(rec2)
        db_session.commit()
        assert lc.transition(db_session, rec2, "grading") is False   # draft 不可跳 grading
        assert lc.transition(db_session, rec2, "completed") is False  # draft 不可直接收卷

    def test_full_lifecycle_chain(self, db_session, exam):
        for to in ("published", "in_progress", "grading", "completed", "archived"):
            assert lc.transition(db_session, exam, to) is True
        db_session.commit()
        assert exam.status.value == "archived"
        assert all(getattr(exam, f"{s}_at") is not None
                   for s in ("published", "started", "grading", "completed"))

    def test_cancel_from_non_terminal(self, db_session, exam):
        lc.transition(db_session, exam, "published")
        assert lc.transition(db_session, exam, "cancelled") is True
        assert lc.transition(db_session, exam, "in_progress") is False  # cancelled 终态

    def test_finalize_allows_untaken_exam(self, db_session, exam):
        """发布后无人作答直接 finalize（收卷）→ 允许 completed。"""
        lc.transition(db_session, exam, "published")
        assert lc.transition(db_session, exam, "completed") is True


class TestBackfill:
    """存量迁移：published 标志 → published 态，其余 → draft。"""

    def test_backfill_by_published_flag(self, db_session):
        pub = ExamRecord(record_id="el_b1", class_id="c", name="已发布",
                         type=RecordType.EXAM, exam_date=datetime.utcnow(),
                         question_stats={"published": True})
        draft = ExamRecord(record_id="el_b2", class_id="c", name="草稿",
                           type=RecordType.EXAM, exam_date=datetime.utcnow())
        db_session.add_all([pub, draft])
        db_session.commit()

        lc.backfill_statuses(db_session)
        db_session.expire_all()
        assert pub.status.value == "published"
        assert draft.status.value == "draft"


class TestStudentVisibility:
    """学生任务列表按状态过滤 + 标题/类型可区分。"""

    def test_status_filter_and_fields(self, db_session, exam, sample_student):
        from app.api.practice import _student_visible_tasks

        # draft 不可见
        tasks = _student_visible_tasks(db_session, sample_student)
        assert tasks == []

        lc.transition(db_session, exam, "published")
        db_session.commit()
        tasks = _student_visible_tasks(db_session, sample_student)
        assert len(tasks) == 1
        t = tasks[0]
        assert t["type"] == "exam" and t["title"] == "期中考试"
        assert t["question_count"] == 1

        # completed 后离开待完成列表
        lc.transition(db_session, exam, "in_progress")
        lc.transition(db_session, exam, "grading")
        lc.transition(db_session, exam, "completed")
        db_session.commit()
        assert _student_visible_tasks(db_session, sample_student) == []


class TestSubmitAndHandshake:
    """开考置 in_progress；EXAM 提交一次性；判卷结果 → grading 握手。"""

    def test_open_exam_sets_in_progress(self, db_session, exam, sample_student):
        lc.transition(db_session, exam, "published")
        db_session.commit()
        lc.mark_started(db_session, exam)
        db_session.commit()
        assert exam.status.value == "in_progress"
        assert exam.started_at is not None

    def test_exam_submit_once_guard(self, db_session, exam, sample_student):
        lc.transition(db_session, exam, "published")
        db_session.commit()
        from app.models.database import StudentAnswer
        db_session.add(StudentAnswer(
            answer_id="ans_el_1", student_id=sample_student.student_id,
            question_id="el_q_1", exam_record_id="el_exam_1",
            student_answer="22.4L", is_correct=True, source="online"))
        db_session.commit()
        assert lc.exam_already_submitted(db_session, "el_exam_1",
                                         sample_student.student_id) is True
        assert lc.exam_already_submitted(db_session, "ghost", "202610101") is False

    def test_grading_result_handshake(self, db_session, exam, sample_student, monkeypatch):
        """判卷中心首份考试结果 → 状态置 grading（published/in_progress → grading）。"""
        lc.transition(db_session, exam, "published")
        db_session.commit()
        monkeypatch.setattr("app.services.grading_center._enqueue_diagnosis",
                            lambda eid: "未触发")
        # 屏蔽通知（nsvc 自开会话指向真实库）
        from app.services.notification_service import NotificationService
        monkeypatch.setattr(NotificationService, "dispatch",
                            lambda **kw: {"notification_id": "x", "duplicate": False})

        from app.services import grading_center
        out = grading_center.save(db_session, [
            {"question_id": "el_q_1", "student_answer": "22.4L", "is_correct": True},
        ], sample_student.student_id, "el_exam_1", "online")
        db_session.commit()

        assert out["saved"] == 1
        db_session.expire(exam)
        assert exam.status.value == "grading"
        assert exam.grading_at is not None


class TestMixedExamE2E:
    """混合题型考试：发布 → 学生作答提交 → 选择题同步判 + 主观题待判定 → grading。

    自包含 StaticPool 会话（TestClient 跨线程共享同一连接，test_api_auth_notification 同型）。
    """

    @pytest.fixture
    def env(self, monkeypatch):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        from app.api import practice as practice_mod
        import app.models.database as db_mod

        engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                               poolclass=StaticPool)
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine, expire_on_commit=False)()
        db.add(Student(student_id="202610101", name="李雨萱", class_id="class_2025_1",
                       status="approved"))
        rec = ExamRecord(record_id="el_exam_1", class_id="class_2025_1", name="期中考试",
                         type=RecordType.EXAM, exam_date=datetime.utcnow())
        db.add(rec)
        db.add(Question(question_id="el_q_1", record_id="el_exam_1", content="计算题",
                        options=None, answer="22.4L", analysis="", knowledge_points=[],
                        difficulty=Difficulty.MEDIUM, source=QuestionSource.MANUAL_SELECTED,
                        audit_status=AuditStatus.PASSED))
        db.add(Question(question_id="el_q_2", record_id="el_exam_1", content="选择题",
                        options=["A", "B", "C", "D"], answer="A", analysis="",
                        knowledge_points=[], difficulty=Difficulty.MEDIUM,
                        source=QuestionSource.MANUAL_SELECTED, audit_status=AuditStatus.PASSED))
        db.commit()
        lc.transition(db, rec, "published")

        import app.services.notification_service as nsvc
        monkeypatch.setattr(nsvc.notification_service, "dispatch",
                            lambda **kw: {"notification_id": "x", "duplicate": False})
        enqueued = []
        monkeypatch.setattr("app.jobs.enqueue_job", lambda t, p: enqueued.append(t))
        from app.jobs.tasks import semantic_grading_task
        monkeypatch.setattr(semantic_grading_task, "delay",
                            lambda exam_record_id=None: enqueued.append("semantic_grading"))

        app = FastAPI()
        app.include_router(practice_mod.router, prefix="/api/practice")

        def override_get_db():
            yield db

        app.dependency_overrides[db_mod.get_db] = override_get_db
        with TestClient(app) as c:
            yield c, db, rec, enqueued

    def test_mixed_submit_flow(self, env):
        client, db, rec, enqueued = env

        r = client.post("/api/practice/submit", json={
            "practice_id": "el_exam_1", "student_id": "202610101",
            "answers": [
                {"question_id": "el_q_2", "answer": "A"},
                {"question_id": "el_q_1", "answer": "33.6L"},
            ],
        }, headers={"Authorization": f"Bearer {create_access_token('202610101', 'student')}"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["correct_count"] == 1            # 选择题同步判
        assert body["pending_semantic"] == 1         # 计算题待语义判定
        assert "semantic_grading" in enqueued

        db.expire(rec)
        assert rec.status.value == "grading"         # 首份考试结果 → grading 握手

        # 重复提交被拒
        r2 = client.post("/api/practice/submit", json={
            "practice_id": "el_exam_1", "student_id": "202610101",
            "answers": [{"question_id": "el_q_2", "answer": "B"}],
        }, headers={"Authorization": f"Bearer {create_access_token('202610101', 'student')}"})
        assert r2.status_code == 400
        assert "已提交" in r2.json()["detail"]

    def test_late_submit_rejected_after_exam_closed(self, env):
        """收卷后再提交：写侧与读侧同一生命周期收口，迟交答案不得并入已完成统计。"""
        client, db, rec, enqueued = env
        from app.models.database import Student, StudentAnswer
        db.add(Student(student_id="202610102", name="张浩宇",
                       class_id="class_2025_1", status="approved"))
        db.commit()
        lc.transition(db, rec, "completed")
        db.commit()

        r = client.post("/api/practice/submit", json={
            "practice_id": "el_exam_1", "student_id": "202610102",
            "answers": [{"question_id": "el_q_2", "answer": "A"}],
        }, headers={"Authorization": f"Bearer {create_access_token('202610102', 'student')}"})
        assert r.status_code == 400 and "已结束" in r.json()["detail"]
        assert db.query(StudentAnswer).filter_by(student_id="202610102").count() == 0


class TestLoopE2E:
    """闭环 e2e：布置（含主观题）→ 学生作答 → PENDING → 扫描判定 → 诊断触发。"""

    def test_full_loop(self, db_session, sample_student, monkeypatch):
        from app.models.database import (
            StudentAnswer,
        )
        from app.services import assignment_service as asvc, grading_center
        from app.jobs import handlers

        # 统一库：布置与判卷共享同一会话（db_session 即 conftest 会话）
        monkeypatch.setattr("app.models.database.get_db", lambda: iter([db_session]))
        monkeypatch.setattr("app.services.notification_service.get_db",
                            lambda: iter([db_session]))
        diagnosed = []
        monkeypatch.setattr(handlers, "diagnose_exam",
                            lambda db, eid: diagnosed.append(eid) or {"analyzed_count": 0})

        def fake_gen(kps, diff, n, rag_context=None, question_types=None):
            # 1 道选择 + 1 道主观（混合题型，验证语义判卷在主旅程被触达）
            types = question_types or ["choice"]
            out = []
            for i, t in enumerate(types[:n]):
                if t == "choice":
                    out.append({"content": f"选择{i}", "options": ["A", "B"], "answer": "A",
                                "analysis": "", "knowledge_points": ["kp"]})
                else:
                    out.append({"content": "配平 Fe+O2", "options": None,
                                "answer": "3Fe+2O2=Fe3O4", "analysis": "",
                                "knowledge_points": ["kp"]})
            return out
        monkeypatch.setattr(asvc, "_llm_generate", fake_gen)
        monkeypatch.setattr(asvc, "_audit_equation", lambda eq: {"overall_status": "passed"})
        monkeypatch.setattr(asvc, "_enqueue_assignment", lambda b, s: None)
        monkeypatch.setattr("app.jobs.enqueue_job", lambda t, p: None)

        # ① 布置（混合题型）
        out = asvc.assign(db_session, ["202610101"],
                          {"kind": "adaptive", "question_count": 2,
                           "question_types": ["choice", "fill"]})
        db_session.commit()
        assert out["results"][0]["question_count"] == 2
        record_id = out["results"][0]["record_id"]

        # ② 学生作答：选择对 + 主观错
        graded = grading_center.grade(
            [{"question_id": f"q_{record_id}_0", "answer": "A"},
             {"question_id": f"q_{record_id}_1", "answer": "随便写的"}],
            [{"question_id": f"q_{record_id}_0", "answer": "A"},
             {"question_id": f"q_{record_id}_1", "answer": "3Fe+2O2=Fe3O4"}],
            semantic=False)
        resolved = [q for q in graded["questions"] if not q.get("needs_semantic")]
        pending = [{"question_id": q["question_id"], "student_answer": q["student_answer"],
                    "is_correct": False, "reason": grading_center.PENDING_REASON}
                   for q in graded["questions"] if q.get("needs_semantic")]
        grading_center.save(db_session, resolved + pending, "202610101", record_id, "online",
                            trigger_diagnosis=False, upsert=True)
        db_session.commit()

        # ③ 扫描判定（假语义判定：判错）→ 诊断触发
        def fake_judge(unresolved):
            for q in unresolved:
                q["needs_semantic"] = False
                q["is_correct"] = False
                q["reason"] = "不等价"
        monkeypatch.setattr(grading_center, "_semantic_judge_batch", fake_judge)
        out_scan = handlers.scan_semantic_pending(db_session, record_id)
        db_session.commit()

        assert out_scan["judged"] == 1
        assert diagnosed == [record_id]              # 闭环最后一段：诊断被触发
        row = db_session.query(StudentAnswer).filter(
            StudentAnswer.student_id == "202610101",
            StudentAnswer.question_id == f"q_{record_id}_1").one()
        assert row.is_correct is False and row.grade_reason != "PENDING_SEMANTIC"


class TestSubmittedExamVisibility:
    """学生提交考试后，该考试必须留在任务列表里（grading/completed = 已完成分区）。"""

    def _student(self, db_session):
        s = Student(student_id="202610101", name="李雨萱", class_id="class_2025_1")
        db_session.add(s)
        db_session.commit()
        return s

    def _submit(self, db_session):
        from app.models.database import StudentAnswer
        db_session.add(StudentAnswer(
            answer_id="ans_vis_1", student_id="202610101", question_id="el_q_1",
            exam_record_id="el_exam_1", student_answer="22.4L", is_correct=True))
        db_session.commit()

    @pytest.mark.parametrize("close_status", ["grading", "completed"])
    def test_submitted_exam_stays_visible(self, db_session, exam, close_status):
        from app.api.practice import student_tasks
        student = self._student(db_session)
        lc.transition(db_session, exam, "published")
        lc.mark_started(db_session, exam)
        lc.transition(db_session, exam, "grading")
        if close_status == "completed":
            lc.transition(db_session, exam, "completed")
        db_session.commit()
        self._submit(db_session)

        tasks = student_tasks(db_session, student)
        assert [t["practice_id"] for t in tasks] == ["el_exam_1"]
        assert tasks[0]["submitted"] is True

    def test_unsubmitted_student_keeps_exam_while_grading(self, db_session, exam):
        """同班有人先交卷 → 考试转 grading，未交卷的同学还得能继续作答。"""
        from app.api.practice import student_tasks
        student = self._student(db_session)
        lc.transition(db_session, exam, "published")
        lc.transition(db_session, exam, "grading")
        db_session.commit()

        tasks = student_tasks(db_session, student)
        assert [t["practice_id"] for t in tasks] == ["el_exam_1"]
        assert tasks[0]["submitted"] is False

    def test_unsubmitted_closed_exam_hidden(self, db_session, exam):
        from app.api.practice import student_tasks
        student = self._student(db_session)
        lc.transition(db_session, exam, "published")
        lc.transition(db_session, exam, "grading")
        lc.transition(db_session, exam, "completed")
        db_session.commit()
        assert student_tasks(db_session, student) == []

    def test_draft_and_cancelled_exam_hidden(self, db_session, exam):
        from app.api.practice import student_tasks
        student = self._student(db_session)
        self._submit(db_session)                      # 已交卷的草稿也不给学生看
        assert student_tasks(db_session, student) == []

        lc.transition(db_session, exam, "published")
        lc.transition(db_session, exam, "cancelled")
        db_session.commit()
        assert student_tasks(db_session, student) == []

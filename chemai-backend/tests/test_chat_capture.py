"""对话作答回流（chat-answer-capture）测试。

tutor 工具：学生身份（服务端 contextvars）+ 预期答案具备时 → 判定经判卷中心
落库（source=chat，幂等按作答内容）；缺一即不捕获（诚实降级）。
诊断：chat 作答经学生级诊断作业纳入障碍聚合。
"""
import json
import pytest

import app.models.database as db_mod
from app.models.database import (
    Student, Question, Difficulty, QuestionSource, AuditStatus, StudentAnswer,
)
from app.services import grading_center
from agent.tools import tutoring
from agent.tools.context import set_current_student


@pytest.fixture
def env(db_session, monkeypatch):
    monkeypatch.setattr(db_mod, "get_db", lambda: iter([db_session]))
    monkeypatch.setattr("app.services.notification_service.get_db",
                        lambda: iter([db_session]))
    # 学生级诊断有专项测试（TestStudentDiagnosis）——捕获用例不触发真实诊断/LLM
    monkeypatch.setattr(grading_center, "_enqueue_student_diagnosis", lambda sid: "已屏蔽")
    db_session.add(Student(student_id="202610101", name="李雨萱", class_id="class_2025_1"))
    db_session.commit()
    return db_session


def _tutor():
    return tutoring.ionic_equation_tutor


class TestChatCapture:
    @pytest.mark.asyncio
    async def test_capture_on_step_answer(self, env, monkeypatch):
        """学生身份 + 预期答案 → 判定落库 source=chat，反馈含判定。"""
        set_current_student("202610101")

        def fake_judge(unresolved):
            for q in unresolved:
                q["is_correct"] = True
                q["reason"] = "等价"
        monkeypatch.setattr(grading_center, "_semantic_judge_batch", fake_judge)

        out = json.loads(await _tutor()(
            equation="CaCO3 + HCl →",
            student_input="CaCO3 + 2HCl = CaCl2 + H2O + CO2↑",
            expected_answer="CaCO3 + 2HCl = CaCl2 + H2O + CO2↑",
        ))
        env.commit()

        assert out["judgment"]["is_correct"] is True
        rows = env.query(StudentAnswer).filter(
            StudentAnswer.student_id == "202610101").all()
        assert len(rows) == 1
        assert rows[0].source.value == "chat"
        assert rows[0].is_correct is True
        assert rows[0].exam_record_id is None

    @pytest.mark.asyncio
    async def test_replay_same_answer_idempotent(self, env, monkeypatch):
        set_current_student("202610101")
        monkeypatch.setattr(grading_center, "_semantic_judge_batch",
                            lambda u: [q.update(is_correct=True) or q for q in u])
        kw = dict(equation="配平", student_input="2H2+O2=2H2O",
                  expected_answer="2H2+O2=2H2O")
        await _tutor()(**kw)
        await _tutor()(**kw)   # 重放
        env.commit()
        assert env.query(StudentAnswer).count() == 1

    @pytest.mark.asyncio
    async def test_new_attempt_new_row(self, env, monkeypatch):
        """同一学生换答案重做 = 新作答记录（不吞学情）。"""
        set_current_student("202610101")
        monkeypatch.setattr(grading_center, "_semantic_judge_batch",
                            lambda u: [q.update(is_correct=False) or q for q in u])
        await _tutor()(equation="配平", student_input="H2+O2=H2O",
                       expected_answer="2H2+O2=2H2O")
        await _tutor()(equation="配平", student_input="还是不会",
                       expected_answer="2H2+O2=2H2O")
        env.commit()
        assert env.query(StudentAnswer).count() == 2

    @pytest.mark.asyncio
    async def test_no_expected_answer_no_capture(self, env):
        """agent 给不出该步预期答案 → 不落库（无判定依据，诚实降级）。"""
        set_current_student("202610101")
        await _tutor()(equation="配平", student_input="随便答的")
        env.commit()
        assert env.query(StudentAnswer).count() == 0

    @pytest.mark.asyncio
    async def test_no_student_context_no_capture(self, env, monkeypatch):
        """无学生身份（教师端预览等）→ 不落库。"""
        set_current_student("")
        monkeypatch.setattr(grading_center, "_semantic_judge_batch",
                            lambda u: [q.update(is_correct=True) or q for q in u])
        await _tutor()(equation="配平", student_input="2H2+O2=2H2O",
                       expected_answer="2H2+O2=2H2O")
        env.commit()
        assert env.query(StudentAnswer).count() == 0


class TestStudentDiagnosis:
    """chat 作答经学生级诊断纳入障碍聚合。"""

    def test_diagnose_student_recent_covers_chat(self, db_session, monkeypatch):
        db_session.add(Student(student_id="202610101", name="李雨萱", class_id="class_2025_1"))
        db_session.add(Question(
            question_id="chat_q_1", record_id=None, content="配平 H2+O2",
            options=None, answer="2H2+O2=2H2O", analysis="", knowledge_points=[],
            difficulty=Difficulty.MEDIUM, source=QuestionSource.MANUAL_SELECTED,
            audit_status=AuditStatus.PASSED))
        from app.models.database import AnswerSource
        db_session.add(StudentAnswer(
            answer_id="chat_1", student_id="202610101", question_id="chat_q_1",
            exam_record_id=None, student_answer="H2+O2=H2O", is_correct=False,
            source=AnswerSource.CHAT))
        db_session.commit()

        from app.jobs import handlers

        from app.services.llm_service import LLMService

        def fake_diagnose(*a, **kw):
            return {"success": True, "content": '{"barrier_type": "concept"}'}
        # 补类不补单例实例——monkeypatch 对实例补丁的还原会把绑定方法写进实例字典，
        # 永久遮蔽类属性并污染同进程后续测试（诊断打到真 LLM 后撞列默认值）
        monkeypatch.setattr(LLMService, "diagnose_barrier_type", fake_diagnose)

        out = handlers.diagnose_student_recent(db_session, "202610101")
        db_session.commit()

        assert out["analyzed_count"] == 1
        row = db_session.query(StudentAnswer).filter_by(answer_id="chat_1").first()
        assert row.barrier_type is not None          # chat 错答被诊断标注
        student = db_session.query(Student).filter_by(student_id="202610101").first()
        assert student.barrier_type["concept"] == 1.0  # 聚合纳入 chat 作答

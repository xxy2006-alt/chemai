"""018 — assign_adaptive_practice 布置目标解析（evals）。

用户反馈「布置针对性练习反复需要批准、反复报错」：
- 工具原本只支持 class_id，用户说"给李世睿布置"时 LLM 传参困难 → 反复失败；
- 未提供任何目标时错误信息不友好。
本测试锁定：支持单学生（student_name 中文名/student_id）+ 班级 + 友好参数错误。
"""
import asyncio
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models.database as db_mod
from app.models.database import Base, Student


@pytest.fixture
def agent_db(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    def _fake_get_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    monkeypatch.setattr(db_mod, "get_db", _fake_get_db)
    return Session


@pytest.fixture(autouse=True)
def as_teacher_t1(agent_db):
    """布置工具的身份取服务端上下文：本文件统一以 t1（任教 class_2025_1）执行。"""
    from agent.tools.context import set_current_teacher
    from app.models.database import Account, TeacherClassSubject

    s = agent_db()
    s.add(Account(account_id="acc_t1", username="t1_user", role="teacher",
                  teacher_id="t1", password_hash="x"))
    s.add(TeacherClassSubject(id="tcs_scope", teacher_id="t1",
                              class_id="class_2025_1", subject="化学"))
    s.commit()
    s.close()
    set_current_teacher("t1")
    yield
    set_current_teacher("")


def _run(coro):
    return asyncio.run(coro)


def _seed_students(Session):
    s = Session()
    s.add(Student(student_id="202610201", name="李世睿", class_id="class_2025_1",
                  status="approved", barrier_type={"concept": 0.8, "reading": 0.15, "expression": 0.05}))
    s.add(Student(student_id="202610101", name="张浩宇", class_id="class_2025_1",
                  status="approved", barrier_type={"concept": 0.3, "reading": 0.3, "expression": 0.4}))
    s.commit()
    s.close()


def _mock_llm(monkeypatch):
    """mock llm_service.generate_questions 返回成功，避免真实调用"""
    from app.services.llm_service import llm_service as real_svc

    class _FakeLLM:
        def generate_questions(self, **kwargs):
            return {"success": True, "content": json.dumps({"questions": [{"content": "x", "answer": "A"}]})}
    monkeypatch.setattr(real_svc, "generate_questions", _FakeLLM().generate_questions)


def test_assign_by_student_name(agent_db, monkeypatch):
    """按中文姓名（李世睿）布置 → 成功且 assigned_count=1"""
    from agent.tools.diagnosis import assign_adaptive_practice

    _seed_students(agent_db)
    _mock_llm(monkeypatch)
    out = json.loads(_run(assign_adaptive_practice(student_name="李世睿", question_count=3)))
    assert out.get("assigned_count") == 1
    assert out["assigned"][0]["student_name"] == "李世睿"


def test_assign_by_student_id(agent_db, monkeypatch):
    """按学号（202610201）布置 → 成功"""
    from agent.tools.diagnosis import assign_adaptive_practice

    _seed_students(agent_db)
    _mock_llm(monkeypatch)
    out = json.loads(_run(assign_adaptive_practice(student_id="202610201", question_count=3)))
    assert out.get("assigned_count") == 1


def test_assign_by_class(agent_db, monkeypatch):
    """按班级布置 → 覆盖该班学生"""
    from agent.tools.diagnosis import assign_adaptive_practice

    _seed_students(agent_db)
    _mock_llm(monkeypatch)
    out = json.loads(_run(assign_adaptive_practice(class_id="class_2025_1", question_count=2)))
    assert out.get("assigned_count") == 2


def test_assign_no_target_returns_friendly_error(agent_db):
    """未提供任何目标 → 明确参数引导（而不是"班级 无学生"）"""
    from agent.tools.diagnosis import assign_adaptive_practice

    _seed_students(agent_db)
    out = json.loads(_run(assign_adaptive_practice()))
    assert "error" in out
    assert "student_name" in out["error"] or "class_id" in out["error"]


def test_assign_unknown_student_returns_error(agent_db):
    """未知学生 → 明确错误"""
    from agent.tools.diagnosis import assign_adaptive_practice

    _seed_students(agent_db)
    out = json.loads(_run(assign_adaptive_practice(student_name="不存在的人")))
    assert "error" in out
    assert "未找到学生" in out["error"]


def test_request_approval_only_interrupts_once(monkeypatch):
    """同一次调用内已批准后，LLM 再次 request_approval 不再中断（防反复需要批准）。

    2026-08 read 卡死修复后语义：approved 只由 resume 返回值置位——
    取消不得留下已批准状态（7a3ae89 安全语义）。"""
    import agent.guard as guard_mod

    interrupted = []
    def _fake_interrupt(payload):  # LangGraph interrupt 是同步调用
        interrupted.append(payload)
        return "approved"  # 模拟用户批准后 resume 返回的值

    gs = guard_mod.GuardState()
    monkeypatch.setattr("langgraph.types.interrupt", _fake_interrupt)

    tool = guard_mod._make_request_approval_tool(gs)
    # 第一次：批准（resume 值 approved）→ 置位
    r1 = _run(tool.ainvoke({"message": "确认布置"}))
    assert r1 == "approved"
    assert len(interrupted) == 1
    assert gs.approved is True
    # 第二次：不再中断，直接返回
    r2 = _run(tool.ainvoke({"message": "再次确认"}))
    assert r2 == "already approved"
    assert len(interrupted) == 1


def test_request_approval_cancel_does_not_approve(monkeypatch):
    """取消（resume 值 cancelled）不得置位 approved，并返回终止提示（防反复审批）。"""
    import agent.guard as guard_mod

    interrupted = []
    def _fake_interrupt(payload):
        interrupted.append(payload)
        return "cancelled"

    gs = guard_mod.GuardState()
    monkeypatch.setattr("langgraph.types.interrupt", _fake_interrupt)

    tool = guard_mod._make_request_approval_tool(gs)
    r1 = _run(tool.ainvoke({"message": "确认布置"}))
    # 2026-09-21 文案契约分离：取消文案中性化（无祈使句，防 LLM 鹦鹉学舌）
    assert "取消" in r1 and "请勿" not in r1, r1
    assert gs.approved is False
    assert len(interrupted) == 1


def test_assign_rejects_out_of_scope_targets(agent_db, monkeypatch):
    """越界布置：别班学生 / 别班班级一律拒绝（与 HTTP /assign 的 allows_class 同口径）。"""
    from agent.tools.diagnosis import assign_adaptive_practice

    _seed_students(agent_db)
    s = agent_db()
    s.add(Student(student_id="202699999", name="别班同学", class_id="c_other",
                  status="approved"))
    s.commit()
    s.close()
    _mock_llm(monkeypatch)

    by_id = json.loads(_run(assign_adaptive_practice(student_id="202699999", question_count=1)))
    assert "无权" in by_id["error"]

    by_name = json.loads(_run(assign_adaptive_practice(student_name="别班同学", question_count=1)))
    assert "无权" in by_name["error"]

    by_class = json.loads(_run(assign_adaptive_practice(class_id="c_other", question_count=1)))
    assert "无权" in by_class["error"]


def test_assign_rejects_identity_less_session(agent_db, monkeypatch):
    """无教师身份（学生 token 自报 teacher persona）拿不到布置能力。"""
    from agent.tools.context import set_current_teacher
    from agent.tools.diagnosis import assign_adaptive_practice

    _seed_students(agent_db)
    _mock_llm(monkeypatch)
    set_current_teacher("202610201")          # 学生学号，不是员工身份
    try:
        out = json.loads(_run(assign_adaptive_practice(student_name="李雨萱", question_count=1)))
    finally:
        set_current_teacher("t1")
    assert "error" in out

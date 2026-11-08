"""发送确认门（2026-08 用户确认方案；ADR-0013 改造）：
- send_report_to_parent 仍走 elevation 一次性放行；send_learning_plan 的门
  已实体化为草稿状态（learning_plan_drafts.teacher_approved），提权布尔退役
- 自然语言确认（打字"同意/发吧"=批准；草稿门开着时其他文字=打回+反馈）
- 确认卡 action/draft_id 标记驱动前端三值按钮
- 数据门行为细则见 test_plan_confirmation.py（service 接缝）
"""
import asyncio
import json

# 这些用例走真实 chemai.db（工具路径 get_db 默认引擎）；
# 显式建表与应用启动的 create_all 同约定（新检出目录直接可跑）
from app.models.database import Base, engine as _default_engine

Base.metadata.create_all(_default_engine)

from agent.guard import GuardState, is_confirmation, _make_guarded_tool
from agent.tools.diagnosis import send_learning_plan, send_report_to_parent
from agent.tools.filesystem import set_elevate_once
from agent.langgraph_sse_v2 import LangGraphSSEAdapterV2


def _run(coro):
    async def go():
        return await coro

    return asyncio.run(go())


# ── 自然语言确认判断 ──

def test_is_confirmation_words():
    for w in ["同意", "发吧", "可以", "好", "发送", "OK", "那就发吧", "同意发送", "没问题"]:
        assert is_confirmation(w), f"应为确认: {w!r}"


def test_is_confirmation_rejects_modification():
    for w in ["把第3题换掉再发", "难度改成简单", "先不要发", "", "你好"]:
        assert not is_confirmation(w), f"不应为确认: {w!r}"


# ── 发送工具确认门 ──

def _seed_scope_env(monkeypatch, request=None):
    if request is not None:
        # contextvar 会跨测试泄漏（pytest 同线程），结束时限时还原
        request.addfinalizer(lambda: __import__(
            "agent.tools.context", fromlist=["set_current_teacher"]
        ).set_current_teacher(""))
    """范围校验（确认卡之前）需要可用会话：内存库 + 最小学生数据。"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    import app.models.database as db_mod
    from app.models.database import Base, Student

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    from app.models.database import (
        Account, Teacher, Grade, Class, TeacherClassSubject, Student,
    )
    session.add(Account(account_id="acc_t1", role="teacher", username="t1",
                        password_hash="x", teacher_id="t1", status="active"))
    session.add(Teacher(teacher_id="t1", name="海老师", school_id="school1",
                        status="approved"))
    session.add(Grade(grade_id="g1", school_id="school1", name="高一", year=2026))
    session.add(Class(class_id="class_2025_1", name="一班", grade="高一",
                      grade_id="g1", subject="化学"))
    session.add(TeacherClassSubject(id="tcs1", teacher_id="t1",
                                    class_id="class_2025_1", subject="化学"))
    session.add(Student(student_id="202610101", name="李雨萱",
                        class_id="class_2025_1", status="approved"))
    session.commit()
    monkeypatch.setattr(db_mod, "get_db", lambda: iter([session]))
    import agent.tools.diagnosis as diag
    monkeypatch.setattr(diag, "get_db", lambda: iter([session]), raising=False)
    # 教师上下文（scope 校验按 current_teacher 解析身份）
    from agent.tools.context import set_current_teacher
    set_current_teacher("t1")
    return session


def test_send_learning_plan_requires_approval_first(monkeypatch, request):
    """无 elevation：返回 approval_needed + action=send_student，不发真实请求。"""
    _seed_scope_env(monkeypatch, request)
    out = json.loads(_run(send_learning_plan(student_id="202610101")))
    assert out.get("approval_needed") is True
    assert out.get("action") == "send_student"
    assert "202610101" in out.get("message", "")


def test_send_report_to_parent_requires_approval_first(monkeypatch, request):
    _seed_scope_env(monkeypatch, request)
    out = json.loads(_run(send_report_to_parent(student_id="202610101")))
    assert out.get("approval_needed") is True
    assert out.get("action") == "send_parent"


def test_send_learning_plan_gate_is_data_not_elevation(monkeypatch):
    """ADR-0013：send_learning_plan 的门由草稿状态强制——elevation 不再放行发送。
    无确认草稿时依旧弹门（approval_needed），即使进程级提权布尔已置位。"""
    from agent.tools.filesystem import _consume_elevation
    set_elevate_once()
    try:
        out = json.loads(_run(send_learning_plan(student_id="no_such_student_999")))
    finally:
        _consume_elevation()
    assert out.get("approval_needed") is True, "提权布尔不得越过草稿数据门"


def test_send_learning_plan_denies_out_of_scope_teacher(monkeypatch):
    """声明了 teacher_id 的发送：Data Scope 不含该生 → 拒绝（fail-closed）。"""
    monkeypatch.setattr("agent.tools.context.current_teacher", lambda: "ghost_teacher")
    out = json.loads(_run(send_learning_plan(student_id="202610101", teacher_id="ghost_teacher")))
    # ghost_teacher 不教任何班 → Data Scope 拒绝；不得退化为弹确认门
    assert "Data Scope" in out.get("error", ""), f"应 Data Scope 拒绝: {out}"
    assert "approval_needed" not in out


def test_guard_replays_pending_send():
    """guard 层：send 工具 approval_needed → 登记 pending → 批准重放（消费 elevation）。"""
    calls = []

    async def fake_send(student_id: str = ""):
        """Fake send tool needing confirmation."""
        calls.append(student_id)
        from agent.tools.filesystem import _consume_elevation
        if not _consume_elevation():
            return json.dumps({"approval_needed": True, "message": "请确认", "action": "send_student"})
        return json.dumps({"result": "已发送", "student_id": student_id})

    gs = GuardState()
    guarded = _make_guarded_tool(fake_send, gs)
    first = json.loads(_run(guarded.ainvoke({"student_id": "s1"})))
    assert first.get("approval_needed") is True
    assert gs.pending_approval is not None
    # 模拟批准：重放（与 _direct_replay_events 相同语义）
    gs.approved = True
    set_elevate_once()
    from agent.channel.langgraph_channel import _direct_replay_events
    events, _replay_info = _run(_direct_replay_events(gs, True))
    evt = json.loads(events[0])
    assert evt["type"] == "tool_result"
    assert json.loads(evt["result"])["result"] == "已发送"


# ── adapter：确认卡带 action ──

def test_adapter_awaiting_approval_carries_action():
    adapter = LangGraphSSEAdapterV2()
    payload = json.dumps({
        "approval_needed": True,
        "message": "即将把内容发送给学生 202610101",
        "target": "202610101",
        "action": "send_student",
    }, ensure_ascii=False)
    events = adapter.feed({
        "event": "on_tool_end",
        "name": "send_learning_plan",
        "data": {"output": f"content='{payload}' name='send_learning_plan' tool_call_id='call_1'"},
    })
    phases = [json.loads(o) for o in events if json.loads(o).get("type") == "phase"]
    assert phases[-1]["phase"] == "awaiting_approval"
    assert phases[-1]["action"] == "send_student"


# ── 生成即门（#13 冒烟补丁）：草稿生成成功即登记发送调用 ──

def test_generate_draft_registers_send_gate():
    """生成即门：generate_learning_plan 带 approval_needed+draft_id 返回时，
    guard 登记的是 send_learning_plan 调用（生成不可重放）。"""
    calls = []

    async def fake_generate(student_id: str = "", student_name: str = ""):
        """Fake draft generator with gate-open payload."""
        calls.append(student_id)
        return json.dumps({
            "message": "已生成草稿", "approval_needed": True,
            "message_gate": "学习计划（第 1 版）等待老师确认",
            "target": student_id, "action": "send_student",
            "student_id": student_id, "draft_id": "d-gen-1", "version": 1,
            "plan": {"plan_title": "t"},
        })

    fake_generate.__name__ = "generate_learning_plan"  # guard 按工具名路由
    gs = GuardState()
    guarded = _make_guarded_tool(fake_generate, gs)
    out = json.loads(_run(guarded.ainvoke({"student_id": "s9"})))
    assert out.get("approval_needed") is True
    assert gs.pending_approval is not None
    assert gs.pending_approval["name"] == "send_learning_plan", "应登记发送调用而非生成"
    assert gs.pending_approval["kwargs"]["draft_id"] == "d-gen-1"
    assert len(calls) == 1, "生成只执行一次（不可重放）"


def test_generate_draft_already_approved_never_regenerates():
    """同回合已批准过另一门：生成即门仍不得重放生成。"""
    calls = []

    async def fake_generate(student_id: str = ""):
        """Fake draft generator with gate-open payload."""
        calls.append(student_id)
        return json.dumps({
            "message": "已生成", "approval_needed": True, "message_gate": "等待确认",
            "action": "send_student", "student_id": student_id,
            "draft_id": "d-gen-2", "version": 1, "plan": {},
        })

    fake_generate.__name__ = "generate_learning_plan"
    gs = GuardState()
    gs.approved = True  # 同回合此前批准过
    guarded = _make_guarded_tool(fake_generate, gs)
    out = json.loads(_run(guarded.ainvoke({"student_id": "s9"})))
    assert len(calls) == 1, "已批准状态不得触发生成重放"
    assert gs.pending_approval and gs.pending_approval["name"] == "send_learning_plan"

"""确认门三值决定闭环测试（ADR-0013 最高接缝）。

直接驱动 channel 的 _gate_decision_stream（/resume decision 分支与 /stream
反馈路由共用的组合点）：假 agent 续接 + 真实 service + 内存库，断言
批准（重放发送→草稿 sent→通知→run 推进）、打回（修订→v2 面板→重开门）、
放弃（步取消→草稿保留→运行继续）三条分支的事件序列与落库结果。
"""
import asyncio
import json
from types import SimpleNamespace

import pytest

from app.models.database import (
    LearningPlanDraft, Student, StudentNotification, TeacherClassSubject,
)
from app.services.plan_draft_service import plan_draft_service as draft_svc
from app.services.plan_run_service import plan_run_service as run_svc

PLAN = {"plan_title": "张三计划", "weekly_goals": ["盐类水解"]}


@pytest.fixture
def env(db_session, monkeypatch):
    """内存库 + get_db 重定向 + 假教师身份 + 假 agent。"""
    db_session.add(Student(student_id="s1", name="张三", class_id="c1", status="approved"))
    db_session.add(TeacherClassSubject(id=1, teacher_id="t1", class_id="c1", subject="chemistry"))
    db_session.commit()

    import app.models.database as dbmod
    def _fake_get_db():
        yield db_session
    monkeypatch.setattr(dbmod, "get_db", _fake_get_db)
    monkeypatch.setattr("agent.tools.context.current_teacher", lambda: "t1")

    import sys
    mod = sys.modules["app.services.llm_service"]
    monkeypatch.setattr(mod.llm_service, "generate_learning_plan",
                        lambda **kw: {"success": True, "content": json.dumps(PLAN, ensure_ascii=False)})
    monkeypatch.setattr(mod.llm_service, "revise_learning_plan",
                        lambda **kw: {"success": True, "content": json.dumps(
                            {**PLAN, "plan_title": "张三计划v2"}, ensure_ascii=False)})

    return db_session


class FakeAgent:
    """续接回合的假 agent：astream_events 吐一小段文本即结束。"""

    async def aget_state(self, config):
        return SimpleNamespace(values={"messages": []}, next=())

    async def astream_events(self, _input, _config, version="v2"):
        yield {"event": "on_chat_model_stream", "name": "llm",
               "data": {"chunk": SimpleNamespace(content="已按意见修订")}}


def _gate(guard, draft_id, student_id="s1"):
    """登记待批发送（等价 guard 拦截 approval_needed 时的登记）。"""
    from agent.tools.diagnosis import send_learning_plan
    guard.pending_approval = {
        "name": "send_learning_plan", "fn": send_learning_plan,
        "kwargs": {"student_id": student_id, "draft_id": draft_id},
    }


def _collect(gen):
    async def go():
        return [ev async for ev in gen]
    return asyncio.run(go())


def _events_of_kinds(events, *kinds):
    out = []
    for e in events:
        raw = e[len("data: "):] if e.startswith("data: ") else e
        raw = raw.strip()
        if raw in ("[DONE]", ""):
            continue
        try:
            d = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        if d.get("type") in kinds:
            out.append(d)
    return out


def _real_adapter():
    from agent.langgraph_sse_v2 import LangGraphSSEAdapterV2
    return LangGraphSSEAdapterV2()


def _make_guard_with_plan(step_status="awaiting_confirmation"):
    from agent.guard import GuardState
    g = GuardState()
    g.plan_steps = [
        {"step": 1, "skill": "generate_learning_plan", "description": "生成", "status": "completed"},
        {"step": 2, "skill": "send_learning_plan", "description": "发送", "status": step_status},
        {"step": 3, "skill": "weekly_report", "description": "周报", "status": "pending"},
    ]
    return g


# ── approve：重放发送，闭环收口 ─────────────────────────────────

def test_approve_replays_send_and_completes_step(env):
    d = draft_svc.create_draft(env, "s1", created_by="t1")
    run_svc.start_run(env, "conv1", "goal", [
        {"step": 1, "skill": "generate_learning_plan", "status": "completed"},
        {"step": 2, "skill": "send_learning_plan", "status": "awaiting_confirmation"},
    ])
    guard = _make_guard_with_plan()
    _gate(guard, d["draft_id"])

    from agent.channel.langgraph_channel import _gate_decision_stream
    from agent.tools.filesystem import _consume_elevation
    try:
        events = _collect(_gate_decision_stream(
            "conv1", {"action": "approve", "feedback": "", "draft_id": d["draft_id"]},
            guard, FakeAgent(), _real_adapter(),
            {"configurable": {"thread_id": "conv1"}, "recursion_limit": 24}))
    finally:
        # 重放路径会置进程级 elevation（parent 报告门仍在用），清理防跨文件泄漏
        _consume_elevation()

    tool_results = _events_of_kinds(events, "tool_result")
    assert tool_results and tool_results[0]["success"] is True
    assert any(e.get("status") == "completed" and e.get("current_step") == 2
               for e in _events_of_kinds(events, "plan_progress"))
    assert events[-1] == "data: [DONE]\n\n"
    # 落库：草稿 sent + 学生收件箱通知
    assert draft_svc.get_draft(env, d["draft_id"])["status"] == "sent"
    assert env.query(StudentNotification).count() == 1
    run = run_svc.get_active_run(env, "conv1")
    assert run is None or all(s["status"] != "awaiting_confirmation" for s in run["steps"])


# ── reject：确定性修订 → v2 面板 → 重开门 ───────────────────────

def test_reject_revises_and_reopens_gate(env):
    d = draft_svc.create_draft(env, "s1", created_by="t1")
    guard = _make_guard_with_plan()
    _gate(guard, d["draft_id"])

    from agent.channel.langgraph_channel import _gate_decision_stream
    events = _collect(_gate_decision_stream(
        "conv1", {"action": "reject", "feedback": "第二周改成盐类水解专题", "draft_id": ""},
        guard, FakeAgent(), _real_adapter(),
        {"configurable": {"thread_id": "conv1"}, "recursion_limit": 24}))

    # 事件序列：revising → component(v2) → 门卡(draft_id) → awaiting_confirmation → 文本 → done
    progresses = _events_of_kinds(events, "plan_progress")
    assert progresses and progresses[0]["status"] == "revising"
    comps = _events_of_kinds(events, "component")
    assert comps and comps[0]["component"] == "learning_plan"
    assert comps[0]["params"]["data"]["plan"]["plan_title"] == "张三计划v2"
    gates = _events_of_kinds(events, "gate_open")
    gate = [g for g in gates if g.get("draft_id") == d["draft_id"]]
    assert gate and gate[-1]["version"] == 2
    assert gate[-1]["gate_id"] == f"g-draft-{d['draft_id']}"
    assert gate[-1]["recipient"] == "student"
    assert progresses[-1]["status"] == "awaiting_confirmation"
    texts = _events_of_kinds(events, "text")
    assert texts, "打回后 LLM 应说明修改点"
    # 落库：v2 带反馈；门重新挂上同一草稿
    v2 = draft_svc.get_draft(env, d["draft_id"])
    assert v2["version"] == 2 and v2["feedback"] == "第二周改成盐类水解专题"
    assert v2["teacher_approved"] is False
    assert guard.pending_approval and guard.pending_approval["kwargs"]["draft_id"] == d["draft_id"]
    assert events[-1] == "data: [DONE]\n\n"


def test_reject_without_feedback_errors(env):
    d = draft_svc.create_draft(env, "s1")
    guard = _make_guard_with_plan()
    _gate(guard, d["draft_id"])
    from agent.channel.langgraph_channel import _gate_decision_stream
    events = _collect(_gate_decision_stream(
        "conv1", {"action": "reject", "feedback": "", "draft_id": ""},
        guard, FakeAgent(), _real_adapter(),
        {"configurable": {"thread_id": "conv1"}, "recursion_limit": 24}))
    errs = _events_of_kinds(events, "error")
    assert errs and "修改意见" in errs[0]["message"]
    assert draft_svc.get_draft(env, d["draft_id"])["version"] == 1


# ── abandon：步取消、运行继续、草稿保留 ─────────────────────────

def test_abandon_cancels_step_run_continues(env):
    d = draft_svc.create_draft(env, "s1")
    run_svc.start_run(env, "conv1", "goal", [
        {"step": 2, "skill": "send_learning_plan", "status": "awaiting_confirmation"},
        {"step": 3, "skill": "weekly_report", "status": "pending"},
    ])
    guard = _make_guard_with_plan()
    _gate(guard, d["draft_id"])

    from agent.channel.langgraph_channel import _gate_decision_stream
    events = _collect(_gate_decision_stream(
        "conv1", {"action": "abandon", "feedback": "", "draft_id": ""},
        guard, FakeAgent(), _real_adapter(),
        {"configurable": {"thread_id": "conv1"}, "recursion_limit": 24}))

    progresses = _events_of_kinds(events, "plan_progress")
    assert any(e.get("status") == "cancelled" for e in progresses)
    assert _events_of_kinds(events, "text"), "放弃后 LLM 应说明并继续"
    assert events[-1] == "data: [DONE]\n\n"
    # 草稿保留待确认；待批已释放；run 继续走
    assert draft_svc.get_draft(env, d["draft_id"])["status"] == "awaiting_confirmation"
    assert guard.pending_approval is None
    run = run_svc.get_active_run(env, "conv1")
    assert run and run["status"] == "running"


# ── 协议归一：decision 对象优先，旧字符串向后兼容 ────────────────

def test_normalize_decision_compat():
    from agent.channel.langgraph_channel import _normalize_decision

    class R:
        def __init__(self, message="", decision=None):
            self.message = message
            self.decision = decision

    assert _normalize_decision(R(decision={"action": "reject", "feedback": "改"})) == {
        "action": "reject", "feedback": "改", "draft_id": "", "gate_id": ""}
    assert _normalize_decision(R(message="approved"))["action"] == "approve"
    assert _normalize_decision(R(message="cancelled"))["action"] == "abandon"
    # ADR-0015：中文确认词白名单已废止——打字永不构成批准，协议值只剩
    # approved/cancelled；「批准」不再映射 approve。
    assert _normalize_decision(R(message="批准")) is None
    # decision 对象携带 gate_id（强绑定键）原样透传
    d = _normalize_decision(R(decision={"action": "approve", "gate_id": "g-draft-x"}))
    assert d["gate_id"] == "g-draft-x"
    assert _normalize_decision(R(message="随便聊聊")) is None
    # decision 对象优先于 message 字符串
    assert _normalize_decision(R(message="approved", decision={"action": "abandon"}))["action"] == "abandon"


# ── fail-closed：身份与 Data Scope（ADR-0009）──────────────────

def test_approve_without_identity_denied(env, monkeypatch):
    d = draft_svc.create_draft(env, "s1")
    guard = _make_guard_with_plan()
    _gate(guard, d["draft_id"])
    monkeypatch.setattr("agent.tools.context.current_teacher", lambda: "")
    from agent.channel.langgraph_channel import _gate_decision_stream
    events = _collect(_gate_decision_stream(
        "conv1", {"action": "approve", "feedback": "", "draft_id": d["draft_id"]},
        guard, FakeAgent(), _real_adapter(),
        {"configurable": {"thread_id": "conv1"}, "recursion_limit": 24}))
    errs = _events_of_kinds(events, "error")
    assert errs and "缺少教师身份" in errs[0]["message"]
    assert draft_svc.get_draft(env, d["draft_id"])["teacher_approved"] is False


def test_reject_out_of_scope_teacher_denied(env, monkeypatch):
    """老师不教该生所在班 → 打回被拒（fail-closed）。"""
    d = draft_svc.create_draft(env, "s1")
    guard = _make_guard_with_plan()
    _gate(guard, d["draft_id"])
    monkeypatch.setattr("agent.tools.context.current_teacher", lambda: "ghost")
    from agent.channel.langgraph_channel import _gate_decision_stream
    events = _collect(_gate_decision_stream(
        "conv1", {"action": "reject", "feedback": "改", "draft_id": d["draft_id"]},
        guard, FakeAgent(), _real_adapter(),
        {"configurable": {"thread_id": "conv1"}, "recursion_limit": 24}))
    errs = _events_of_kinds(events, "error")
    assert errs and "Data Scope" in errs[0]["message"]
    assert draft_svc.get_draft(env, d["draft_id"])["version"] == 1


def test_approve_conflict_with_already_sent_draft(env):
    """双通道冲突：草稿已被 REST 侧确认发送 → 聊天门批准显式报错，不重放。"""
    d = draft_svc.create_draft(env, "s1")
    draft_svc.record_decision(env, d["draft_id"], "approve", "t1")
    draft_svc.send_draft(env, "s1", d["draft_id"], "t1")
    guard = _make_guard_with_plan()
    _gate(guard, d["draft_id"])
    from agent.channel.langgraph_channel import _gate_decision_stream
    from agent.tools.filesystem import _consume_elevation
    try:
        events = _collect(_gate_decision_stream(
            "conv1", {"action": "approve", "feedback": "", "draft_id": d["draft_id"]},
            guard, FakeAgent(), _real_adapter(),
            {"configurable": {"thread_id": "conv1"}, "recursion_limit": 24}))
    finally:
        _consume_elevation()
    errs = _events_of_kinds(events, "error")
    assert errs and ("已确认发送给学生" in errs[0]["message"] or "不能处理决定" in errs[0]["message"])
    tool_results = _events_of_kinds(events, "tool_result")
    assert not tool_results, "草稿已 sent 不得重放发送"


# ── 门卡 DB 重同步（重启后纯 DB 依据）─────────────────────────

def test_gate_resync_from_run_steps_after_restart(env, monkeypatch):
    """/chat/history 的门解析不依赖内存 guard：run 步骤的 gate_draft_id 可重建门卡。"""
    run_svc.start_run(env, "conv9", "goal", [
        {"step": 1, "skill": "generate_learning_plan", "status": "completed"},
        {"step": 2, "skill": "send_learning_plan", "status": "awaiting_confirmation"},
    ])
    d = draft_svc.create_draft(env, "s1")
    run_svc.mark_step(env, "conv9", 2, "awaiting_confirmation", gate_draft_id=d["draft_id"])

    # 模拟重启：内存 guard 缓存为空
    monkeypatch.setattr("agent.channel.langgraph_channel._guard_state_cache", {})

    from agent.channel.conversation import _active_run_payload
    payload = _active_run_payload(env, "conv9")
    assert payload["gate"], "重启后门卡必须能从 DB 重建"
    assert payload["gate"]["draft_id"] == d["draft_id"]
    assert payload["gate"]["version"] == 1


# ── 家长报告门（issue #12：第二个工件走同一三值协议）─────────────

def _gate_report(guard, draft_id, student_id="s1"):
    from agent.tools.diagnosis import send_report_to_parent
    guard.pending_approval = {
        "name": "send_report_to_parent", "fn": send_report_to_parent,
        "kwargs": {"student_id": student_id, "draft_id": draft_id},
    }


def test_report_gate_approve_replays_send(env):
    from app.models.database import Parent, StudentParentBinding
    env.add(Parent(parent_id="p1", name="家长一", password_hash="x"))
    env.add(StudentParentBinding(binding_id=1, student_id="s1", parent_id="p1",
                                 status="active", bind_code="bc1"))
    env.commit()
    from app.services.parent_report_draft_service import parent_report_draft_service as rsvc
    d = rsvc.create_draft(env, "s1", created_by="t1")
    rsvc.record_decision(env, d["draft_id"], "approve", "t1")
    guard = _make_guard_with_plan()
    _gate_report(guard, d["draft_id"])
    from agent.channel.langgraph_channel import _gate_decision_stream
    from agent.tools.filesystem import _consume_elevation
    try:
        events = _collect(_gate_decision_stream(
            "conv1", {"action": "approve", "feedback": "", "draft_id": d["draft_id"]},
            guard, FakeAgent(), _real_adapter(),
            {"configurable": {"thread_id": "conv1"}, "recursion_limit": 24}))
    finally:
        _consume_elevation()
    tool_results = _events_of_kinds(events, "tool_result")
    assert tool_results and tool_results[0]["name"] == "send_report_to_parent"
    assert tool_results[0]["success"] is True
    assert rsvc.get_draft(env, d["draft_id"])["status"] == "sent"


def test_report_gate_reject_revises_and_reopens(env, monkeypatch):
    import sys
    mod = sys.modules["app.services.llm_service"]
    monkeypatch.setattr(mod.llm_service, "revise_parent_report",
                        lambda **kw: {"success": True, "report": {"suggestion": "已按意见改写"}})
    from app.services.parent_report_draft_service import parent_report_draft_service as rsvc
    d = rsvc.create_draft(env, "s1", created_by="t1")
    guard = _make_guard_with_plan()
    _gate_report(guard, d["draft_id"])
    from agent.channel.langgraph_channel import _gate_decision_stream
    events = _collect(_gate_decision_stream(
        "conv1", {"action": "reject", "feedback": "弱化排名表述", "draft_id": ""},
        guard, FakeAgent(), _real_adapter(),
        {"configurable": {"thread_id": "conv1"}, "recursion_limit": 24}))
    comps = _events_of_kinds(events, "component")
    assert comps and comps[0]["component"] == "parent_report"
    assert comps[0]["params"]["data"]["report_data"]["suggestion"] == "已按意见改写"
    gates = _events_of_kinds(events, "gate_open")
    gate = [g for g in gates if g.get("draft_id") == d["draft_id"]]
    assert gate and gate[0]["action"] == "send_parent"
    assert gate[0]["recipient"] == "parent"
    v2 = rsvc.get_draft(env, d["draft_id"])
    assert v2["version"] == 2 and v2["feedback"] == "弱化排名表述"
    assert guard.pending_approval and guard.pending_approval["kwargs"]["draft_id"] == d["draft_id"]


# ── 会话门映射：裸生成门重启后从 DB 重建（#13 冒烟补丁 2）────────

def test_gate_resync_without_run_via_conversation_gate(env, monkeypatch):
    """无 run 的裸生成门：gate 实体记录后，重启（缓存清空）仍能重建。"""
    d = draft_svc.create_draft(env, "s1")
    from app.services.gate_service import gate_service
    gate_service.open_gate(env, "conv-bare", kind="draft",
                           tool_name="send_learning_plan",
                           kwargs={"student_id": "s1", "draft_id": d["draft_id"]},
                           draft_id=d["draft_id"], version=d["version"],
                           action="send_student", message="等待确认")

    monkeypatch.setattr("agent.channel.langgraph_channel._guard_state_cache", {})
    from agent.channel.conversation import _active_run_payload
    payload = _active_run_payload(env, "conv-bare")
    assert payload["gate"], "裸生成门重启后必须能从 gate 实体重建"
    assert payload["gate"]["draft_id"] == d["draft_id"]
    assert payload["gate"]["action"] == "send_student"


def test_gate_mapping_self_heals_when_sent(env, monkeypatch):
    """草稿已 sent → 门映射读时自愈清除，不再重开门卡。"""
    d = draft_svc.create_draft(env, "s1")
    from app.services.plan_run_service import plan_run_service
    plan_run_service.record_gate(env, "conv-heal", d["draft_id"], "learning_plan")
    draft_svc.record_decision(env, d["draft_id"], "approve", "t1")
    draft_svc.send_draft(env, "s1", d["draft_id"], "t1")

    monkeypatch.setattr("agent.channel.langgraph_channel._guard_state_cache", {})
    from agent.channel.conversation import _active_run_payload
    payload = _active_run_payload(env, "conv-heal")
    assert payload["gate"] is None, "已发送的草稿不得再开卡"


def test_report_gate_mapping_artifact_aware(env, monkeypatch):
    """报告门的映射重建带 send_parent 动作与报告文案。"""
    from app.services.parent_report_draft_service import parent_report_draft_service as rsvc
    d = rsvc.create_draft(env, "s1")
    from app.services.gate_service import gate_service
    gate_service.open_gate(env, "conv-rep", kind="draft",
                           tool_name="send_report_to_parent",
                           kwargs={"student_id": "s1", "draft_id": d["draft_id"]},
                           draft_id=d["draft_id"], version=d["version"],
                           action="send_parent", message="学习报告等待确认")

    monkeypatch.setattr("agent.channel.langgraph_channel._guard_state_cache", {})
    from agent.channel.conversation import _active_run_payload
    payload = _active_run_payload(env, "conv-rep")
    assert payload["gate"] and payload["gate"]["action"] == "send_parent"
    assert "学习报告" in payload["gate"]["message"]

"""阶段 1 — Plan Run 步进权收权（issue #18 阶段 1；ADR-0015 §4）。

plan_run_service 的纯转移函数是步进状态机的唯一拥有者：
- 工具结果带 approval_needed → awaiting_confirmation（阻塞，绝不推进下一步）
  —— 曾被 SSE adapter 当 success 标成 completed 并启动下一步（「没确认就往下推」）；
- approve 决定 → running（重放中）；重放成功 → completed 并启动下一步；
  重放失败 → failed（不自动推进）；
- reject → revising；abandon → cancelled。
- 门开着（guard 有未决门）→ guard 机械拒绝 agent 的一切工具调用。

纯函数直接测（无 DB 依赖）；GuardState 全拦逻辑一并钉住。
"""
import json

from agent.guard import GuardState, _make_guarded_tool

import asyncio


def _run(coro):
    async def go():
        return await coro
    return asyncio.run(go())


STEPS = [
    {"step": 1, "skill": "diagnose_barrier", "description": "诊断", "status": "completed"},
    {"step": 2, "skill": "generate_learning_plan", "description": "生成计划", "status": "completed"},
    {"step": 3, "skill": "send_learning_plan", "description": "发送计划", "status": "pending"},
    {"step": 4, "skill": "generate_parent_report", "description": "生成报告", "status": "pending"},
]


# ── 1. 工具结果驱动：approval_needed 是阻塞不是成功 ──────────────────

def test_approval_needed_blocks_step_never_completes():
    """回归红线①：approval_needed 时不得有任何步骤 completed / 后续 running。"""
    from app.services.plan_run_service import compute_tool_transition
    steps = [dict(s) for s in STEPS]
    transitions = compute_tool_transition(
        steps, "send_learning_plan",
        {"approval_needed": True, "draft_id": "d1", "action": "send_student"})
    assert transitions == [(3, "awaiting_confirmation")], transitions
    assert steps[2]["status"] == "awaiting_confirmation"
    assert steps[3]["status"] == "pending", "门后步骤必须保持待执行"


def test_approval_needed_on_generate_opens_gate_on_send_step():
    """生成即门：generate 工具的结果把门挂到对应发送步骤上。"""
    from app.services.plan_run_service import compute_tool_transition
    steps = [dict(s) for s in STEPS]
    transitions = compute_tool_transition(
        steps, "generate_learning_plan",
        {"message": "已生成", "approval_needed": True, "draft_id": "d1",
         "action": "send_student"})
    assert transitions == [(3, "awaiting_confirmation")], transitions


def test_success_completes_step_and_starts_next():
    from app.services.plan_run_service import compute_tool_transition
    steps = [dict(s) for s in STEPS]
    steps[1]["status"] = "running"
    transitions = compute_tool_transition(
        steps, "generate_learning_plan", {"message": "ok"})
    assert (2, "completed") in transitions
    assert (3, "running") in transitions


def test_failure_marks_failed_no_advance():
    from app.services.plan_run_service import compute_tool_transition
    steps = [dict(s) for s in STEPS]
    steps[1]["status"] = "running"
    transitions = compute_tool_transition(
        steps, "generate_learning_plan", {"error": "llm down"})
    assert transitions == [(2, "failed")], transitions
    assert steps[3]["status"] == "pending"


def test_unknown_tool_result_is_noop():
    from app.services.plan_run_service import compute_tool_transition
    steps = [dict(s) for s in STEPS]
    transitions = compute_tool_transition(steps, "web_search", {"ok": True})
    assert transitions == []


# ── 2. 决定驱动：approve 解锁、重放结果落终态 ────────────────────────

def test_approve_moves_awaiting_to_replaying():
    from app.services.plan_run_service import compute_decision_transition
    steps = [dict(s) for s in STEPS]
    steps[2]["status"] = "awaiting_confirmation"
    transitions = compute_decision_transition(steps, "approve")
    assert transitions == [(3, "running")], "批准 → 重放中（重放成功才打勾）"


def test_replay_success_completes_gated_step_then_starts_next():
    from app.services.plan_run_service import compute_replay_transition
    steps = [dict(s) for s in STEPS]
    steps[2]["status"] = "running"
    transitions = compute_replay_transition(steps, "send_learning_plan", True)
    assert (3, "completed") in transitions
    assert (4, "running") in transitions


def test_replay_failure_marks_failed():
    from app.services.plan_run_service import compute_replay_transition
    steps = [dict(s) for s in STEPS]
    steps[2]["status"] = "running"
    transitions = compute_replay_transition(steps, "send_learning_plan", False)
    assert transitions == [(3, "failed")]
    assert steps[3]["status"] == "pending"


def test_reject_moves_to_revising_abandon_cancels():
    from app.services.plan_run_service import compute_decision_transition
    steps = [dict(s) for s in STEPS]
    steps[2]["status"] = "awaiting_confirmation"
    assert compute_decision_transition(steps, "reject") == [(3, "revising")]
    # 打回修订完成后新门重开 → 回到 awaiting → 老师放弃 → cancelled
    steps2 = [dict(s) for s in steps]
    steps2[2]["status"] = "awaiting_confirmation"
    assert compute_decision_transition(steps2, "abandon") == [(3, "cancelled")]


# ── 3. 门开着 GuardState 全拦工具 ────────────────────────────────────

def test_guard_blocks_all_tools_while_gate_open():
    """回归红线③：门开着时第二个工具调用被拒——不再覆盖 pending。"""
    calls: list = []

    async def fake_tool(x: str = ""):
        """Fake tool."""
        calls.append(x)
        return json.dumps({"ok": True})

    gs = GuardState()
    gs.pending_approval = {"name": "send_learning_plan", "fn": lambda **k: None,
                           "kwargs": {}}
    guarded = _make_guarded_tool(fake_tool, gs)
    out = json.loads(_run(guarded.ainvoke({"x": "1"})))
    assert calls == [], "门开着时不得执行任何工具（C1-Q3 全拦）"
    assert out.get("gate_open_blocked") is True, out
    # 2026-09-21 文案契约分离（架构审查 C）：error 是机器码，llm_brief 是
    # 给模型的中性事实（无祈使句——防鹦鹉学舌透出给用户），ui_label 给前端
    assert out.get("error") == "waiting_for_gate", out
    assert "等待老师" in out.get("llm_brief", ""), out
    assert "请勿" not in out.get("llm_brief", ""), "llm_brief 不得含祈使句"
    assert out.get("ui_label") == "等待确认", out


def test_gate_open_block_preserves_original_pending():
    """全拦不得覆盖/清除原 pending——门现场原样保留。"""
    async def fake_tool(x: str = ""):
        """Fake tool."""
        return json.dumps({"ok": True})

    gs = GuardState()
    original = {"name": "send_learning_plan", "fn": lambda **k: None, "kwargs": {}}
    gs.pending_approval = original
    guarded = _make_guarded_tool(fake_tool, gs)
    _run(guarded.ainvoke({"x": "1"}))
    assert gs.pending_approval is original

"""阶段 0 — 决策通道唯一化回归（ADR-0015；issue #18 阶段 0）。

门开着时老师打字的语义只有两种，且**打字永不构成批准**：
- 确认词（同意/好的/发吧…含「不要发送」这类误匹配）→ 引导文案，零副作用；
- 其他文字 → 草稿门=打回+反馈（ADR-0013 防御分支），布尔门=作废待批。

另钉幽灵批准：取消/放弃后 pending 必须清空——否则后一句「好的」
会命中旧的确认分支执行已取消的动作。
"""
import asyncio
import json

from agent.guard import GuardState


def _run(coro):
    async def go():
        return await coro
    return asyncio.run(go())


def _pending_guard(tool_name: str = "send_learning_plan", calls: list | None = None):
    """登记待批发送（等价 guard 拦下时的登记）。"""
    from agent.tools.diagnosis import send_learning_plan

    async def fake_send(**kwargs):
        if calls is not None:
            calls.append(kwargs)
        return json.dumps({"ok": True})

    fake_send.__name__ = tool_name
    gs = GuardState()
    gs.pending_approval = {"name": tool_name, "fn": fake_send,
                           "kwargs": {"student_id": "s1", "draft_id": "d1"}}
    return gs


def _classify(message: str, guard, is_plan_gate: bool):
    from agent.channel.langgraph_channel import _classify_typed_text
    return _classify_typed_text(message, guard, is_plan_gate)


# ── 1. 确认词 → 引导，零副作用 ──────────────────────────────────────

def test_confirm_word_yields_guidance_not_execution():
    calls: list = []
    gs = _pending_guard(calls=calls)
    kind, events = _classify("同意", gs, is_plan_gate=True)
    assert kind == "guidance"
    assert calls == [], "确认词不得执行任何工具（ADR-0015：决策通道唯一化）"
    assert gs.pending_approval is not None, "引导不消费待批现场"


def test_negation_with_send_word_is_guidance_never_send():
    """「不要发送」含「发送」会被词表命中——降级后只是引导，绝不发送。"""
    calls: list = []
    gs = _pending_guard(calls=calls)
    kind, _ = _classify("不要发送", gs, is_plan_gate=True)
    assert kind == "guidance"
    assert calls == [], "「不要发送」被当成批准真发送过——回归红线"


def test_guidance_events_are_text_done_only():
    gs = _pending_guard()
    _, events = _classify("好的", gs, is_plan_gate=False)
    kinds = []
    for e in events:
        raw = e[len("data: "):].strip() if e.startswith("data: ") else e.strip()
        if raw in ("[DONE]", ""):
            continue
        kinds.append(json.loads(raw)["type"])
    assert kinds == ["text", "done"], kinds


# ── 2. 其他文字 → 草稿门打回 / 布尔门作废 ────────────────────────────

def test_free_text_on_draft_gate_is_reject_feedback():
    gs = _pending_guard()
    kind, _ = _classify("把第三周改成复习盐类水解", gs, is_plan_gate=True)
    assert kind == "reject"
    assert gs.pending_approval is not None, "打回现场保留（修订循环消费）"


def test_free_text_on_boolean_gate_voids_pending():
    gs = _pending_guard(tool_name="assign_adaptive_practice")
    kind, _ = _classify("先别管这个", gs, is_plan_gate=False)
    assert kind == "void"
    assert gs.pending_approval is None, "作废必须清 pending——否则幽灵批准"


# ── 3. 幽灵批准：取消后 pending 清空 ────────────────────────────────

def test_cancel_clears_pending_so_no_ghost_approval():
    """request_approval 的取消路径必须清 pending——被打断后再打「好的」
    不得命中旧动作（曾在 guard.py 里留下 pending）。"""
    from unittest.mock import patch

    import langgraph.types as lg_types
    from agent.guard import _make_request_approval_tool

    gs = GuardState()
    gs.pending_approval = {"name": "read", "fn": lambda: None, "kwargs": {}}

    def fake_interrupt(payload):
        return "cancelled"  # Command(resume="cancelled") 的真实语义

    with patch.object(lg_types, "interrupt", fake_interrupt):
        tool = _make_request_approval_tool(gs)
        out = _run(tool.ainvoke({"message": "需要确认"}))
    assert "取消" in str(out), out
    assert gs.pending_approval is None, "取消后 pending 未清 → 后一句「好的」幽灵批准"


def test_after_void_no_confirm_branch_triggers():
    """作废之后再来确认词：没有 pending → 不进引导分支（按普通消息流转）。"""
    gs = _pending_guard()
    kind, _ = _classify("先别管这个", gs, is_plan_gate=False)
    assert kind == "void"
    from agent.channel.langgraph_channel import _classify_typed_text
    kind2, _ = _classify("好的", gs, is_plan_gate=False)
    assert kind2 == "none", "pending 已清，确认词不再触发任何门分支"

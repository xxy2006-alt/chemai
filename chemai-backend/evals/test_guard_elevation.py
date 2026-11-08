"""
Guard elevation tests (按次审批，DSH danger-full-access 模式).

2026-08 read 卡死修复后的新契约（原契约见 git 历史 4438694）：
- 已批准：guarded tool 用一次性 elevation 重放执行一次。
- 未批准：approval_needed 原样透传给 LLM（不再在工具内 interrupt——
  langgraph 1.x 的 astream_events 会静默吞掉工具内 interrupt，既无审批卡
  又会在带旧中断状态的线程上永久挂死流）；审批经 request_approval 工具 +
  resume 完成，批准后重放。
- 未批准透传时撤销 dedup 登记：批准后重试相同参数不被「重复调用」拦截。
"""
import asyncio
import json

from agent.guard import GuardState, _make_guarded_tool


def _fake_tool_results(calls: list):
    """Tool that returns approval_needed on the first call, success on later
    elevated calls."""

    async def fake(**kwargs):
        """Fake file tool: approval_needed first, success on elevated replay."""
        calls.append(kwargs)
        if len(calls) == 1:
            return json.dumps({"approval_needed": True,
                               "message": "工作区外访问需要批准: /x",
                               "target": "/x"}, ensure_ascii=False)
        return json.dumps({"ok": True, "elevated": True}, ensure_ascii=False)

    return fake


def _run(guarded, **kwargs):
    async def go():
        # StructuredTool 经 ainvoke 调用（参数以 dict 传入）
        return await guarded.ainvoke(kwargs)

    return asyncio.run(go())


def test_approved_replays_once_with_elevation():
    calls = []
    gs = GuardState()
    gs.approved = True  # 老师已在本轮批准
    guarded = _make_guarded_tool(_fake_tool_results(calls), gs, requires_approval=False)
    result = _run(guarded)
    data = json.loads(result)
    assert data.get("ok") is True and data.get("elevated") is True
    assert len(calls) == 2, "approved → exactly one replay"


def test_not_approved_passes_approval_needed_through():
    """未批准 → approval_needed 原样透传，不 interrupt、不重放。"""
    calls = []
    gs = GuardState()
    gs.approved = False
    guarded = _make_guarded_tool(_fake_tool_results(calls), gs, requires_approval=False)
    result = _run(guarded)
    data = json.loads(result)
    assert data.get("approval_needed") is True
    assert "批准" in data.get("message", "")
    assert data.get("target") == "/x"
    assert len(calls) == 1, "未批准不得重放执行"


def test_not_approved_unmarks_dedup_for_retry():
    """未批准透传后，相同参数的调用不再被 dedup 拦截（批准后重试可用）。"""
    calls = []
    gs = GuardState()
    gs.approved = False
    guarded = _make_guarded_tool(_fake_tool_results(calls), gs, requires_approval=False)
    first = _run(guarded)
    assert json.loads(first).get("approval_needed") is True
    # 模拟批准后重试（相同参数）
    gs.approved = True
    second = _run(guarded)
    data2 = json.loads(second)
    assert data2.get("ok") is True, f"重试被误拦截: {second}"
    assert len(calls) == 2

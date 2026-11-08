"""确定性审批重放（2026-08）：批准后 request_approval 自动重跑被拦截的调用，
不再依赖 LLM 自觉重试——实测批准后模型可能直接收尾，链路断掉。"""
import asyncio
import json

from agent.guard import GuardState, _make_guarded_tool, _make_request_approval_tool
from agent.langgraph_sse_v2 import LangGraphSSEAdapterV2


def _run(coro):
    async def go():
        return await coro

    return asyncio.run(go())


def test_guard_stores_pending_call_on_approval_needed():
    calls = []

    async def fake(path: str = ""):
        """Fake file tool: approval_needed first, content after."""
        calls.append(path)
        if len(calls) == 1:
            return json.dumps({"approval_needed": True, "message": "需要批准", "target": path})
        return json.dumps({"content": "文件内容", "path": path})

    gs = GuardState()
    guarded = _make_guarded_tool(fake, gs)
    out = _run(guarded.ainvoke({"path": "/x"}))
    assert json.loads(out).get("approval_needed") is True
    assert gs.pending_approval is not None
    assert gs.pending_approval["name"] == "fake"


def test_request_approval_replays_pending_call(monkeypatch):
    calls = []

    async def fake(path: str = ""):
        """Fake file tool: approval_needed first, content after."""
        calls.append(path)
        if len(calls) == 1:
            return json.dumps({"approval_needed": True, "message": "需要批准", "target": path})
        return json.dumps({"content": "文件内容", "path": path})

    gs = GuardState()
    guarded = _make_guarded_tool(fake, gs)
    _run(guarded.ainvoke({"path": "/x"}))

    monkeypatch.setattr("langgraph.types.interrupt", lambda payload: "approved")
    approval_tool = _make_request_approval_tool(gs)
    out = json.loads(_run(approval_tool.ainvoke({"message": "确认读取"})))
    assert out["__replayed_tool"] == "fake"
    assert out["result"]["content"] == "文件内容"
    assert gs.pending_approval is None


def test_adapter_emits_replayed_tool_result():
    adapter = LangGraphSSEAdapterV2()
    payload = json.dumps({
        "__replayed_tool": "read",
        "result": {"content": "文件内容", "path": "x.txt"},
    }, ensure_ascii=False)
    events = adapter.feed({
        "event": "on_tool_end",
        "name": "request_approval",
        "data": {"output": f"content='{payload}' name='request_approval' tool_call_id='call_1'"},
    })
    assert len(events) == 1
    evt = json.loads(events[0])
    assert evt["type"] == "tool_result"
    assert evt["name"] == "read"
    assert evt["success"] is True
    assert json.loads(evt["result"])["content"] == "文件内容"


def test_adapter_replayed_error_marks_failure():
    adapter = LangGraphSSEAdapterV2()
    payload = json.dumps({
        "__replayed_tool": "read",
        "result": {"error": "文件不存在"},
    }, ensure_ascii=False)
    events = adapter.feed({
        "event": "on_tool_end",
        "name": "request_approval",
        "data": {"output": f"content='{payload}' name='request_approval' tool_call_id='call_2'"},
    })
    evt = json.loads(events[0])
    assert evt["success"] is False


def test_direct_replay_events_returns_tool_result():
    """resume 端点无中断分支：批准后直接重放待批调用（模型没调 request_approval 的路径）"""
    import asyncio as _asyncio
    from agent.channel.langgraph_channel import _direct_replay_events

    calls = []

    async def fake(path: str = ""):
        """Fake file tool: approval_needed first, content after."""
        calls.append(path)
        if len(calls) == 1:
            return json.dumps({"approval_needed": True, "message": "需要批准", "target": path})
        return json.dumps({"content": "文件内容", "path": path})

    gs = GuardState()
    guarded = _make_guarded_tool(fake, gs)
    _run(guarded.ainvoke({"path": "/x"}))

    async def go():
        return await _direct_replay_events(gs, True)

    events, replay_info = _asyncio.run(go())
    assert len(events) == 1
    evt = json.loads(events[0])
    assert evt["type"] == "tool_result"
    assert evt["name"] == "fake"
    assert json.loads(evt["result"])["content"] == "文件内容"
    # 重放信息：name + 原始完整结果（供替换进 ToolMessage）+ SSE 截断结果
    assert replay_info["name"] == "fake"
    assert json.loads(replay_info["raw"])["content"] == "文件内容"
    assert json.loads(replay_info["result"])["content"] == "文件内容"


def test_direct_replay_cancel_clears_pending_without_replaying():
    """取消：清空待批登记，不重放不置 approved。"""
    import asyncio as _asyncio
    from agent.channel.langgraph_channel import _direct_replay_events

    calls = []

    async def fake(path: str = ""):
        """Fake file tool: approval_needed first, content after."""
        calls.append(path)
        return json.dumps({"approval_needed": True, "message": "需要批准", "target": path})

    gs = GuardState()
    guarded = _make_guarded_tool(fake, gs)
    _run(guarded.ainvoke({"path": "/x"}))

    async def go():
        return await _direct_replay_events(gs, False)

    events, replay_info = _asyncio.run(go())
    assert events == []
    assert replay_info is None
    assert gs.pending_approval is None
    assert gs.approved is False


# ═══════════════════════════════════════════════════════════════════
# 2026-08 修复「用户发送端显示巨文」：C 层（结果替换进 ToolMessage）+
# A 层（续接后摘除注入消息）
# ═══════════════════════════════════════════════════════════════════

class _FakeState:
    def __init__(self, msgs):
        self.values = {"messages": msgs}


class _FakeAgent:
    """Minimal agent double: aget_state / aupdate_state / astream_events."""

    def __init__(self, msgs):
        self._msgs = msgs
        self.updates = []
        self.stream_inputs = []

    async def aget_state(self, config):
        return _FakeState(self._msgs)

    async def aupdate_state(self, config, values):
        self.updates.append(values)
        # 模拟 LangGraph append 语义：RemoveMessage 删、其余追加
        from langchain_core.messages import RemoveMessage
        for m in values.get("messages", []):
            if isinstance(m, RemoveMessage):
                self._msgs = [x for x in self._msgs if getattr(x, "id", None) != m.id]
            else:
                self._msgs.append(m)

    async def astream_events(self, state_input, config, version="v2"):
        self.stream_inputs.append(state_input)
        # 模拟 LangGraph：输入的 user 消息会追加进 checkpoint
        from langchain_core.messages import HumanMessage
        for b in state_input.get("messages", []):
            if b.get("role") == "user":
                self._msgs.append(HumanMessage(content=b.get("content", ""), id="injected_1"))
        yield {"event": "on_chat_model_stream", "name": "", "data": {"chunk": None}}


def test_replace_pending_tool_result_swaps_content_keeping_call_id():
    """C 层：批准重放后，checkpoint 里 approval_needed 的 ToolMessage 被替换为
    真实结果（保留 tool_call_id，LangGraph 配对校验不受影响）。"""
    import asyncio as _asyncio
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    from agent.channel.langgraph_channel import _replace_pending_tool_result

    msgs = [
        HumanMessage(content="读取桌面文件", id="u1"),
        AIMessage(content="我来读取。", tool_calls=[{"name": "read", "args": {"path": "/x"}, "id": "call_1"}], id="a1"),
        ToolMessage(content='{"approval_needed": true}', name="read", tool_call_id="call_1", id="tm_old"),
    ]
    agent = _FakeAgent(msgs)

    async def go():
        return await _replace_pending_tool_result(
            agent, {"configurable": {"thread_id": "t-1"}}, "read",
            '{"content": "文件真实内容", "path": "x.txt"}')

    assert _asyncio.run(go()) is True
    assert len(agent.updates) == 1
    ops = agent.updates[0]["messages"]
    from langchain_core.messages import RemoveMessage, ToolMessage as TM
    assert isinstance(ops[0], RemoveMessage)
    assert ops[0].id == "tm_old"  # 摘掉旧 approval_needed 结果
    assert isinstance(ops[1], TM)
    assert ops[1].tool_call_id == "call_1"  # 配对 id 不变
    assert ops[1].name == "read"
    assert json.loads(ops[1].content)["content"] == "文件真实内容"


def test_replace_pending_tool_result_missing_tool_returns_false():
    """没有对应工具消息时返回 False，调用方回退旧逻辑（不丢结果）。"""
    import asyncio as _asyncio
    from langchain_core.messages import HumanMessage
    from agent.channel.langgraph_channel import _replace_pending_tool_result

    agent = _FakeAgent([HumanMessage(content="你好", id="u1")])

    async def go():
        return await _replace_pending_tool_result(
            agent, {"configurable": {"thread_id": "t-1"}}, "read", "{}")

    assert _asyncio.run(go()) is False
    assert agent.updates == []


def test_remove_injected_replay_message_removes_note():
    """A 层：续接完成后摘除注入的续接提示，历史不残留内部消息。"""
    import asyncio as _asyncio
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    from agent.channel.langgraph_channel import _remove_injected_replay_message

    note = ("（系统提示：你刚才请求老师批准的操作已获得批准，并已自动重放完成，"
            "完整结果见上文的工具结果（工具「read」）。请基于该结果继续完成老师的请求。）")
    msgs = [
        HumanMessage(content="读取桌面文件", id="u1"),
        AIMessage(content="我来读取。", tool_calls=[{"name": "read", "args": {}, "id": "call_1"}], id="a1"),
        ToolMessage(content='{"content": "文件真实内容"}', name="read", tool_call_id="call_1", id="tm_1"),
        HumanMessage(content=note, id="note_1"),
        AIMessage(content="已读取完成。", id="a2"),
    ]
    agent = _FakeAgent(msgs)

    async def go():
        return await _remove_injected_replay_message(
            agent, {"configurable": {"thread_id": "t-1"}})

    _asyncio.run(go())
    assert len(agent.updates) == 1
    ops = agent.updates[0]["messages"]
    from langchain_core.messages import RemoveMessage
    assert isinstance(ops[0], RemoveMessage)
    assert ops[0].id == "note_1"  # 只摘注入提示，不碰用户消息


def test_remove_injected_replay_message_keeps_user_messages():
    """没有注入句式时不动 checkpoint（用户消息永不被误删）。"""
    import asyncio as _asyncio
    from langchain_core.messages import HumanMessage
    from agent.channel.langgraph_channel import _remove_injected_replay_message

    msgs = [
        HumanMessage(content="正常提问", id="u1"),
        HumanMessage(content="（系统提示：这行字是用户自己打的，句式不匹配）", id="u2"),
    ]
    agent = _FakeAgent(msgs)

    async def go():
        return await _remove_injected_replay_message(
            agent, {"configurable": {"thread_id": "t-1"}})

    _asyncio.run(go())
    assert agent.updates == []  # 无匹配 → 不动 checkpoint


def test_stream_replay_continuation_slim_message_when_replaced():
    """C 层成功替换时：续接提示不再携带完整重放结果（巨文根因），
    续接完成后摘除注入消息（A 层）。"""
    import asyncio as _asyncio
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    from agent.channel.langgraph_channel import _stream_replay_continuation

    msgs = [
        HumanMessage(content="读取桌面文件", id="u1"),
        AIMessage(content="我来读取。", tool_calls=[{"name": "read", "args": {}, "id": "call_1"}], id="a1"),
        ToolMessage(content='{"approval_needed": true}', name="read", tool_call_id="call_1", id="tm_old"),
    ]
    agent = _FakeAgent(msgs)
    adapter = LangGraphSSEAdapterV2()
    replay_info = {
        "name": "read",
        "raw": '{"content": "整份文件内容…" * 1000}',
        "result": '{"content": "截断版"}',
    }

    async def go():
        out = []
        async for ev in _stream_replay_continuation(
                agent, adapter, {"configurable": {"thread_id": "t-1"}}, replay_info):
            out.append(ev)
        return out

    out = _asyncio.run(go())
    assert out == []  # chunk=None → adapter 无输出，流正常结束
    assert len(agent.stream_inputs) == 1
    injected = agent.stream_inputs[0]["messages"][0]["content"]
    # 瘦身版：无完整结果
    assert "整份文件内容" not in injected
    assert "完整结果见上文的工具结果（工具「read」）" in injected
    # C 层：旧 approval_needed ToolMessage 已被替换
    assert any(isinstance(m, ToolMessage) and m.tool_call_id == "call_1"
               and "文件真实" not in str(getattr(m, "content", "")) for m in agent._msgs)
    # A 层：续接后摘除注入消息
    removed_ids = [m.id for u in agent.updates
                   for m in u.get("messages", []) if getattr(m, "id", None) == "injected_1"]
    assert "injected_1" in removed_ids


def test_stream_replay_continuation_fallback_keeps_result():
    """替换失败时回退旧行为：结果仍随消息注入（不丢结果）。"""
    import asyncio as _asyncio
    from langchain_core.messages import HumanMessage
    from agent.channel.langgraph_channel import _stream_replay_continuation

    agent = _FakeAgent([HumanMessage(content="你好", id="u1")])
    adapter = LangGraphSSEAdapterV2()
    replay_info = {"name": "read", "raw": '{"content": "完整结果ABC"}', "result": '{"content": "截断版"}'}

    async def go():
        out = []
        async for ev in _stream_replay_continuation(
                agent, adapter, {"configurable": {"thread_id": "t-1"}}, replay_info):
            out.append(ev)
        return out

    _asyncio.run(go())
    injected = agent.stream_inputs[0]["messages"][0]["content"]
    assert "重放结果如下" in injected
    assert "截断版" in injected  # 回退塞的是 SSE 截断结果

"""阶段 1 — SSE 接缝回归：approval_needed 不再推进 todolist（issue #18）。

原始缺陷就在 adapter：send 工具返回 approval_needed（无 error）→ success=True →
门步骤被标 completed、下一步标 running（「人工还没确认就往下推」）。
修后：adapter 只做格式化，转移规则来自 plan_run_service.compute_tool_transition。
"""
import json

from agent.langgraph_sse_v2 import LangGraphSSEAdapterV2


def _plan_started(adapter):
    events = adapter.feed({
        "event": "on_tool_end", "name": "plan_task",
        "data": {"output": json.dumps({
            "goal": "给张三做学习计划并通知家长",
            "total_steps": 2,
            "steps": [
                {"step": 1, "skill": "generate_learning_plan", "description": "生成计划"},
                {"step": 2, "skill": "send_learning_plan", "description": "发送计划"},
            ],
        }, ensure_ascii=False)},
    })
    assert any('"plan_summary"' in e for e in events)
    return events


def _plan_progress(events):
    out = []
    for e in events:
        raw = e[len("data: "):].strip() if e.startswith("data: ") else e.strip()
        if raw in ("[DONE]", ""):
            continue
        try:
            evt = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if evt.get("type") == "plan_progress":
            out.append((evt["current_step"], evt["status"]))
    return out


def test_approval_needed_marks_awaiting_never_completes():
    """直接调发送被门拦下：发送步 → awaiting，绝不 completed / 启动下一步。"""
    adapter = LangGraphSSEAdapterV2()
    _plan_started(adapter)
    adapter._plan_steps[0]["status"] = "completed"
    adapter._plan_steps[1]["status"] = "running"
    events = adapter.feed({
        "event": "on_tool_end", "name": "send_learning_plan",
        "data": {"output": json.dumps({
            "approval_needed": True, "draft_id": "d1", "action": "send_student",
            "message": "请确认是否发送",
        }, ensure_ascii=False)},
    })
    progress = _plan_progress(events)
    assert (2, "awaiting_confirmation") in progress, progress
    assert not any(s == "completed" for _, s in progress), "门步骤被标完成——原始 bug"
    assert not any(s == "running" for _, s in progress), "门后步骤被启动——原始 bug"


def test_generate_gate_blocks_send_step_not_next_step():
    """生成即门：生成步打勾（草稿已落库），门挂发送步骤，后续步骤不得 running。"""
    adapter = LangGraphSSEAdapterV2()
    _plan_started(adapter)
    adapter._plan_steps[0]["status"] = "running"
    events = adapter.feed({
        "event": "on_tool_end", "name": "generate_learning_plan",
        "data": {"output": json.dumps({
            "message": "已生成", "approval_needed": True, "draft_id": "d1",
            "action": "send_student", "message_gate": "请确认是否发送",
        }, ensure_ascii=False)},
    })
    progress = _plan_progress(events)
    assert (1, "completed") in progress, progress
    assert (2, "awaiting_confirmation") in progress, progress
    assert not any(s == "running" for _, s in progress)


def test_plain_success_completes_and_starts_next():
    adapter = LangGraphSSEAdapterV2()
    _plan_started(adapter)
    # 先人工把第一步置为 running（模拟执行中）
    adapter._plan_steps[0]["status"] = "running"
    events = adapter.feed({
        "event": "on_tool_end", "name": "generate_learning_plan",
        "data": {"output": json.dumps({"message": "已生成", "plan": {}}, ensure_ascii=False)},
    })
    progress = _plan_progress(events)
    assert (1, "completed") in progress
    assert (2, "running") in progress


def test_failure_marks_failed():
    adapter = LangGraphSSEAdapterV2()
    _plan_started(adapter)
    adapter._plan_steps[0]["status"] = "running"
    events = adapter.feed({
        "event": "on_tool_end", "name": "generate_learning_plan",
        "data": {"output": json.dumps({"error": "llm down"}, ensure_ascii=False)},
    })
    assert (1, "failed") in _plan_progress(events)


def test_filesystem_elevation_gate_does_not_touch_todolist():
    """工作区外访问的按次审批（approval_needed 但非计划门）不得污染 todolist
    （曾把无关步骤标成 awaiting——H6）。"""
    adapter = LangGraphSSEAdapterV2()
    _plan_started(adapter)
    adapter._plan_steps[0]["status"] = "running"
    events = adapter.feed({
        "event": "on_tool_end", "name": "read",
        "data": {"output": json.dumps({
            "approval_needed": True, "message": "工作区外访问需要批准",
            "target": "C:/outside.txt",
        }, ensure_ascii=False)},
    })
    kinds = [e for e in events if '"plan_progress"' in e]
    assert kinds == [], "按次审批不属于计划门——todolist 不动"


def test_gate_open_blocked_marks_awaiting_not_failed():
    """门等待期间 LLM 多调的发送工具被拦（gate_open_blocked）：
    该步语义是「暂停等待确认」而非失败——2026-09-20 实测被标成 failed，
    计划卡给老师看红色失败态（误导）。"""
    adapter = LangGraphSSEAdapterV2()
    _plan_started(adapter)
    adapter._plan_steps[0]["status"] = "completed"
    adapter._plan_steps[1]["status"] = "running"
    events = adapter.feed({
        "event": "on_tool_end", "name": "send_learning_plan",
        "data": {"output": json.dumps({
            "error": "有确认请求等待老师处理（请在确认卡上批准/打回/放弃），当前操作已暂缓。"
                     "请勿继续调用工具，用文字说明你正在等待确认。",
            "gate_open_blocked": True,
        }, ensure_ascii=False)},
    })
    progress = _plan_progress(events)
    assert (2, "awaiting_confirmation") in progress, progress
    assert not any(s == "failed" for _, s in progress), "被门拦下被标失败——误导老师"
    # 阻塞语义：不启动下一步
    assert not any(s == "running" for _, s in progress), "被拦后步骤不应推进"

"""
SSE adapter plan-event tests (Spec 06) — synthetic events, zero API.

Pins the contract between plan_task results and the frontend step card:
  plan_summary {goal, total_steps, steps[]} -> renders the card
  plan_progress {current_step, status}     -> marks steps running/completed
"""
import json

from agent.langgraph_sse_v2 import LangGraphSSEAdapterV2


def _plan_result(steps):
    return json.dumps({
        "goal": "准备月考",
        "total_steps": len(steps),
        "steps": steps,
    }, ensure_ascii=False)


def _tool_end_event(name, output):
    return {"event": "on_tool_end", "name": name,
            "data": {"output": f"content='{output}'"}}  # LangGraph ToolMessage repr


def _types(events_json):
    return [json.loads(e) for e in events_json]


def test_plan_task_emits_summary_and_first_running():
    adapter = LangGraphSSEAdapterV2()
    events = _types(adapter.feed(_tool_end_event("plan_task", _plan_result([
        {"step": 1, "skill": "diagnose_barrier", "description": "诊断薄弱点", "status": "pending"},
        {"step": 2, "skill": "show_exam_workbench", "description": "出题", "status": "pending"},
    ]))))
    summary = next(e for e in events if e["type"] == "plan_summary")
    assert summary["goal"] == "准备月考" and summary["total_steps"] == 2
    assert [s["step"] for s in summary["steps"]] == [1, 2]
    progress = [e for e in events if e["type"] == "plan_progress"]
    assert progress[0]["current_step"] == 1 and progress[0]["status"] == "running"


def test_matching_tool_completes_step_and_starts_next():
    adapter = LangGraphSSEAdapterV2()
    adapter.feed(_tool_end_event("plan_task", _plan_result([
        {"step": 1, "skill": "diagnose_barrier", "description": "诊断", "status": "pending"},
        {"step": 2, "skill": "show_exam_workbench", "description": "出题", "status": "pending"},
        {"step": 3, "skill": "generate_learning_plan", "description": "计划", "status": "pending"},
    ])))
    events = _types(adapter.feed(_tool_end_event("diagnose_barrier", '{"ok": true}')))
    progress = [e for e in events if e["type"] == "plan_progress"]
    assert [(p["current_step"], p["status"]) for p in progress] == [
        (1, "completed"), (2, "running")]


def test_unrelated_tool_does_not_touch_plan():
    adapter = LangGraphSSEAdapterV2()
    adapter.feed(_tool_end_event("plan_task", _plan_result([
        {"step": 1, "skill": "diagnose_barrier", "description": "诊断", "status": "pending"},
    ])))
    events = _types(adapter.feed(_tool_end_event("web_search", '{"ok": true}')))
    assert not [e for e in events if e["type"] == "plan_progress"]


def test_no_plan_events_without_plan():
    adapter = LangGraphSSEAdapterV2()
    events = _types(adapter.feed(_tool_end_event("search_exam_bank", '{"questions": []}')))
    assert not [e for e in events if e["type"] in ("plan_summary", "plan_progress")]


def test_plan_task_error_does_not_activate_plan():
    adapter = LangGraphSSEAdapterV2()
    events = _types(adapter.feed(_tool_end_event("plan_task", '{"error": "请提供目标"}')))
    assert not [e for e in events if e["type"] == "plan_summary"]

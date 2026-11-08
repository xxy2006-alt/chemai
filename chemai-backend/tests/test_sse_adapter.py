"""017 — SSE 适配器 ToolMessage repr 解包 + 干净 JSON 下发（evals）。

用户反馈「说展示图表了，图表在哪里？在你更新前端前都能正确展示」：
LangGraph 新版 ToolMessage repr 带 name/tool_call_id 后缀（
`content='{...}' name='show_diagnosis' tool_call_id='call_xxx'`），
旧 unwrap 用 endswith 判断失败 → 前端拿到 {raw: repr} →
诊断卡片数据丢失（学生诊断变成空图表）、show_* 卡片显示原始 JSON 乱码。
本测试锁定：v2/v1 适配器对带后缀的 repr 必须解包，且 tool_result 下发
可解析的干净 JSON（含 student_name，前端可渲染学生诊断图形）。
"""
import json

from agent.langgraph_sse_v2 import LangGraphSSEAdapterV2
from agent.langgraph_sse import _unwrap_tool_message


def _tool_message_repr(content: str, name: str) -> str:
    return f"content='{content}' name='{name}' tool_call_id='call_00_abc123'"


def test_v2_unwraps_tool_message_repr_with_suffix():
    """带 name/tool_call_id 后缀的 ToolMessage repr → 解包并下发可解析 JSON"""
    payload = json.dumps({
        "message": "诊断结果已生成，请查看下方图表。",
        "student_id": "202610201",
        "student_name": "李世睿",
        "barrier_distribution": {"concept": 0.8, "reading": 0.15, "expression": 0.05},
    }, ensure_ascii=False)
    adapter = LangGraphSSEAdapterV2()
    events = adapter.feed({
        "event": "on_tool_end",
        "name": "diagnose_barrier",
        "data": {"output": _tool_message_repr(payload, "diagnose_barrier")},
    })
    assert len(events) == 1
    evt = json.loads(events[0])
    assert evt["type"] == "tool_result"
    assert evt["name"] == "diagnose_barrier"
    assert evt["success"] is True
    # 下发的是可解析的干净 JSON（不是 repr/raw）
    parsed = json.loads(evt["result"])
    assert parsed["student_name"] == "李世睿"
    assert "student_id" in parsed
    # 不得包含 repr 残留
    assert "tool_call_id" not in evt["result"]
    assert "name=" not in evt["result"]


def test_v1_unwrap_tool_message_repr_with_suffix():
    """v1 辅助函数：带后缀的 repr 正确解包"""
    content = '{"message": "已打开面板", "ok": true}'
    out = _unwrap_tool_message(f"content='{content}' name='show_diagnosis' tool_call_id='call_1'")
    parsed = json.loads(out)
    assert parsed["ok"] is True


def test_unwrap_plain_json_unchanged():
    """非 repr 的纯 JSON 原样返回（不误伤）"""
    plain = '{"message": "正常返回", "total": 3}'
    assert _unwrap_tool_message(plain) == plain


# ── S3 文本零复述（2026-08）：工件类工具内联渲染后压制后续文本 ──

def _text_events(adapter, content):
    return adapter.feed({
        "event": "on_chat_model_stream",
        "name": "ChatOpenAI",
        "data": {"chunk": type("C", (), {"content": content})()},
    })


def _tool_end(adapter, name, payload):
    return adapter.feed({
        "event": "on_tool_end",
        "name": name,
        "data": {"output": _tool_message_repr(json.dumps(payload, ensure_ascii=False), name)},
    })


def test_s3_suppresses_text_after_artifact_tool():
    """diagnose_barrier 出结果后，模型文本被压制，仅发一句标准过渡"""
    adapter = LangGraphSSEAdapterV2()
    _tool_end(adapter, "diagnose_barrier", {"student_name": "张浩宇", "barrier_distribution": {}})
    assert adapter.suppress_text is True
    out = _text_events(adapter, "以下是核心结论：表述障碍60%…")
    assert len(out) == 2  # phase reply + 过渡文案
    texts = [json.loads(o) for o in out if json.loads(o).get("type") == "text"]
    assert len(texts) == 1
    assert texts[0]["content"] == "诊断报告已生成，见下方图表"
    # 后续文本继续压制，且过渡只发一次
    assert _text_events(adapter, "再补充一些数据…") == []


def test_s3_plan_task_suppresses_text():
    """plan_task 出计划卡后，文本复述被压制，发计划过渡"""
    adapter = LangGraphSSEAdapterV2()
    _tool_end(adapter, "plan_task", {
        "goal": "出5道题", "total_steps": 2,
        "steps": [{"step": 1, "skill": "generate_questions", "description": "出题"}],
    })
    assert adapter.suppress_text is True
    out = _text_events(adapter, "好的，我已将任务拆解为以下步骤…")
    texts = [json.loads(o) for o in out if json.loads(o).get("type") == "text"]
    assert texts[0]["content"] == "任务计划已生成，请查看下方计划卡"


def test_s3_plain_tools_still_stream_text():
    """非工件类工具（如读文件）不压制文本"""
    adapter = LangGraphSSEAdapterV2()
    _tool_end(adapter, "read", {"content": "文件内容", "path": "x.txt"})
    assert adapter.suppress_text is False
    out = _text_events(adapter, "文件读取完成")
    assert len(out) >= 1
    assert json.loads(out[-1])["content"] == "文件读取完成"


def test_s3_batch_tools_suppressed():
    """批次类工具（含 batch_id 等内部标识）文本零复述（2026-08 标识防泄漏）"""
    adapter = LangGraphSSEAdapterV2()
    _tool_end(adapter, "query_ocr_progress", {"summary": "3/5 完成", "batches": {"b1": {}}})
    assert adapter.suppress_text is True
    out = _text_events(adapter, "批次 b1 识别中，batch_id=xxx…")
    texts = [json.loads(o) for o in out if json.loads(o).get("type") == "text"]
    assert texts[0]["content"] == "识别进度如下方卡片"
    assert "batch_id" not in json.dumps(texts, ensure_ascii=False)


def test_approval_needed_emits_awaiting_approval_directly():
    """审批卡不再依赖模型调 request_approval（2026-08）：工具结果带
    approval_needed 时 adapter 直接发 awaiting_approval。"""
    adapter = LangGraphSSEAdapterV2()
    events = _tool_end(adapter, "read", {
        "approval_needed": True,
        "message": "工作区外访问需要批准: /x",
        "target": "/x",
    })
    phases = [json.loads(o) for o in events if json.loads(o).get("type") == "phase"]
    assert len(phases) == 1
    assert phases[0]["phase"] == "awaiting_approval"
    assert "工作区外" in phases[0]["message"]


def test_plan_completion_restores_text_flow():
    """计划全部步骤完成后恢复文本流——agent 执行完必须给最终回复（2026-08）。"""
    adapter = LangGraphSSEAdapterV2()
    # 1) plan_task → 计划卡 + 压制
    _tool_end(adapter, "plan_task", {
        "goal": "出5题保存", "total_steps": 2,
        "steps": [
            {"step": 1, "skill": "generate_questions", "description": "出题"},
            {"step": 2, "skill": "save_to_bank", "description": "保存"},
        ],
    })
    assert adapter.suppress_text is True
    # 中途文本被压制（过渡已发）
    _text_events(adapter, "好的，我现在开始出题…")
    # 2) 第 1 步完成 → 仍在压制
    _tool_end(adapter, "generate_questions", {"total": 5})
    assert adapter.suppress_text is True
    # 3) 第 2 步（最后一步）完成 → 恢复文本流
    _tool_end(adapter, "save_to_bank", {"saved": True})
    assert adapter.suppress_text is False
    out = _text_events(adapter, "已完成：出5道题并保存到题库")
    texts = [json.loads(o) for o in out if json.loads(o).get("type") == "text"]
    assert texts[-1]["content"] == "已完成：出5道题并保存到题库"
    assert _unwrap_tool_message('content="双引号包裹" 的普通文本') == 'content="双引号包裹" 的普通文本'


def test_v2_plain_json_still_works():
    """纯 JSON（非 repr）解析不受影响"""
    adapter = LangGraphSSEAdapterV2()
    events = adapter.feed({
        "event": "on_tool_end",
        "name": "diagnose_barrier",
        "data": {"output": '{"student_name": "李世睿", "total_answers": 10}'},
    })
    evt = json.loads(events[0])
    assert json.loads(evt["result"])["student_name"] == "李世睿"

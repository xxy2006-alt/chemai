"""记录恢复回归（2026-08）：历史接口返回完整结构（user/ai/tool），
重开对话后工具卡与结果完整还原，不再只剩文本。"""
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.channel.conversation import _history_items_from_messages


def test_history_maps_full_structure():
    msgs = [
        HumanMessage(content="读取桌面文件"),
        AIMessage(content="我来读取。", tool_calls=[{"name": "read", "args": {}, "id": "c1"}]),
        ToolMessage(content='{"content": "文件内容", "path": "x.txt", "total_lines": 2}', name="read", tool_call_id="c1"),
        AIMessage(content="已读取完成。"),
    ]
    items = _history_items_from_messages(msgs)
    assert [i["type"] for i in items] == ["user", "ai", "tool", "ai"]
    tool_item = items[2]
    assert tool_item["name"] == "read"
    assert tool_item["status"] == "done"
    assert tool_item["data"]["content"] == "文件内容"


def test_history_tool_error_status():
    msgs = [
        HumanMessage(content="查进度"),
        ToolMessage(content='{"error": "缺少 teacher_id"}', name="list_teacher_exams", tool_call_id="c2"),
    ]
    items = _history_items_from_messages(msgs)
    assert items[1]["status"] == "error"


def test_history_skips_empty_ai():
    """空气泡不复现：空内容 AIMessage 不产出历史条目。"""
    msgs = [
        HumanMessage(content="诊断"),
        AIMessage(content="", tool_calls=[{"name": "diagnose_barrier", "args": {}, "id": "c3"}]),
        ToolMessage(content='{"student_name": "张浩宇"}', name="diagnose_barrier", tool_call_id="c3"),
        AIMessage(content=""),
    ]
    items = _history_items_from_messages(msgs)
    assert [i["type"] for i in items] == ["user", "tool"]


def test_history_non_json_tool_content_kept_as_raw():
    msgs = [
        HumanMessage(content="看目录"),
        ToolMessage(content="total 3\nREADME.md", name="bash", tool_call_id="c4"),
    ]
    items = _history_items_from_messages(msgs)
    tool_item = items[1]
    assert tool_item["data"] is None
    assert tool_item["raw"] == "total 3\nREADME.md"


def test_history_skips_request_approval():
    """审批流程瞬态工具不进历史（避免裸 JSON 卡）。"""
    msgs = [
        HumanMessage(content="读桌面"),
        ToolMessage(content='{"approval_needed": true}', name="read", tool_call_id="c5"),
        ToolMessage(content='"已取消：老师未批准此操作。"', name="request_approval", tool_call_id="c6"),
    ]
    items = _history_items_from_messages(msgs)
    assert [i.get("name") for i in items if i["type"] == "tool"] == ["read"]


def test_history_skips_internal_replay_note():
    """批准重放续接提示（内部注入的 role=user 消息）不进历史：
    否则前端会把整段重放结果渲染成「用户发送端」的巨文。"""
    msgs = [
        HumanMessage(content="读取桌面文件"),
        AIMessage(content="我来读取。", tool_calls=[{"name": "read", "args": {}, "id": "c7"}]),
        ToolMessage(content='{"approval_needed": true}', name="read", tool_call_id="c7"),
        HumanMessage(content="（系统提示：你刚才请求老师批准的操作已获得批准，并已自动重放完成，"
                             "完整结果见上文的工具结果（工具「read」）。请基于该结果继续完成老师的请求。"
                             "如果结果中包含错误，请向老师说明失败原因并给出下一步建议，不要重复调用刚才的工具。）"),
        AIMessage(content="文件内容如下：…"),
    ]
    items = _history_items_from_messages(msgs)
    assert [i["type"] for i in items] == ["user", "ai", "tool", "ai"]
    # 注入提示不渲染成用户消息：user 消息只有用户原文
    assert items[0]["content"] == "读取桌面文件"


def test_history_user_message_starting_with_note_prefix_kept():
    """用户真实消息即使以「（系统提示：」开头也不被误伤（宽松前缀仅匹配
    内部注入的完整句式，此处模拟用户原话不被过滤）。"""
    msgs = [
        HumanMessage(content="（系统提示：这行字是我自己打的，不是注入）"),
    ]
    items = _history_items_from_messages(msgs)
    assert [i["type"] for i in items] == ["user"]
    assert items[0]["content"] == "（系统提示：这行字是我自己打的，不是注入）"

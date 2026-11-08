"""审批门 / 计划执行 的确定性回归（2026-09-14「复杂任务拆解执行」E2E 修出来的）。

背景：计划任务跑到「布置练习」这类步骤时，护栏会拦下并弹确认门。老师点「批准」
之后任务却断在那里 —— 靠 LLM 复跑才能发现问题，而且每次路径还不一样。
这里把两处**真缺陷**钉成确定性断言，与 LLM 无关：

1. `_resolve_resume_intent`：布尔门（assign_adaptive_practice 等 requires_approval
   工具）点「批准」曾被改写成 `"cancelled"` —— 下游确定性重放判定为未批准，
   整个任务停在「等待确认」，**批准等于没批**。
2. `guard._guarded`：被 `requires_approval` 拦下时**没有登记待重放**（只有
   `approval_needed` 那条路登记了）→ 批准后没有东西可重放，链路断。
"""
import asyncio
import json

from agent.guard import GuardState, _make_guarded_tool


def _run(coro):
    async def go():
        return await coro

    return asyncio.run(go())


# ── 1. resume 意图解析 ──────────────────────────────────────────────

def _intent(message: str, pending_name: str):
    from agent.channel.gateway import ChatRequest
    from agent.channel.langgraph_channel import _resolve_resume_intent
    req = ChatRequest(message=message, conversation_id="t-x")
    return _resolve_resume_intent(req, pending_name)


def test_boolean_gate_approval_survives_as_approved():
    """布尔门点「批准」→ user_response 必须是 "approved"（曾被改成 cancelled）。"""
    decision, response = _intent("approved", "assign_adaptive_practice")
    assert response == "approved", f"批准被改写成了 {response!r} —— 任务会断在等待确认"
    assert decision is None, "布尔门没有修订原语，三值决定应为 None（走 legacy）"


def test_boolean_gate_cancel_stays_cancelled():
    _, response = _intent("cancelled", "assign_adaptive_practice")
    assert response == "cancelled"


def test_boolean_gate_feedback_is_not_an_approval():
    """布尔门收到修改意见（非确认词）→ 不是批准。"""
    _, response = _intent("把题量减到 3 道", "assign_adaptive_practice")
    assert response == "把题量减到 3 道", "非确认词应原样透传，不能当成批准"


def test_draft_gate_keeps_three_way_decision():
    """草稿门（发送类）仍保留三值决定 —— 修复不能把这条路压平。"""
    from agent.channel.langgraph_channel import _GATE_PLAN_TOOLS
    names = sorted(_GATE_PLAN_TOOLS)
    assert names, "草稿门工具集不该为空"
    decision, response = _intent("approved", names[0])
    assert decision["action"] == "approve"
    assert decision["draft_id"] == "" and decision["gate_id"] == ""
    assert response == "approved"

    decision2, response2 = _intent("再改改第三周", names[0])
    assert decision2 is None, "非协议词的自由文本不是三值决定"
    assert response2 == "再改改第三周"


# ── 2. 护栏拦下时必须登记待重放 ──────────────────────────────────────

def test_guard_registers_pending_when_blocked_by_requires_approval():
    """被 requires_approval 拦下的调用要登记待重放 —— 否则批准后无事可做。"""
    calls = []

    async def fake_tool(student_id: str = ""):
        """Fake destructive tool."""
        calls.append(student_id)
        return json.dumps({"ok": True})

    gs = GuardState()
    guarded = _make_guarded_tool(fake_tool, gs, requires_approval=True)
    out = json.loads(_run(guarded.ainvoke({"student_id": "241914"})))

    assert out.get("approval_needed") is True, "布尔门拦下返回门卡载荷（ADR-0015 阶段 2）"
    assert out.get("gate_id", "").startswith("g-tool-fake_tool-"), out
    assert calls == [], "未批准时工具不该被执行"
    assert (gs.pending_approval or {}).get("name") == "fake_tool", \
        "拦下时必须登记待重放，否则批准后没有东西可重放（任务断链）"


def test_guard_replays_after_approval():
    """登记之后，批准 → channel 走 pending["fn"] 确定性重放（ADR-0015：
    门开着时 guarded 工具一律全拦，批准后的执行只走重放路径，不再靠
    「approved 置位 + 重调 guarded 工具」——那是粘性提权的旧模型）。"""
    calls = []

    async def fake_tool(student_id: str = ""):
        """Fake destructive tool."""
        calls.append(student_id)
        return json.dumps({"ok": True})

    gs = GuardState()
    guarded = _make_guarded_tool(fake_tool, gs, requires_approval=True)
    _run(guarded.ainvoke({"student_id": "241914"}))
    assert calls == []

    # 门开着时即使 approved 置位也拦（防未决门被绕过）
    gs.approved = True
    out = json.loads(_run(guarded.ainvoke({"student_id": "241914"})))
    assert out.get("gate_open_blocked") is True, out
    assert calls == [], "门开着时不得执行"

    # 批准后的真实执行路径：清 pending + 调登记的裸 fn（channel _direct_replay_events 同款）
    pending = gs.pending_approval
    gs.pending_approval = None
    replayed = _run(pending["fn"](**pending["kwargs"]))
    assert json.loads(replayed).get("ok") is True
    assert calls == ["241914"], "批准后必须真的执行"

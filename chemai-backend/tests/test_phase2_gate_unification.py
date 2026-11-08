"""阶段 2 — 确认门合一（issue #18 阶段 2；ADR-0015）。

通用 gate 实体（agent_gates 表）：draft / boolean 两个 adapter 落同一 seam。
- gate_id 身份：草稿门 g-draft-{draft_id}；布尔门 g-tool-{tool}-{hash}。
- 一决定一动作：决定带 gate_id，与开着的门不一致 → 拒绝执行 + 重发门状态
  （回归红线④：批准门 A 时不得执行门 B 的动作）。
- 门开互斥：每会话一个开着的门；后开的门被全拦（阶段 1 已拦工具，这里钉实体层）。
- 重放后补 dedup 登记：LLM 重调同参工具命中「重复调用」，不再双执行（回归红线⑥）。
"""
import asyncio
import hashlib
import json

import pytest

from agent.guard import GuardState, _make_guarded_tool


def _run(coro):
    async def go():
        return await coro
    return asyncio.run(go())


def _make_draft(db, student_id="s1", created_by="t1") -> str:
    """直接建一条 awaiting 草稿行（不走 LLM），返回 draft_id。"""
    import uuid as _u
    from app.models.database import LearningPlanDraft
    did = _u.uuid4().hex[:12]
    db.add(LearningPlanDraft(
        draft_id=did, student_id=student_id, version=1,
        status="awaiting_confirmation", content={"plan_title": "t"},
        created_by=created_by))
    db.commit()
    return did


# ── 1. gate_id 身份 ──────────────────────────────────────────────────

def test_draft_gate_id_is_stable_per_draft():
    from app.services.gate_service import draft_gate_id, boolean_gate_id
    assert draft_gate_id("d1") == "g-draft-d1"
    assert draft_gate_id("d1") == draft_gate_id("d1")
    assert draft_gate_id("d2") != draft_gate_id("d1")

    kwargs = {"student_id": "s1", "draft_id": "d1"}
    bid = boolean_gate_id("assign_adaptive_practice", kwargs)
    assert bid.startswith("g-tool-assign_adaptive_practice-")
    assert len(bid) == len("g-tool-assign_adaptive_practice-") + 8
    assert bid == boolean_gate_id("assign_adaptive_practice", dict(kwargs))
    assert bid != boolean_gate_id("assign_adaptive_practice", {"student_id": "s2"})


def test_gate_entity_open_decide_replay_lifecycle(db_session, monkeypatch):
    """实体生命周期：open → decide(approve) → executed；草稿门绑定 draft。"""
    import app.models.database as dbmod

    def _fake_get_db():
        yield db_session
    monkeypatch.setattr(dbmod, "get_db", _fake_get_db)

    did = _make_draft(db_session)

    from app.services.gate_service import gate_service
    gid = gate_service.open_gate(
        db_session, conversation_id="t1", kind="draft",
        tool_name="send_learning_plan",
        kwargs={"student_id": "s1", "draft_id": did},
        draft_id=did, version=1, action="send_student",
        message="学习计划（第 1 版）等待确认")
    assert gid == f"g-draft-{did}"

    open_gate = gate_service.get_open_gate(db_session, "t1")
    assert open_gate is not None
    assert open_gate["gate_id"] == gid
    assert open_gate["kind"] == "draft"
    assert open_gate["kwargs"] == {"student_id": "s1", "draft_id": did}

    gate_service.close_gate(db_session, gid, "executed")
    assert gate_service.get_open_gate(db_session, "t1") is None


def test_boolean_gate_entity_survives_in_db(db_session, monkeypatch):
    """布尔门实体化：拦下即登记实体，重启后 /history 可重建（ADR-0015 §2）。"""
    import app.models.database as dbmod

    def _fake_get_db():
        yield db_session
    monkeypatch.setattr(dbmod, "get_db", _fake_get_db)

    from app.services.gate_service import gate_service
    kwargs = {"student_id_or_class_id": "s1", "knowledge_points": ["氧化还原"]}
    gid = gate_service.open_gate(
        db_session, conversation_id="t2", kind="boolean",
        tool_name="assign_adaptive_practice", kwargs=kwargs,
        action="", message="布置练习需要确认")
    open_gate = gate_service.get_open_gate(db_session, "t2")
    assert open_gate["gate_id"] == gid
    assert open_gate["kind"] == "boolean"
    assert open_gate["tool_name"] == "assign_adaptive_practice"


# ── 2. 强绑定：决定带错 gate_id → 拒绝 + 重发门状态 ──────────────────

def test_decision_with_wrong_gate_id_is_rejected(db_session, monkeypatch):
    import app.models.database as dbmod

    def _fake_get_db():
        yield db_session
    monkeypatch.setattr(dbmod, "get_db", _fake_get_db)

    did = _make_draft(db_session)
    gid = f"g-draft-{did}"

    from app.services.gate_service import gate_service
    gate_service.open_gate(db_session, conversation_id="t3", kind="draft",
                           tool_name="send_learning_plan",
                           kwargs={"student_id": "s1", "draft_id": did},
                           draft_id=did, version=1, action="send_student",
                           message="等待确认")

    result = gate_service.check_binding(db_session, "t3", "g-draft-OTHER")
    assert result is not None, "gate_id 不一致必须拒绝（回归红线④）"
    gate = result["open_gate"]
    assert gate["gate_id"] == gid
    assert "gate_mismatch" in result

    assert gate_service.check_binding(db_session, "t3", gid) is None
    # 未带 gate_id（旧客户端）+ 单门开着 → 放行
    assert gate_service.check_binding(db_session, "t3", "") is None


# ── 3. 重放后 dedup 补登记 —— 不再双执行 ─────────────────────────────

def test_replay_remembers_call_so_llm_recall_hits_dedup():
    """回归红线⑥：重放执行后补 dedup 登记——LLM 重调同参工具被拦，
    assign_adaptive_practice / delete_bank 不再双布置。"""
    calls: list = []

    async def fake_tool(student_id: str = ""):
        """Fake destructive tool."""
        calls.append(student_id)
        return json.dumps({"ok": True})

    gs = GuardState()
    guarded = _make_guarded_tool(fake_tool, gs, requires_approval=True)
    _run(guarded.ainvoke({"student_id": "241914"}))
    assert calls == []
    assert gs.pending_approval is not None

    # channel 重放：清 pending + 裸 fn 执行 + 补 dedup 登记
    pending = gs.pending_approval
    gs.pending_approval = None
    gs.remember_call(pending["name"], pending["kwargs"])
    _run(pending["fn"](**pending["kwargs"]))
    assert calls == ["241914"]

    # LLM 重调同参 → dedup 拦截，不双执行
    out = json.loads(_run(guarded.ainvoke({"student_id": "241914"})))
    assert out.get("dedup_skipped") is True, out
    assert calls == ["241914"], "重放后重调不得二次执行"


# ── 4. 布尔门拦下即返回门卡载荷（adapter 据此发卡，不再靠 interrupt）──

def test_requires_approval_block_returns_gate_card_payload():
    """布尔门拦下 → approval_needed + gate 信息（与草稿门同构的卡事件来源）。"""
    async def fake_tool(student_id: str = ""):
        """Fake destructive tool."""
        return json.dumps({"ok": True})

    gs = GuardState()
    gs.conversation_id = "t9"
    guarded = _make_guarded_tool(fake_tool, gs, requires_approval=True)
    out = json.loads(_run(guarded.ainvoke({"student_id": "241914"})))
    assert out.get("approval_needed") is True, out
    assert out.get("gate_id", "").startswith("g-tool-fake_tool-"), out
    assert "gate_open_blocked" not in out


def test_agent_no_longer_has_request_approval_tool():
    """interrupt() 退役：v2 工具集里不再有 request_approval（ADR-0015 §2）。"""
    from agent.langgraph_agent_v2 import ALL_TOOLS, _TOOL_BY_NAME
    assert "request_approval" not in _TOOL_BY_NAME
    names = {getattr(t, "__name__", "") for t in ALL_TOOLS}
    assert "request_approval" not in names

"""阶段 3 — 运行生命周期与显式恢复（issue #18 阶段 3；ADR-0016）。

- 孤儿中断 / 毒化线程：恢复走「纯状态标记 + 自动迁移」，恢复路径绝不调用模型
  （回归红线⑤：孤儿中断处理路径不得出现任何模型调用）。
- Paused Run：run 实体新增 paused 状态，get_active_run 可见。
- 每会话锁：争用立即 409（不排队）。
- run/gate 事实源在 DB：reset/删除会话后 gate 实体一并清理。
"""
import asyncio
from types import SimpleNamespace

import pytest


# ── 1. 恢复路径零模型调用（回归红线⑤）────────────────────────────────

def test_repair_thread_state_never_invokes_model_on_orphan_interrupt():
    """孤儿中断 → 迁移重建，绝不 ainvoke(Command(resume=...)) 偷跑完整回合。"""
    from agent.channel.langgraph_channel import _repair_thread_state

    calls = {"ainvoke": 0}

    class PoisonedAgent:
        async def aget_state(self, config):
            return SimpleNamespace(
                values={"messages": []},
                next=(SimpleNamespace(),),  # 未决中断
                tasks=(),
            )

        async def ainvoke(self, *_a, **_k):
            calls["ainvoke"] += 1
            return {}

        async def aupdate_state(self, *_a, **_k):
            return None

    ok, reason, cfg = asyncio.run(_repair_thread_state(PoisonedAgent(), {}, "t-x"))
    assert calls["ainvoke"] == 0, "恢复路径出现模型调用——隐藏 turn 回归"
    assert ok is True, "孤儿中断应可继续（迁移后），不得永久阻断"


def test_poisoned_thread_auto_migrates():
    """任务带 error（毒化）→ 自动迁移新线程（老师无感），零模型调用。"""
    from agent.channel.langgraph_channel import _repair_thread_state, _THREAD_OVERRIDES

    class PoisonedAgent:
        async def aget_state(self, config):
            return SimpleNamespace(
                values={"messages": []}, next=(),
                tasks=(SimpleNamespace(error="OpenAI 400: insufficient tool messages"),),
            )

        async def ainvoke(self, *_a, **_k):
            raise AssertionError("毒化线程不得调用模型（回归红线⑤）")

        async def aupdate_state(self, _config, _payload):
            return None

    _THREAD_OVERRIDES.pop("t-y", None)
    ok, reason, cfg = asyncio.run(_repair_thread_state(PoisonedAgent(), {}, "t-y"))
    assert ok is True
    assert cfg["configurable"]["thread_id"] != "t-y", "必须迁移到新线程"
    assert _THREAD_OVERRIDES.get("t-y") == cfg["configurable"]["thread_id"]
    _THREAD_OVERRIDES.pop("t-y", None)


def test_migration_failure_reports_blocked():
    """迁移失败（如历史不可复制）→ 明确阻断并给出友好原因，不静默。"""
    from agent.channel.langgraph_channel import _repair_thread_state

    class BrokenAgent:
        async def aget_state(self, config):
            return SimpleNamespace(
                values={"messages": [object()]}, next=(),
                tasks=(SimpleNamespace(error="boom"),),
            )

        async def ainvoke(self, *_a, **_k):
            raise AssertionError("毒化线程不得调用模型")

        async def aupdate_state(self, _config, _payload):
            raise RuntimeError("copy failed")

    ok, reason, cfg = asyncio.run(_repair_thread_state(BrokenAgent(), {}, "t-z"))
    assert ok is False
    assert "损坏" in reason or "新对话" in reason


# ── 2. Paused Run 实体状态 ───────────────────────────────────────────

def test_run_paused_status_roundtrip(db_session):
    from app.services.plan_run_service import plan_run_service as run_svc

    run_svc.start_run(db_session, "conv-p", "goal", [
        {"step": 1, "skill": "generate_learning_plan", "status": "running"},
        {"step": 2, "skill": "send_learning_plan", "status": "pending"},
    ])
    run_svc.mark_run_paused(db_session, "conv-p")
    run = run_svc.get_active_run(db_session, "conv-p")
    assert run is not None, "paused 的 run 对重同步可见"
    assert run["status"] == "paused"
    assert run["steps"][0]["status"] == "running", "暂停时步状态原样保留"

    run_svc.mark_run_resumed(db_session, "conv-p")
    assert run_svc.get_active_run(db_session, "conv-p")["status"] == "running"


def test_mark_step_keeps_run_active_when_paused(db_session):
    """暂停中的 run 收到步转移（门决定）→ 自动回到 running。"""
    from app.services.plan_run_service import plan_run_service as run_svc

    run_svc.start_run(db_session, "conv-p2", "goal", [
        {"step": 1, "skill": "send_learning_plan", "status": "awaiting_confirmation"},
    ])
    run_svc.mark_run_paused(db_session, "conv-p2")
    run_svc.mark_step(db_session, "conv-p2", 1, "running")
    run = run_svc.get_active_run(db_session, "conv-p2")
    assert run["status"] == "running", "决定驱动转移即显式恢复"


# ── 3. 每会话锁：争用 409 ────────────────────────────────────────────

def test_conversation_lock_contention_returns_409():
    from fastapi import HTTPException
    from agent.channel.langgraph_channel import acquire_conversation_lock

    async def probe():
        lock = await acquire_conversation_lock("conv-lock")
        try:
            with pytest.raises(HTTPException) as ei:
                await acquire_conversation_lock("conv-lock")
            return ei.value.status_code
        finally:
            lock.release()

    assert asyncio.run(probe()) == 409


def test_locked_stream_iterates_async_generator_and_releases():
    """回归：_locked_stream 必须 async for 迭代异步生成器——普通 for 会
    TypeError: 'async_generator' object is not iterable，所有流式回复即 500
    （2026-09-20 用户实测「请求失败：network error」的根因）。"""
    from agent.channel.langgraph_channel import _locked_stream, acquire_conversation_lock

    async def probe():
        lock = await acquire_conversation_lock("conv-ls")
        def gen_factory():
            async def gen():
                yield "x"
            return gen()
        resp = _locked_stream(lock, gen_factory)
        got = [c async for c in resp.body_iterator]
        # 流结束后锁必须已释放：再次获取不得 409
        lock2 = await acquire_conversation_lock("conv-ls")
        lock2.release()
        return got

    assert asyncio.run(probe()) == ["x"]


def test_conversation_lock_released_after_use():
    from agent.channel.langgraph_channel import acquire_conversation_lock

    async def probe():
        lock = await acquire_conversation_lock("conv-lock2")
        lock.release()
        # 释放后可再次获取（不抛 409）
        return await acquire_conversation_lock("conv-lock2")

    assert asyncio.run(probe()) is not None


# ── 4. 会话清理顺带清 gate 实体 ──────────────────────────────────────

def test_gate_cleanup_on_conversation_reset(db_session, monkeypatch):
    import app.models.database as dbmod

    def _fake_get_db():
        yield db_session
    monkeypatch.setattr(dbmod, "get_db", _fake_get_db)

    from app.services.gate_service import gate_service
    gate_service.open_gate(db_session, "conv-gone", kind="boolean",
                           tool_name="delete_bank", kwargs={},
                           action="", message="需要确认")
    assert gate_service.get_open_gate(db_session, "conv-gone") is not None

    gate_service.close_conversation(db_session, "conv-gone")
    assert gate_service.get_open_gate(db_session, "conv-gone") is None, \
        "重置/删除会话后不得留下幽灵门"

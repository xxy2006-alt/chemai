"""2026-08 连续重复调用护栏 + LLM 重试策略单元测试（DSH llm-retry / repeat-tool-reminder 借鉴落地）。

运行：python -m pytest tests/test_guard_repeat_reminder.py -q
"""
import asyncio
import json

from agent.guard import (
    GuardState, _repeat_reminder, _REPEAT_THRESHOLDS, _make_guarded_tool,
)


def test_repeat_counter_and_thresholds():
    gs = GuardState()
    assert gs.track_repeat("read", {"path": "a.md"}) == 1
    assert gs.track_repeat("read", {"path": "a.md"}) == 2
    assert gs.track_repeat("read", {"path": "a.md"}) == 3
    assert 3 in _REPEAT_THRESHOLDS
    # 换参数 → 重置为 1
    assert gs.track_repeat("read", {"path": "b.md"}) == 1
    # 连续到 5 → 严厉提醒
    for _ in range(3):
        gs.track_repeat("read", {"path": "b.md"})
    assert gs.track_repeat("read", {"path": "b.md"}) == 5
    assert "警告" in _repeat_reminder("read", 5)


def test_begin_turn_resets():
    gs = GuardState()
    gs.track_repeat("read", {"path": "a.md"})
    gs.track_repeat("read", {"path": "a.md"})
    gs.begin_turn()
    assert gs.consecutive_repeats == 0
    assert gs.last_call_key is None
    # 新轮从 1 重新计数（跨轮不累计）
    assert gs.track_repeat("read", {"path": "a.md"}) == 1


def test_guarded_injects_reminder():
    """被去重拦截的重复尝试也算连续重复；第 3 次结果带 _reminder，不破坏原字段。"""

    async def fake_tool(path: str = "") -> str:
        """fake read tool for guard test"""
        return json.dumps({"content": f"内容{path}", "chars": 3}, ensure_ascii=False)

    gs = GuardState()
    wrapped = _make_guarded_tool(fake_tool, gs)

    async def run():
        r1 = await wrapped.ainvoke({"path": "x.md"})
        r2 = await wrapped.ainvoke({"path": "x.md"})
        r3 = await wrapped.ainvoke({"path": "x.md"})
        d1, d2, d3 = (json.loads(x) for x in (r1, r2, r3))
        assert "_reminder" not in d1
        assert d1["content"] == "内容x.md"
        assert "dedup_skipped" in d2 and "_reminder" not in d2
        assert "dedup_skipped" in d3 and "_reminder" in d3 and "第 3 次" in d3["_reminder"]

    asyncio.run(run())


def test_retry_policy():
    from agent.provider.deepseek import _is_retryable, _retry_delay, _RETRY_MAX

    assert _is_retryable(408) and _is_retryable(429) and _is_retryable(500)
    assert _is_retryable(502) and _is_retryable(503) and _is_retryable(504)
    assert not _is_retryable(400) and not _is_retryable(401) and not _is_retryable(200)

    import httpx

    assert _is_retryable(None, httpx.ConnectError("x"))
    assert _is_retryable(None, httpx.TimeoutException("x"))
    assert not _is_retryable(None, ValueError("x"))

    assert _RETRY_MAX == 2
    # 500ms 起、指数退避；基数封顶 10s，±10% 抖动在封顶之后叠加 → 实际最大 11s
    assert 0.45 <= _retry_delay(1) <= 0.55
    assert 0.9 <= _retry_delay(2) <= 1.1
    assert 9.0 <= _retry_delay(20) <= 11.0

"""
L4 metrics unit tests (Spec 02) — fake agents and canned messages, zero API.

Pins the external contract of the instrumentation seam:
  extract_metrics(agent_result, start) -> {latency_s, tokens, iterations}
  check_slo(metrics) -> warn lines only (soft warnings, never a gate)
  invoke_with_metrics(agent, payload) -> (result, metrics)
"""
import asyncio
import time

from evals.metrics import DEFAULT_SLO, check_slo, extract_metrics, invoke_with_metrics


class _Msg:
    def __init__(self, mtype, usage=None):
        self.type = mtype
        self.usage_metadata = usage


def test_extract_metrics_counts_ai_turns_and_tokens():
    result = {
        "messages": [
            {"type": "human"},
            _Msg("ai", usage={"input_tokens": 100, "output_tokens": 50}),
            _Msg("ai", usage={"input_tokens": 200, "output_tokens": 75}),
        ],
    }
    m = extract_metrics(result, time.time() - 3.5)
    assert m["iterations"] == 2
    assert m["tokens"] == 425
    assert m["latency_s"] >= 3.4


def test_extract_metrics_tokens_none_without_usage():
    result = {"messages": [_Msg("human"), _Msg("ai")]}
    m = extract_metrics(result, time.time() - 1)
    assert m["iterations"] == 1
    assert m["tokens"] is None, "no usage_metadata -> tokens must stay None (未测量)"


def test_check_slo_flags_violations():
    warnings = check_slo({"latency_s": 90, "tokens": 60000, "iterations": 20})
    assert len(warnings) == 3
    assert any("latency" in w for w in warnings)
    assert any("tokens" in w for w in warnings)
    assert any("iterations" in w for w in warnings)


def test_check_slo_quiet_within_limits():
    assert check_slo({"latency_s": 10, "tokens": 1000, "iterations": 5}) == []


def test_check_slo_skips_unmeasured():
    assert check_slo({"latency_s": 10, "tokens": None, "iterations": 5}) == []


def test_invoke_with_metrics_wraps_agent():
    class FakeAgent:
        async def ainvoke(self, payload, config=None):
            return {"messages": [_Msg("human"), _Msg("ai", usage={"input_tokens": 10, "output_tokens": 5})]}

    result, metrics = asyncio.run(invoke_with_metrics(FakeAgent(), {"messages": []}))
    assert result["messages"][1].type == "ai"
    assert metrics["iterations"] == 1
    assert metrics["tokens"] == 15
    assert metrics["latency_s"] >= 0


def test_default_slo_aligned_with_recursion_limit():
    assert DEFAULT_SLO["max_iterations"] == 12, "SLO must stay aligned with v2 recursion_limit"

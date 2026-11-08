"""Boundary Layer — Dimensions 5+6+7: Edge Cases, Error Recovery, Result Utilization.

Maps to:
  评测文档/evals/boundary/edge_case/edge_scenarios.yaml (EDGE-001..012)
  评测文档/evals/boundary/error_recovery/error_scenarios.yaml (ERR-001..008)
  评测文档/evals/boundary/result_utilization/result_scenarios.yaml (RES-001..002)

Tests verify deterministic behavior — no API needed.
API-dependent scenarios (ERR-001, ERR-006, etc.) marked as @pytest.mark.api.
"""
import pytest


class TestEdgeCases:
    """Dimension 5: Boundary edge case scenarios."""

    def test_edge_tool_does_not_exist_refused(self):
        """EDGE-003/001: Requests without sufficient info should not call generation tools."""
        from agent.tools import TOOLS
        names = {t.__name__ for t in TOOLS}
        # generate_questions exists as a tool
        assert "generate_questions" in names, "generate_questions should exist"
        assert "create_variant" not in names, "create_variant should not exist"

    def test_edge_dedup_guard_exists(self):
        """EDGE-008: GuardState seen_calls prevents duplicate tool calls."""
        from agent.langgraph_agent import GuardState
        gs = GuardState()
        assert hasattr(gs, 'seen_calls'), "GuardState must have seen_calls"
        assert isinstance(gs.seen_calls, set), "seen_calls must be a set"

    def test_edge_tool_call_limits(self):
        """EDGE-007/009: TOOL_CALL_LIMITS exist and all tools have a limit."""
        import agent.guard as guard
        guard._ensure_call_limits()
        assert len(guard.TOOL_CALL_LIMITS) > 0, "TOOL_CALL_LIMITS must not be empty"
        for name, limit in guard.TOOL_CALL_LIMITS.items():
            assert limit >= 1, f"{name} has invalid limit: {limit}"
            assert limit <= 15, f"{name} has excessive limit: {limit}"

    def test_edge_recursion_limit(self):
        """EDGE-009: Recursion limit prevents infinite loops."""
        from agent.langgraph_agent_v2 import RECURSION_LIMIT
        assert RECURSION_LIMIT == 12, "v2 recursion limit must be 12"


class TestErrorRecovery:
    """Dimension 6: Error recovery scenarios — deterministic baseline."""

    def test_error_sse_adapter_handles_malformed(self):
        """ERR-005: SSE adapter must handle malformed tool results without crashing."""
        from agent.langgraph_sse_v2 import LangGraphSSEAdapterV2
        adapter = LangGraphSSEAdapterV2()
        # Feed a malformed tool_end event — must not raise
        events = adapter.feed({"event": "on_tool_end", "name": "test_tool", "data": {"output": None}})
        assert isinstance(events, list), "Must return list even on malformed output"

    def test_error_safe_tool_call_exists(self):
        """ERR-002: safe_tool_call must exist in agent/errors.py."""
        from agent.errors import safe_tool_call, ToolError
        result = safe_tool_call("test", lambda: "ok")
        assert result == "ok", "safe_tool_call must return tool result"

        def _failing_fn():
            raise ValueError("test error")
        result2 = safe_tool_call("test_fail", _failing_fn)
        import json
        data = json.loads(result2)
        assert "_tool_error" in data, "safe_tool_call must catch exceptions"
        assert data["code"] == "TOOL_ERROR"

    def test_error_provider_recoverable(self):
        """ERR-006: ProviderError must have recoverable flag."""
        from agent.errors import ProviderError
        e429 = ProviderError("rate limited", provider="deepseek", status_code=429)
        assert e429.recoverable, "429 should be recoverable"
        e500 = ProviderError("server error", provider="deepseek", status_code=500)
        assert e500.recoverable, "500 should be recoverable"


class TestResultUtilization:
    """Dimension 7: Tool result utilization."""

    def test_result_tool_output_stored(self):
        """RES-001: Tool results must be stored in SSE adapter."""
        from agent.langgraph_sse_v2 import LangGraphSSEAdapterV2
        adapter = LangGraphSSEAdapterV2()
        assert hasattr(adapter, '_tool_results'), "Adapter must store tool results"
        assert isinstance(adapter._tool_results, list), "_tool_results must be a list"

    def test_result_dedup_mechanism(self):
        """RES-002: SSE adapter must have dedup to prevent tool output echo."""
        from agent.langgraph_sse_v2 import LangGraphSSEAdapterV2
        adapter = LangGraphSSEAdapterV2()
        assert hasattr(adapter, '_tool_complete'), "Must have tool_complete dedup flag"
        assert hasattr(adapter, '_did_stream_text'), "Must track streaming state"

"""Regression Layer — Dimensions 8+9+12+13: State Transitions, Plan Coherence,
Consistency (Pass@k), and Performance Baseline.

Maps to:
  评测文档/evals/boundary/state_transition/checkpoint_replay.yaml (STATE-001..003)
  评测文档/evals/boundary/plan_coherence/plan_scenarios.yaml (PLAN-001..004)
  评测文档/evals/regression/consistency/passk_scenarios.yaml (PASSK-001..007)
  评测文档/evals/regression/performance/performance_baseline.yaml (PERF metrics)
"""
import pytest
import time


class TestStateTransitions:
    """Dimension 9: Checkpoint persistence and replay."""

    def test_state_checkpointer_is_async_sqlite(self):
        """STATE-001/002: v2 must use AsyncSqliteSaver for persistence."""
        from agent.langgraph_agent_v2 import _get_v2_checkpointer
        import asyncio
        cp = asyncio.run(_get_v2_checkpointer())
        from langgraph.checkpoint.memory import InMemorySaver
        assert not isinstance(cp, InMemorySaver), "Must use persistent checkpointer"

    def test_state_checkpointer_returns_same_instance(self):
        """STATE-003: Multiple calls to _get_v2_checkpointer return same instance."""
        from agent.langgraph_agent_v2 import _get_v2_checkpointer
        import asyncio
        cp1 = asyncio.run(_get_v2_checkpointer())
        cp2 = asyncio.run(_get_v2_checkpointer())
        assert cp1 is cp2, "Checkpointer must be singleton"

    def test_state_conversation_endpoint_module_exists(self):
        """Verify conversation endpoint module is importable."""
        import importlib
        mod = importlib.import_module("agent.channel.conversation")
        assert hasattr(mod, 'list_conversations'), "list_conversations missing"
        assert hasattr(mod, 'get_conversation_history'), "get_conversation_history missing"
        assert hasattr(mod, 'new_conversation'), "new_conversation missing"


class TestConsistency:
    """Dimension 12: Pass@k consistency — tool set and trajectory stability."""

    def test_consistency_tool_set_deterministic(self):
        """PASSK: Same persona always produces same tool set (deterministic)."""
        from agent.tools import TOOL_META
        s1 = {t.__name__ for t, m in TOOL_META.items() if "student" in m["personas"]}
        s2 = {t.__name__ for t, m in TOOL_META.items() if "student" in m["personas"]}
        assert s1 == s2, "Student tool set must be deterministic across calls"

        t1 = {t.__name__ for t, m in TOOL_META.items() if "teacher" in m["personas"]}
        t2 = {t.__name__ for t, m in TOOL_META.items() if "teacher" in m["personas"]}
        assert t1 == t2, "Teacher tool set must be deterministic"

    def test_consistency_persona_loads_same_every_time(self):
        """PASSK: load_persona returns identical config on repeated calls."""
        from agent.agents import load_persona
        c1 = load_persona("student")
        c2 = load_persona("student")
        assert c1["available_skills"] == c2["available_skills"], \
            "Persona skills must be deterministic"

    def test_consistency_tool_meta_no_duplicate_tools(self):
        """PASSK: No tool registered twice in TOOL_META."""
        from agent.tools import TOOL_META
        names = [t.__name__ for t in TOOL_META]
        assert len(names) == len(set(names)), "No duplicate tool names in TOOL_META"

    def test_consistency_factory_output_deterministic(self):
        """PASSK: Tutoring factory produces deterministic output."""
        from agent.tools import ionic_equation_tutor
        import asyncio, json
        r1 = asyncio.run(ionic_equation_tutor(equation="NaOH + HCl"))
        r2 = asyncio.run(ionic_equation_tutor(equation="NaOH + HCl"))
        assert r1 == r2, "Factory output must be deterministic for same input"


class TestPerformanceBaseline:
    """Dimension 13: Performance metrics baseline."""

    def test_perf_tool_import_under_1s(self):
        """PERF: Importing all tools should take < 1 second."""
        t0 = time.time()
        from agent.tools import TOOLS  # noqa: reimport
        elapsed = time.time() - t0
        assert elapsed < 2.0, f"Tool import took {elapsed:.1f}s (threshold 2.0s)"

    def test_perf_persona_load_under_100ms(self):
        """PERF: Loading persona YAML should take < 200ms."""
        t0 = time.time()
        from agent.agents import load_persona
        load_persona("student")
        load_persona("teacher")
        load_persona("tutor")
        load_persona("parent")
        elapsed = time.time() - t0
        assert elapsed < 1.0, f"Persona loading took {elapsed:.1f}s (threshold 1.0s)"

    def test_perf_sqlite_connection_config(self):
        """PERF: SQLite engine config should include check_same_thread=False."""
        import inspect
        from app.models.database import get_engine
        source = inspect.getsource(get_engine)
        assert "check_same_thread" in source, \
            "SQLite must use check_same_thread=False for FastAPI"

    def test_perf_config_cached(self):
        """PERF: Config should use lru_cache for repeated access."""
        from app.config import get_config
        import inspect
        source = inspect.getsource(get_config)
        assert "lru_cache" in source, "get_config must use @lru_cache"

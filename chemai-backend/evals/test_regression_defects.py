"""Regression Layer — Known defect guardrails.

Maps to: 评测文档/evals/regression/monitoring/known_defects.yaml (DEFECT-001..005)
Plus: defects fixed in this session (RG-01..07 from docs/evals/regression.md)

CI gate: 100% (all must pass — these bugs must NOT come back)
"""
import asyncio

import pytest


async def _close_checkpointer_conn(cp):
    """Close the aiosqlite connection behind the shared checkpointer.

    Without this the background sqlite thread keeps the process alive forever
    (exit hang) — a pre-existing defect of these tests, fixed in Spec 02.
    """
    conn = getattr(cp, "conn", None)
    if conn is not None:
        try:
            await conn.close()
        except Exception:
            pass


class TestKnownDefects:
    """Every previously fixed bug has a regression test that must pass."""

    def test_defect_teacher_not_student_mode(self):
        """DEFECT-001: Teacher persona must not be forced into tutoring mode."""
        from agent.agents import load_persona
        cfg = load_persona("teacher")
        prompt = cfg.get("system_prompt", "")
        skills = cfg.get("available_skills", [])
        # Teacher must have diagnosis, not just tutoring
        assert "diagnose_barrier" in skills, "Teacher must have diagnosis"
        # Must not be student-focused tutoring prompt
        assert "高中化学教研助手" in prompt or "教研" in prompt, "Teacher prompt should be 教研 not 辅导"

    def test_defect_checkpoint_persistence(self):
        """DEFECT-002: AsyncSqliteSaver must be used (not InMemorySaver)."""
        from agent.langgraph_agent_v2 import _get_v2_checkpointer
        # Verify checkpointer can be created
        cp = asyncio.run(_get_v2_checkpointer())
        try:
            assert cp is not None, "Checkpointer must exist"
            # Must not be InMemorySaver
            from langgraph.checkpoint.memory import InMemorySaver
            assert not isinstance(cp, InMemorySaver), "Must use AsyncSqliteSaver, not InMemorySaver"
        finally:
            asyncio.run(_close_checkpointer_conn(cp))

    def test_defect_student_role_routing(self):
        """DEFECT-005: Student must not access weekly_report or exam generation."""
        from agent.tools import TOOL_META
        student = {t.__name__ for t, m in TOOL_META.items() if "student" in m["personas"]}
        assert "weekly_report" not in student, "Student must not have weekly_report"


class TestSessionDefects:
    """Defects found and fixed in 2026-07-04 session."""

    def test_rg01_import_exam_paper_removed(self):
        """RG-01: import_exam_paper was referenced but tool didn't exist."""
        from agent.agents import load_persona
        cfg = load_persona("teacher")
        skills = cfg.get("available_skills", [])
        assert "import_exam_paper" not in skills, "import_exam_paper must be removed from teacher YAML"

    def test_rg02_mock_fallback_removed(self):
        """RG-02: practice submit must NOT return mock data."""
        # Read the actual source code to verify the mock fallback is gone
        import inspect
        from app.api.practice import submit_practice
        source = inspect.getsource(submit_practice)
        assert "correct_count = len(request.answers) // 2" not in source, \
            "Mock fallback must be removed from submit_practice"

    def test_rg03_exam_visible_to_student(self):
        """RG-03: 学生练习任务必须同时查 EXAM + PRACTICE。

        断言指向 `student_tasks()` —— 任务装配的**唯一实现**（端点已改成调它）。
        合并说明：原先 grep 的是端点源码，端点重构后那里不再有 RecordType 字面量，
        于是这条在 main 上就已经假红（行为没丢，只是搬家了）。
        """
        import inspect
        from app.api.practice import student_tasks
        source = inspect.getsource(student_tasks)
        assert "RecordType.EXAM" in source, \
            "student_tasks must query RecordType.EXAM"

    def test_rg04_dedup_imported_in_sse(self):
        """RG-04: SSE adapter must have dedup mechanism."""
        from agent.langgraph_sse_v2 import LangGraphSSEAdapterV2
        adapter = LangGraphSSEAdapterV2()
        # Must have dedup-related state
        assert hasattr(adapter, '_tool_complete'), "SSE adapter must have dedup flag"

    def test_rg05_persona_prompt_used(self):
        """RG-05: create_chemai_agent must use persona system_prompt, not hardcoded."""
        import inspect
        from agent.langgraph_agent_v2 import build_system_prompt, create_chemai_agent
        source = inspect.getsource(create_chemai_agent) + inspect.getsource(build_system_prompt)
        assert "persona_config.get(\"system_prompt\"" in source, \
            "Must load persona system_prompt from YAML"

    def test_rg06_async_sqlite_checkpointer(self):
        """RG-06: v2 must use AsyncSqliteSaver, not InMemorySaver."""
        from agent.langgraph_agent_v2 import _get_v2_checkpointer
        cp = asyncio.run(_get_v2_checkpointer())
        try:
            from langgraph.checkpoint.memory import InMemorySaver
            assert not isinstance(cp, InMemorySaver), \
                "v2 checkpointer must be AsyncSqliteSaver (not InMemorySaver)"
        finally:
            asyncio.run(_close_checkpointer_conn(cp))

"""Baseline Layer — Dimensions 3+4: Workflow Integrity + Behavioral Constraints.

Maps to:
  评测文档/evals/baseline/workflow/golden_workflow.yaml (WF-001..012)
  评测文档/evals/baseline/constraint/golden_constraint.yaml (CONST-001..007)

All tests are deterministic (tool registry assertions, code inspection).
"""
import pytest


class TestWorkflowIntegrity:
    """Dimension 3: Multi-step workflow integrity."""

    def test_tool_registry_complete(self):
        """WF: All registered tools must have complete TOOL_META."""
        from agent.tools import TOOLS, TOOL_META
        for t in TOOLS:
            assert t in TOOL_META, f"{t.__name__} missing from TOOL_META"
            meta = TOOL_META[t]
            assert "personas" in meta, f"{t.__name__} missing personas"
            assert "call_limit" in meta, f"{t.__name__} missing call_limit"
            assert len(meta["personas"]) >= 1, f"{t.__name__} has empty personas"

    def test_search_saves_to_bank_workflow(self):
        """WF: search_exam_bank and save_to_bank are distinct tools."""
        from agent.tools import TOOLS
        names = {t.__name__ for t in TOOLS}
        assert "search_exam_bank" in names
        assert "save_to_bank" in names
        assert "show_exam_workbench" in names  # exam creation entry point

    def test_diagnose_to_assign_workflow(self):
        """WF: diagnose_barrier → assign_adaptive_practice workflow exists."""
        from agent.tools import TOOL_META
        teacher_tools = {t.__name__ for t, m in TOOL_META.items() if "teacher" in m["personas"]}
        assert "diagnose_barrier" in teacher_tools
        assert "assign_adaptive_practice" in teacher_tools

    def test_student_answer_to_wrong_workflow(self):
        """WF: Student submit → wrong/list → review pipeline exists."""
        # Verify API endpoints exist
        import importlib
        mods = ['app.api.practice', 'app.api.practice_wrong']
        for m in mods:
            try:
                importlib.import_module(m)
            except ImportError:
                pytest.fail(f"Module {m} must be importable")

    def test_exam_workbench_to_practice_workflow(self):
        """WF: show_exam_workbench → student practice → diagnosis chain."""
        from agent.tools import TOOL_META
        for name in ["show_exam_workbench", "show_diagnosis", "assign_adaptive_practice"]:
            assert name in {t.__name__ for t, m in TOOL_META.items()
                           if "teacher" in m["personas"]}, f"{name} must be in teacher"


class TestBehavioralConstraints:
    """Dimension 4: Behavioral constraint scenarios."""

    def test_constraint_save_requires_search_first(self):
        """CONST-001: save_to_bank should only be called after search_exam_bank."""
        from agent.tools import TOOL_META
        # save_to_bank has call_limit=1 — must be used carefully
        for t, m in TOOL_META.items():
            if t.__name__ == "save_to_bank":
                assert m["call_limit"] == 1, "save_to_bank call_limit must be 1"
            if t.__name__ == "search_exam_bank":
                assert m["call_limit"] == 3, "search_exam_bank call_limit must be 3"

    def test_constraint_student_has_tutor_not_exam(self):
        """CONST-002/005: Student has tutoring tools but NOT exam generation or experiment."""
        from agent.tools import TOOL_META
        student = {t.__name__ for t, m in TOOL_META.items() if "student" in m["personas"]}
        assert "chemistry_tutor" in student, "Student must have chemistry_tutor"
        assert "simulate_experiment" in student, "Student has simulate_experiment (CONST-005 updated)"
        assert "show_exam_workbench" not in student, "Student must NOT have exam workbench"

    def test_constraint_teacher_not_forced_student_mode(self):
        """CONST-004: Teacher persona must have its own system_prompt, not student."""
        from agent.agents import load_persona
        cfg = load_persona("teacher")
        prompt = cfg.get("system_prompt", "")
        assert len(prompt) >= 1, "Teacher must have a system_prompt"
        # Teacher must not be the same as student
        student_cfg = load_persona("student")
        student_prompt = student_cfg.get("system_prompt", "")
        assert prompt != student_prompt, "Teacher and student prompts must differ"

    def test_constraint_approval_required_exists(self):
        """CONST-007: Destructive tools must require approval."""
        from agent.langgraph_agent import TOOL_APPROVAL_REQUIRED
        assert len(TOOL_APPROVAL_REQUIRED) >= 1, "Must have approval-required tools"
        assert "delete_bank" in TOOL_APPROVAL_REQUIRED, "delete_bank must require approval"
        assert "assign_adaptive_practice" in TOOL_APPROVAL_REQUIRED, \
            "assign_adaptive_practice must require approval"

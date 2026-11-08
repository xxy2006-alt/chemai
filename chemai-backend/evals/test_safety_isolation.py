"""Safety Layer Evals — Persona isolation and role-based access control.

Maps to: 评测文档/evals/regression/cross_role/role_scenarios.yaml (ROLE-001..006)
CI gate: 100% (all assertions are deterministic from TOOL_META)
"""
import pytest
from agent.tools import TOOL_META


class TestPersonaIsolation:
    """Verify each persona's tool set has correct boundaries."""

    def test_student_cannot_generate_questions(self):
        """ROLE-001: Student must not have exam generation tools."""
        student = {t.__name__ for t, m in TOOL_META.items() if "student" in m["personas"]}
        forbidden = {"generate_questions", "save_question", "show_exam_workbench",
                     "save_to_bank", "delete_bank", "assign_adaptive_practice"}
        overlap = student & forbidden
        assert not overlap, f"Student has forbidden tools: {overlap}"

    def test_student_cannot_access_class_data(self):
        """ROLE-002: Student must not access class-level reports."""
        student = {t.__name__ for t, m in TOOL_META.items() if "student" in m["personas"]}
        forbidden = {"weekly_report", "diagnose_barrier", "show_diagnosis", "show_students"}
        overlap = student & forbidden
        assert not overlap, f"Student has class-data tools: {overlap}"

    def test_student_has_tutoring_tools(self):
        """ROLE-003/004: Student should have practice and review capabilities."""
        student = {t.__name__ for t, m in TOOL_META.items() if "student" in m["personas"]}
        expected = {"chemistry_tutor", "simulate_experiment", "web_search",
                    "ionic_equation_tutor", "stoichiometry_tutor", "redox_tutor",
                    "equilibrium_tutor", "periodic_law_tutor", "organic_tutor"}
        missing = expected - student
        assert not missing, f"Student missing tutoring tools: {missing}"

    def test_parent_cannot_generate_or_diagnose(self):
        """ROLE-006: Parent must not have exam generation or class management."""
        parent = {t.__name__ for t, m in TOOL_META.items() if "parent" in m["personas"]}
        # diagnose_barrier is allowed — parents need it for their child
        forbidden = {"generate_questions", "show_diagnosis",
                     "show_students", "assign_adaptive_practice", "delete_bank",
                     "show_exam_workbench", "save_to_bank"}
        overlap = parent & forbidden
        assert not overlap, f"Parent has forbidden tools: {overlap}"

    def test_parent_has_report_tools(self):
        """Parent should have weekly_report and memory access."""
        parent = {t.__name__ for t, m in TOOL_META.items() if "parent" in m["personas"]}
        expected = {"weekly_report"}
        missing = expected - parent
        assert not missing, f"Parent missing report tools: {missing}"

    def test_teacher_has_full_diagnosis(self):
        """ROLE-005: Teacher should have full diagnosis and exam management."""
        teacher = {t.__name__ for t, m in TOOL_META.items() if "teacher" in m["personas"]}
        expected = {"diagnose_barrier", "show_diagnosis", "show_students",
                    "assign_adaptive_practice", "show_exam_workbench", "save_to_bank"}
        missing = expected - teacher
        assert not missing, f"Teacher missing management tools: {missing}"

    def test_no_cross_persona_leakage(self):
        """Every tool's persona list must be valid."""
        valid = {"student", "tutor", "teacher", "parent"}
        for fn, meta in TOOL_META.items():
            for p in meta["personas"]:
                assert p in valid, f"{fn.__name__} has invalid persona: {p}"

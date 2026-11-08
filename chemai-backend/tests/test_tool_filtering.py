"""Test persona-based tool filtering works correctly.

Verifies that TOOL_META auto-registration produces the right tool sets
for each persona, and that the YAML whitelist filter (intersection) works.
"""
import pytest


class TestTOOL_META:
    """Verify all 20 tools are registered with correct personas."""

    def test_all_tools_have_meta(self):
        from agent.tools import TOOLS, TOOL_META
        assert set(TOOLS) == set(TOOL_META.keys()), "Every tool must be in TOOL_META"

    def test_student_tools_exclude_teacher(self):
        """Student must NOT have show_exam_workbench, balance_equation, assign_adaptive_practice."""
        from agent.tools import TOOL_META
        student_names = {t.__name__ for t, m in TOOL_META.items() if "student" in m["personas"]}
        forbidden = {"show_exam_workbench", "balance_equation", "assign_adaptive_practice",
                     "show_diagnosis", "show_students", "delete_bank"}
        assert student_names.isdisjoint(forbidden), f"Student has teacher tools: {student_names & forbidden}"

    def test_student_has_tutors(self):
        """Student must have all 4 tutoring tools."""
        from agent.tools import TOOL_META
        student_names = {t.__name__ for t, m in TOOL_META.items() if "student" in m["personas"]}
        expected = {"ionic_equation_tutor", "stoichiometry_tutor", "redox_tutor", "equilibrium_tutor",
                    "chemistry_tutor", "simulate_experiment", "web_search"}
        assert expected.issubset(student_names), f"Missing: {expected - student_names}"

    def test_teacher_has_diagnosis(self):
        """Teacher must have all diagnosis tools."""
        from agent.tools import TOOL_META
        teacher_names = {t.__name__ for t, m in TOOL_META.items() if "teacher" in m["personas"]}
        expected = {"diagnose_barrier", "show_diagnosis", "show_students", "assign_adaptive_practice",
                    "query_ocr_progress", "grade_answer_sheets", "save_grading_results"}
        assert expected.issubset(teacher_names), f"Missing: {expected - teacher_names}"

    def test_call_limits_exist(self):
        """Every tool must have a positive call_limit."""
        from agent.tools import TOOL_META
        for fn, meta in TOOL_META.items():
            assert meta["call_limit"] >= 1, f"{fn.__name__} has invalid call_limit: {meta['call_limit']}"

    def test_personas_are_valid(self):
        """All persona values must be known."""
        from agent.tools import TOOL_META
        valid_personas = {"student", "tutor", "teacher", "parent"}
        for fn, meta in TOOL_META.items():
            for p in meta["personas"]:
                assert p in valid_personas, f"{fn.__name__} has unknown persona: {p}"


class TestYAMLFiltering:
    """Verify persona YAMLs produce correct tool sets when intersected."""

    def test_student_yaml_skills_all_in_auto(self):
        from agent.agents import load_persona
        from agent.tools import TOOL_META
        cfg = load_persona("student")
        yaml_skills = set(cfg.get("available_skills", []))
        auto_student = {t.__name__ for t, m in TOOL_META.items() if "student" in m["personas"]}
        # YAML should be a subset of auto (no zombie skill names)
        extra = yaml_skills - auto_student
        assert not extra, f"YAML skills not in TOOL_META: {extra}"

    def test_teacher_yaml_skills_all_in_auto(self):
        from agent.agents import load_persona
        from agent.tools import TOOL_META
        cfg = load_persona("teacher")
        yaml_skills = set(cfg.get("available_skills", []))
        auto_teacher = {t.__name__ for t, m in TOOL_META.items() if "teacher" in m["personas"]}
        extra = yaml_skills - auto_teacher
        assert not extra, f"YAML skills not in TOOL_META: {extra}"


class TestYAMLWhitelistDoesNotDropTools:
    """反方向不变量：persona 白名单不能悄悄吃掉已注册的工具。

    v2 agent 的工具集是 `TOOL_META(persona) ∩ YAML.available_skills`，所以
    「注册了但没写进 YAML」的工具在生产 agent 里不可达（老师永远叫不出确认成绩）。
    """

    @pytest.mark.parametrize("persona", ["student", "teacher", "tutor", "parent"])
    def test_every_auto_tool_is_whitelisted(self, persona):
        from agent.agents import load_persona
        from agent.tools import TOOL_META
        cfg = load_persona(persona)
        yaml_skills = set(cfg.get("available_skills") or [])
        if not yaml_skills:
            pytest.skip(f"{persona} 无白名单（不做交集过滤）")
        auto = {t.__name__ for t, m in TOOL_META.items() if persona in m.get("personas", [])}
        unreachable = sorted(auto - yaml_skills)
        assert not unreachable, f"{persona} 的工具被白名单过滤掉了: {unreachable}"

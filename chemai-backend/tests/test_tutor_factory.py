"""Test the tutoring tool factory produces correct outputs.

All 4 tutoring tools (ionic/stoichiometry/redox/equilibrium) share
the _make_tutor_tool factory. Tests verify they all follow the same contract.
"""
import json, pytest, asyncio


TUTORS = [
    ("ionic_equation_tutor", "NaOH + HCl", "可拆"),
    ("stoichiometry_tutor", "10.6g Na2CO3", "已知"),
    ("redox_tutor", "Cu + HNO3", "化合"),
    ("equilibrium_tutor", "2SO2 + O2", "平衡"),
]


class TestTutorFactory:
    """Test all 4 factory-generated tutoring tools."""

    @pytest.mark.parametrize("name,equation,keyword", TUTORS)
    def test_returns_json(self, name, equation, keyword):
        """Every tutoring tool returns valid JSON."""
        from agent.tools import TOOLS
        tool = {t.__name__: t for t in TOOLS}[name]

        result = asyncio.run(tool(equation=equation))
        data = json.loads(result)
        assert isinstance(data, dict)
        assert "guidance" in data

    @pytest.mark.parametrize("name,equation,keyword", TUTORS)
    def test_step_one_has_guidance(self, name, equation, keyword):
        """Step 1 response contains instruction guidance with the expected keyword."""
        from agent.tools import TOOLS
        tool = {t.__name__: t for t in TOOLS}[name]

        result = asyncio.run(tool(equation=equation))
        data = json.loads(result)
        assert keyword in data.get("guidance", ""), f"Expected '{keyword}' in guidance"

    @pytest.mark.parametrize("name,equation,keyword", TUTORS)
    def test_empty_input_shows_intro(self, name, equation, keyword):
        """Calling with no arguments returns title + guidance."""
        from agent.tools import TOOLS
        tool = {t.__name__: t for t in TOOLS}[name]

        result = asyncio.run(tool())
        data = json.loads(result)
        assert "title" in data
        assert "guidance" in data
        assert len(data["guidance"]) > 20

    @pytest.mark.parametrize("name,equation,keyword", TUTORS)
    def test_student_followup_returns_feedback(self, name, equation, keyword):
        """Student responding to step 1 triggers feedback + next guidance."""
        from agent.tools import TOOLS
        tool = {t.__name__: t for t in TOOLS}[name]

        result = asyncio.run(tool(equation=equation, student_input="我不知道"))
        data = json.loads(result)
        assert "feedback" in data
        assert "guidance" in data

    def test_all_four_not_none(self):
        """All 4 tutoring tools exist as functions."""
        from agent.tools import TOOLS
        names = {t.__name__ for t in TOOLS}
        for name, _, _ in TUTORS:
            assert name in names, f"{name} not in TOOLS"

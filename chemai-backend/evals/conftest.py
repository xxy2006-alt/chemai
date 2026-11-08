"""
ChemAI Eval 共享工具 — fixtures, validators, assertions
"""
import json
import sys
import os
import time
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ═══════════════════════════════════════════════════════════════════════
# Test case definitions
# ═══════════════════════════════════════════════════════════════════════

EVAL_CASES = {
    # ── balance_equation ──
    "balance_fe_o2": {
        "input": "帮我配平 Fe + O2 = Fe2O3",
        "expected_tool": "balance_equation",
        "persona": "tutor",
        "validate": lambda r: "overall_status" in r,
    },
    "balance_complex": {
        "input": "配平 KMnO4 + HCl = KCl + MnCl2 + Cl2 + H2O",
        "expected_tool": "balance_equation",
        "persona": "tutor",
        "validate": lambda r: "overall_status" in r,
    },
    "balance_already_balanced": {
        "input": "检查 2H2 + O2 = 2H2O 是否配平",
        "expected_tool": "balance_equation",
        "persona": "tutor",
        "validate": lambda r: r.get("overall_status") == "passed",
    },

    # ── search_exam_bank ──
    "search_organic": {
        "input": "搜索3条关于有机化学的真题",
        "expected_tool": "search_exam_bank",
        "persona": "tutor",
        "validate": lambda r: isinstance(r.get("questions"), list),
    },
    "search_by_year": {
        "input": "找2023年的高考化学真题",
        "expected_tool": "search_exam_bank",
        "persona": "teacher",
        "validate": lambda r: isinstance(r.get("questions"), list),
    },

    # ── generate_questions ──
    "gen_questions_salt_hydrolysis": {
        "input": "出3道盐类水解的选择题",
        "expected_tool": "generate_questions",
        "persona": "tutor",
        "validate": lambda r: isinstance(r.get("questions"), list) and len(r.get("questions", [])) > 0,
    },
    "gen_questions_redox": {
        "input": "生成5道氧化还原反应的选择题",
        "expected_tool": "generate_questions",
        "persona": "teacher",
        "validate": lambda r: isinstance(r.get("questions"), list),
    },

    # ── chemistry_tutor ──
    "tutor_concept": {
        "input": "什么是勒夏特列原理？",
        "expected_tool": "chemistry_tutor",
        "persona": "tutor",
        "validate": lambda r: "answer" in r,
    },

    # ── simulate_experiment ──
    "experiment_neutralization": {
        "input": "模拟酸碱中和滴定实验",
        "expected_tool": "simulate_experiment",
        "persona": "tutor",
        "validate": lambda r: "experiment_name" in r or "steps" in r,
    },

    # ── chat (no tool) ──
    "chat_greeting": {
        "input": "你好",
        "expected_tool": None,
        "persona": "tutor",
        "validate": lambda r: True,  # any text reply is valid
    },
    "chat_weather": {
        "input": "今天天气怎么样",
        "expected_tool": None,
        "persona": "tutor",
        "validate": lambda r: True,
    },

    # ── web_search ──
    "web_search_gk": {
        "input": "搜索2025年高考化学大纲变化",
        "expected_tool": "web_search",
        "persona": "tutor",
        "validate": lambda r: "result" in r or "query" in r,
    },

    # ── diagnose_barrier ──
    "diagnose_student": {
        "input": "诊断学生S001的学习障碍",
        "expected_tool": "diagnose_barrier",
        "persona": "teacher",
        "validate": lambda r: True,
    },

    # ── weekly_report ──
    "weekly_report_student": {
        "input": "生成S001的本周学习报告",
        "expected_tool": "weekly_report",
        "persona": "parent",
        "validate": lambda r: True,
    },
}


# ═══════════════════════════════════════════════════════════════════════
# Validators
# ═══════════════════════════════════════════════════════════════════════

def parse_tool_result(result_output):
    """Parse tool result (may be JSON string or dict)."""
    if isinstance(result_output, str):
        try:
            return json.loads(result_output)
        except (json.JSONDecodeError, TypeError):
            return {"raw": result_output}
    return result_output


def extract_tools_called(agent_result):
    """Extract tool names called during an agent run."""
    tools = []
    for msg in agent_result.all_messages():
        for part in getattr(msg, 'parts', []):
            name = getattr(part, 'tool_name', None)
            if name:
                tools.append(name)
    return tools


# ═══════════════════════════════════════════════════════════════════════
# Report helpers
# ═══════════════════════════════════════════════════════════════════════

class EvalReport:
    def __init__(self):
        self.results = []
        self.start_time = time.time()

    def add(self, name, passed, details=""):
        self.results.append({
            "name": name,
            "passed": passed,
            "details": str(details)[:500],
        })

    def summary(self):
        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        failed = total - passed
        elapsed = time.time() - self.start_time
        lines = [
            f"\n{'='*60}",
            f"  ChemAI Eval Report",
            f"  {'='*60}",
            f"  Total: {total}  |  Passed: {passed}  |  Failed: {failed}  |  Time: {elapsed:.1f}s",
            f"  {'='*60}",
        ]
        for r in self.results:
            status = "PASS" if r["passed"] else "FAIL"
            lines.append(f"  [{status}] {r['name']}")
            if r["details"] and not r["passed"]:
                lines.append(f"         {r['details']}")
        return "\n".join(lines)


def discover_evals():
    """Discover all eval files in this directory."""
    import glob as _glob
    evals_dir = os.path.dirname(__file__)
    pattern = os.path.join(evals_dir, "test_*.py")
    return sorted(_glob.glob(pattern))

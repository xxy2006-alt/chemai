"""
Unit evals — pure-logic tools (no API keys, no DB)
Tests: balance_equation, exam_bank, chemical_balance
"""
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from evals.conftest import EvalReport, parse_tool_result


def test_chemical_balance_engine():
    """Test the core chemical_balance audit engine directly."""
    from app.services.chemical_balance import audit_chemical_equation

    cases = [
        # (equation, expected_status)
        # Note: chemical_balance uses "blocked" for unbalanced equations, not "warning"
        ("Fe + O2 = Fe2O3", "blocked"),       # unbalanced
        ("2H2 + O2 = 2H2O", "passed"),        # balanced
        ("Na + Cl2 = NaCl", "blocked"),        # unbalanced
        ("2Na + Cl2 = 2NaCl", "passed"),       # balanced
        ("KMnO4 + HCl = KCl + MnCl2 + Cl2 + H2O", "blocked"),  # unbalanced
        ("CH4 + 2O2 = CO2 + 2H2O", "passed"), # balanced
        ("not an equation", "blocked"),        # invalid (parser returns blocked)
        ("H2O = H2 + O2", "blocked"),          # unbalanced
        ("2H2O = 2H2 + O2", "passed"),         # balanced
    ]

    results = []
    for eq, expected in cases:
        r = audit_chemical_equation(eq)
        status = r.get("overall_status", "unknown")
        passed = status == expected
        results.append({
            "equation": eq,
            "expected": expected,
            "actual": status,
            "passed": passed,
        })
        if not passed:
            results[-1]["details"] = json.dumps(r, ensure_ascii=False)[:200]

    return results


def test_exam_bank_search():
    """Test exam bank search (uses local JSON files, no API)."""
    from app.services.exam_bank import exam_bank_service

    tests = [
        ("search by keyword", lambda: exam_bank_service.search_questions(knowledge_point="有机", limit=5)),
        ("search by year", lambda: exam_bank_service.search_questions(year=2023, limit=5)),
        ("search by difficulty", lambda: exam_bank_service.search_questions(difficulty="medium", limit=5)),
        ("search all", lambda: exam_bank_service.search_questions(limit=3)),
    ]

    results = []
    for name, fn in tests:
        try:
            r = fn()
            passed = isinstance(r, list)
            results.append({
                "name": name,
                "count": len(r) if isinstance(r, list) else 0,
                "passed": passed,
            })
        except Exception as e:
            results.append({"name": name, "passed": False, "details": str(e)[:200]})

    return results


def test_balance_equation_tool():
    """Test balance_equation tool function directly."""
    import asyncio
    from agent.tools import balance_equation

    async def run():
        results = []
        test_cases = [
            ("Fe + O2 = Fe2O3", False),   # unbalanced → warning
            ("2H2 + O2 = 2H2O", True),    # balanced → passed
            ("Na + Cl2 = NaCl", False),   # unbalanced
        ]
        for eq, should_be_balanced in test_cases:
            raw = await balance_equation(equation=eq)
            data = parse_tool_result(raw)
            status = data.get("overall_status", "unknown")
            if should_be_balanced:
                passed = status == "passed"
            else:
                passed = status in ("warning", "blocked")
            results.append({
                "equation": eq,
                "status": status,
                "passed": passed,
            })
        return results

    return asyncio.run(run())


def run():
    report = EvalReport()

    print("=== Unit Eval: chemical_balance engine ===")
    for r in test_chemical_balance_engine():
        report.add(f"balance_engine: {r['equation']}", r["passed"],
                   r.get("details", f"expected={r['expected']} actual={r['actual']}"))

    print("=== Unit Eval: exam_bank search ===")
    for r in test_exam_bank_search():
        report.add(f"exam_bank: {r['name']}", r["passed"],
                   f"count={r.get('count', 'N/A')}" if not r["passed"] else "")

    print("=== Unit Eval: balance_equation tool ===")
    for r in test_balance_equation_tool():
        report.add(f"balance_tool: {r['equation'][:30]}", r["passed"],
                   f"status={r['status']}")

    print(report.summary())
    return report


if __name__ == "__main__":
    run()

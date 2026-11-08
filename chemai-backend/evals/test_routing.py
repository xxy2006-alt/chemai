"""Golden routing test runner.

Phase 2: Tests Gateway._keyword_fallback (deterministic keyword → tool mapping).
Phase 3: extends to test full routing (agent + tool) after Coordinator merge.

Usage:
    python evals/test_routing.py              # all tests
    python evals/test_routing.py --phase2     # keyword routing only
    python evals/test_routing.py --phase3     # full routing (after Phase 3)
"""
import os, sys, yaml, json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_cases(path: str = None) -> list[dict]:
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "golden_routing.yaml")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("cases", [])


def run_keyword_routing(cases: list[dict] = None) -> tuple[int, int, list[str]]:
    """Phase 2: run Gateway._keyword_fallback cases, return (passed, failed, failures).

    返回元组给脚本 main() 打印报告；非 test_ 前缀避免 pytest 收集。
    默认参数让 pytest 不再把 cases 当 fixture；main() 仍可显式传入。
    """
    from agent.gateway import IntentClassifier

    if cases is None:
        cases = load_cases()

    classifier = IntentClassifier(provider=None)

    passed = 0
    failed = 0
    failures = []

    for case in cases:
        cid = case["id"]
        inp = case["input"]
        expect_tools = case.get("expect_tools", [])
        expect_agent = case.get("expect_agent")

        result = classifier._keyword_fallback(inp)

        # Validate tools
        result_tools = result.tools or []
        if expect_tools:
            missing = [t for t in expect_tools if t not in result_tools]
            if missing:
                failed += 1
                failures.append(
                    f"  FAIL [{cid}] \"{inp}\"\n"
                    f"        expected tools: {expect_tools}\n"
                    f"        got tools: {result_tools}\n"
                    f"        missing: {missing}"
                )
                continue

        # Check navigate vs chat
        if expect_agent is None and result.type == "navigate":
            # navigate cases — just verify type
            passed += 1
            continue

        if expect_agent is None and not expect_tools:
            # respond-directly cases (greeting)
            passed += 1
            continue

        passed += 1

    return passed, failed, failures


def test_keyword_routing():
    """Phase 2: pytest entry that asserts no routing failures (real assertion, not a returned tuple)."""
    passed, failed, failures = run_keyword_routing()
    assert failed == 0, (
        f"{failed}/{passed + failed} routing cases FAILED:\n" + "\n".join(failures)
    )


def print_report(passed: int, failed: int, failures: list[str], phase: str):
    total = passed + failed
    print(f"\n{'='*60}")
    print(f"  Golden Routing Test — {phase}")
    print(f"  {passed}/{total} passed", end="")
    if failed:
        print(f", {failed} FAILED")
    else:
        print(" — ALL PASSED")
    print(f"{'='*60}")

    if failures:
        print("\nFailures:")
        for f in failures:
            print(f)

    return failed == 0


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Golden routing test runner")
    parser.add_argument("--phase2", action="store_true", default=True,
                        help="Run Phase 2 keyword routing tests (default)")
    parser.add_argument("--phase3", action="store_true",
                        help="Run Phase 3 full routing tests (requires LLM)")
    parser.add_argument("--all", action="store_true",
                        help="Run all phases")
    args = parser.parse_args()

    cases = load_cases()
    all_pass = True

    if args.phase2 or args.all:
        passed, failed, failures = run_keyword_routing(cases)
        all_pass = print_report(passed, failed, failures, "Phase 2: Keyword Routing") and all_pass

    if args.phase3:
        # Placeholder for Phase 3 integration tests (requires LLM mocking)
        print("\n  Phase 3: Full routing tests — not yet implemented")
        print("  Run after Gateway+Coordinator merge is complete.")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())

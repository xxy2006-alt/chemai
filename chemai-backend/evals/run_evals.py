"""
ChemAI Eval Runner — fast/slow dual-layer unified entry.

Spec: docs/specs/evals/spec-01-eval-infra.md

Usage:
    python evals/run_evals.py --fast [--save] [--only NAME]
        fast layer (L0+L1+L4+L5, zero LLM, seconds) — CI gate, exit 1 on failure
    python evals/run_evals.py --slow [--only NAME]
        slow layer (L2+L3+L6, costs tokens) — severe errors veto release;
        scores go to the trend archive only. Slow runs are always archived.
    --unit / --classifier   (deprecated) see --fast --only / --slow --only
"""
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from evals.runner import run_group, format_report, REPORTS_DIR  # noqa: E402
from evals.layers import LAYERS  # noqa: E402


def main():
    # Windows 管道/控制台默认 GBK，统一按 UTF-8 输出避免报告乱码
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass

    parser = argparse.ArgumentParser(description="ChemAI Eval Runner (fast/slow dual layer)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--fast", action="store_true", help="fast layer gate: zero LLM, CI (default)")
    group.add_argument("--slow", action="store_true", help="slow layer: judge/safety/e2e, costs tokens")
    parser.add_argument("--save", action="store_true", help="archive report (slow always archives)")
    parser.add_argument("--only", metavar="NAME", help="run a single registry entry")
    parser.add_argument("--unit", action="store_true", help="(deprecated) alias for --fast --only unit_tools")
    parser.add_argument("--classifier", action="store_true", help="(deprecated) alias for --slow --only classifier")
    args = parser.parse_args()

    group_name = "slow" if args.slow else "fast"
    only = args.only
    if args.unit:
        print("[deprecated] --unit 已并入层注册表，请改用: --fast --only unit_tools")
        group_name, only = "fast", "unit_tools"
    if args.classifier:
        print("[deprecated] --classifier 已并入层注册表（需 API），请改用: --slow --only classifier")
        group_name, only = "slow", "classifier"

    save = args.save or group_name == "slow"  # 慢跑必须归档以积累趋势
    from evals.tool_coverage import coverage_warnings  # 快跑层：覆盖清单审计（Spec 02）
    extra_warnings = coverage_warnings() if group_name == "fast" else []
    try:
        report, exit_code = run_group(
            LAYERS, group=group_name, only=only,
            report_dir=REPORTS_DIR if save else None,
            extra_warnings=extra_warnings,
        )
    except ValueError as exc:
        print(f"error: {exc}")
        sys.exit(2)

    print(format_report(report))
    if save:
        print(f"\nReport archived to: {REPORTS_DIR} (index.json 维护趋势序列)")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

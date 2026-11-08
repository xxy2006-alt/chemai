"""
ChemAI Eval Runner Core — fast/slow dual-layer gate engine.

Spec:   docs/specs/evals/spec-01-eval-infra.md (seam 1: runner CLI)
Design: docs/evals/eval-system-design.md §4/§5

Pure logic, zero API: registry-driven, testable with fake registries
(see evals/test_runner.py).

Gate rules:
  - fast layer: any non-expected failure -> blocked (exit 1)
  - slow layer: only severity "severe" vetoes (exit 1); fail/warn -> report only
  - expected_fail: failed + expected -> "pending" (exempt, not a failure);
                   passed + expected -> warning "remove expected_fail marker"
Case status: pass / pass_expected / pending / fail / severe
"""
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = Path(__file__).resolve().parent / "reports"

# status -> summary bucket
_STATUS_BUCKET = {
    "pass": "passed",
    "pending": "pending",
    "fail": "failed",
    "severe": "severe",
    "pass_expected": "warnings",
}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _classify(case_name, passed, is_expected, severity="fail"):
    """Map (passed, expected_fail) to (status, severity, warning)."""
    if passed and is_expected:
        return "pass_expected", "warn", f"REMOVE expected_fail marker: {case_name} now passes"
    if passed:
        return "pass", "pass", ""
    if is_expected:
        return "pending", "pass", ""
    return ("severe" if severity == "severe" else "fail"), severity, ""


def _run_entry(entry):
    """Run one registry entry -> list of case dicts (name, passed, severity, details)."""
    kind = entry.get("kind", "function")
    try:
        if kind == "callable":  # test-only
            return entry["fn"]()
        if kind == "function":
            import importlib
            mod = importlib.import_module(entry["module"])
            result = getattr(mod, entry["func"])()
            results = getattr(result, "results", result)
            return [
                {
                    "name": r.get("name", f"{entry['name']}[{i}]"),
                    "passed": bool(r.get("passed")),
                    "severity": r.get("severity", "fail"),
                    "details": r.get("details", ""),
                }
                for i, r in enumerate(results)
            ]
        module_file = entry["module"].replace(".", "/") + ".py"
        if kind == "pytest":
            cmd = [sys.executable, "-m", "pytest", module_file, "-q", "--no-header"]
        elif kind == "script":
            cmd = [sys.executable, module_file, *entry.get("args", [])]
        else:
            raise ValueError(f"unknown entry kind: {kind}")
        proc = subprocess.run(
            cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True,
            timeout=entry.get("timeout", 300),
        )
    except subprocess.TimeoutExpired:
        severity = entry.get("failure_severity", "fail")
        return [{"name": entry["name"], "passed": False, "severity": severity, "details": "timeout"}]
    except Exception as exc:  # entry crashed -> a failed case, never a crashed runner
        severity = entry.get("failure_severity", "fail")
        return [{"name": entry["name"], "passed": False, "severity": severity,
                 "details": f"{type(exc).__name__}: {exc}"}]
    passed = proc.returncode == 0
    # failure_severity: L6 端到端失败 = severe → 慢跑层一票否决（Spec 01/06）
    severity = "fail" if passed else entry.get("failure_severity", "fail")
    details = (proc.stdout or "")[-800:] if not passed else ""
    return [{"name": entry["name"], "passed": passed, "severity": severity, "details": details}]


def run_group(registry, group="fast", only=None, report_dir=None, extra_warnings=None):
    """Run one group of the registry. Returns (report, exit_code)."""
    started = time.time()
    layers_out = {}
    summary = {"total": 0, "passed": 0, "failed": 0, "severe": 0, "pending": 0, "warnings": 0}
    warnings = list(extra_warnings or [])

    for layer_id, layer_cfg in registry.items():
        entries = [
            e for e in layer_cfg.get("entries", [])
            if e.get("group", layer_cfg.get("group", "fast")) == group
        ]
        if only:
            entries = [e for e in entries if e["name"] == only]
        layer_out = {
            "id": layer_id,
            "name": layer_cfg.get("name", layer_id),
            "unimplemented": not layer_cfg.get("entries"),
            "entries": [],
        }
        if not layer_cfg.get("entries"):
            layer_out["note"] = layer_cfg.get("status", "未实现")
        for entry in entries:
            cases = _run_entry(entry)
            entry_out = {"name": entry["name"], "cases": []}
            expected_fail = entry.get("expected_fail")
            for case in cases:
                is_expected = (expected_fail is True) or (
                    isinstance(expected_fail, list) and case["name"] in expected_fail
                )
                status, severity, warning = _classify(
                    case["name"], case["passed"], is_expected, case.get("severity", "fail")
                )
                entry_out["cases"].append({
                    "name": case["name"],
                    "status": status,
                    "severity": severity,
                    "details": case.get("details", ""),
                })
                summary["total"] += 1
                summary[_STATUS_BUCKET[status]] += 1
                if warning:
                    warnings.append(warning)
            layer_out["entries"].append(entry_out)
        layers_out[layer_id] = layer_out

    if only and summary["total"] == 0:
        raise ValueError(f"--only: no entry named '{only}' in {group} layer")

    blocked_reasons = []
    if group == "fast":
        failing = [
            c for layer in layers_out.values() for e in layer["entries"] for c in e["cases"]
            if c["status"] in ("fail", "severe")
        ]
        if failing:
            blocked_reasons.append(f"fast layer: {len(failing)} deterministic failure(s) — gate blocked")
    else:
        severe = [
            c for layer in layers_out.values() for e in layer["entries"] for c in e["cases"]
            if c["status"] == "severe"
        ]
        if severe:
            blocked_reasons.append(f"slow layer: {len(severe)} severe error(s) — release vetoed")

    verdict = "blocked" if blocked_reasons else "pass"
    report = {
        "timestamp": _now(),
        "group": group,
        "layers": layers_out,
        "summary": summary,
        "warnings": warnings,
        "cost": {"judge_calls": 0, "estimated_yuan": 0},  # 占位，Spec 04 填充
        "gate": {"verdict": verdict, "reasons": blocked_reasons},
        "elapsed_seconds": round(time.time() - started, 1),
    }
    if report_dir is not None:
        save_report(report, report_dir)
    return report, (1 if verdict == "blocked" else 0)


def save_report(report, report_dir=None):
    """Archive one run and append it to the trend index. Returns report file path."""
    report_dir = Path(report_dir) if report_dir is not None else REPORTS_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    file_path = report_dir / f"{stamp}-{report['group']}.json"
    file_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    index = report_dir / "index.json"
    runs = []
    if index.exists():
        try:
            runs = json.loads(index.read_text(encoding="utf-8")).get("runs", [])
        except (json.JSONDecodeError, OSError):
            runs = []
    runs.append({
        "timestamp": report["timestamp"],
        "file": file_path.name,
        "group": report["group"],
        "verdict": report["gate"]["verdict"],
        "passed": report["summary"]["passed"],
        "failed": report["summary"]["failed"] + report["summary"]["severe"],
        "pending": report["summary"]["pending"],
    })
    index.write_text(json.dumps({"runs": runs}, ensure_ascii=False, indent=2), encoding="utf-8")
    return file_path


_ICON = {"pass": "PASS", "pending": "PEND", "fail": "FAIL",
         "severe": "SEV ", "pass_expected": "WARN"}


def format_report(report):
    lines = [
        "=" * 64,
        f"  ChemAI Eval Report — {report['group']} layer  ({report['timestamp']})",
        "=" * 64,
    ]
    for layer_id, layer in report["layers"].items():
        if layer["unimplemented"]:
            lines.append(f"  [{layer_id}] {layer['name']}: 未实现（{layer.get('note', '')}）")
            continue
        for entry in layer["entries"]:
            for c in entry["cases"]:
                icon = _ICON[c["status"]]
                lines.append(f"  [{icon}] [{layer_id}] {entry['name']} / {c['name']}")
                if c["details"] and c["status"] in ("fail", "severe"):
                    lines.append(f"         {c['details'][:200]}")
    s = report["summary"]
    lines.append("-" * 64)
    lines.append(
        f"  Total {s['total']} | Pass {s['passed']} | Fail {s['failed']} | Severe {s['severe']}"
        f" | Pending {s['pending']} | Warn {s['warnings']} | {report['elapsed_seconds']}s"
    )
    for w in report["warnings"]:
        lines.append(f"  ! {w}")
    g = report["gate"]
    lines.append(
        f"  GATE: {g['verdict'].upper()}" + (f" — {'; '.join(g['reasons'])}" if g["reasons"] else "")
    )
    lines.append("=" * 64)
    return "\n".join(lines)

"""
Runner meta-tests — verify the fast/slow gate engine itself (Spec 01, seam 1).

Fake registries drive verdict decisions; zero API, zero LLM. These tests pin
the EXTERNAL behavior of the eval system: exit codes, gate verdicts, report
structure, expected_fail semantics, and trend archiving.
"""
import json
import sys

import pytest

from evals.runner import run_group, save_report


# ── fake registry helpers ────────────────────────────────────────────────

def _reg(*entries, group="fast"):
    return {"L0": {"name": "工具自身正确性", "group": group, "entries": list(entries)}}


def _callable(name, fn, expected_fail=None):
    entry = {"name": name, "kind": "callable", "fn": fn}
    if expected_fail is not None:
        entry["expected_fail"] = expected_fail
    return entry


def _cases(pairs, severity="fail"):
    return [{"name": n, "passed": p, "severity": severity} for n, p in pairs]


def _flatten(report):
    return [c for l in report["layers"].values() for e in l["entries"] for c in e["cases"]]


# ── fast gate ────────────────────────────────────────────────────────────

def test_fast_all_green_passes():
    entry = _callable("ok", lambda: _cases([("c1", True), ("c2", True)]))
    report, code = run_group(_reg(entry), "fast")
    assert code == 0
    assert report["gate"]["verdict"] == "pass"
    assert report["summary"] == {
        "total": 2, "passed": 2, "failed": 0, "severe": 0, "pending": 0, "warnings": 0,
    }


def test_fast_failure_blocks():
    entry = _callable("bad", lambda: _cases([("c1", True), ("c2", False)]))
    report, code = run_group(_reg(entry), "fast")
    assert code == 1
    assert report["gate"]["verdict"] == "blocked"
    assert report["summary"]["failed"] == 1
    assert "deterministic failure" in report["gate"]["reasons"][0]


# ── expected_fail semantics (eval-first) ─────────────────────────────────

def test_expected_fail_failure_is_pending():
    entry = _callable("red", lambda: _cases([("c1", False)]), expected_fail=True)
    report, code = run_group(_reg(entry), "fast")
    assert code == 0, "expected-fail red tests must not block the gate"
    case = _flatten(report)[0]
    assert case["status"] == "pending"
    assert report["summary"]["pending"] == 1
    assert report["summary"]["failed"] == 0


def test_expected_fail_pass_warns_remove():
    entry = _callable("red", lambda: _cases([("c1", True)]), expected_fail=True)
    report, code = run_group(_reg(entry), "fast")
    assert code == 0
    case = _flatten(report)[0]
    assert case["status"] == "pass_expected"
    assert any("REMOVE expected_fail" in w for w in report["warnings"])


def test_expected_fail_name_list_granularity():
    entry = _callable(
        "mixed",
        lambda: _cases([("red_case", False), ("real_case", False)]),
        expected_fail=["red_case"],
    )
    report, code = run_group(_reg(entry), "fast")
    assert code == 1, "non-expected failure must still block"
    statuses = {c["name"]: c["status"] for c in _flatten(report)}
    assert statuses == {"red_case": "pending", "real_case": "fail"}


# ── slow gate ────────────────────────────────────────────────────────────

def test_slow_fail_does_not_block():
    entry = _callable("noisy", lambda: _cases([("c1", False)]))
    report, code = run_group(_reg(entry, group="slow"), "slow")
    assert code == 0, "score noise must not veto a release"
    assert report["gate"]["verdict"] == "pass"
    assert report["summary"]["failed"] == 1


def test_slow_severe_blocks():
    entry = _callable("veto", lambda: _cases([("c1", False)], severity="severe"))
    report, code = run_group(_reg(entry, group="slow"), "slow")
    assert code == 1
    assert report["gate"]["verdict"] == "blocked"
    assert "severe" in report["gate"]["reasons"][0]


def test_entry_failure_severity_escalates(monkeypatch):
    """Spec 06: L6 e2e 失败 = severe（failure_severity 条目级升级）。"""
    import evals.runner as runner_mod

    def fake_run(cmd, **kwargs):
        class P:
            returncode = 1
            stdout = "e2e failed"
        return P()

    monkeypatch.setattr(runner_mod.subprocess, "run", fake_run)
    entry = {"name": "e2e", "kind": "pytest", "module": "fake", "failure_severity": "severe"}
    report, code = run_group(_reg(entry, group="slow"), "slow")
    assert code == 1, "severe e2e failure must veto the slow gate"
    case = _flatten(report)[0]
    assert case["status"] == "severe"


# ── layers / report structure ────────────────────────────────────────────

def test_unimplemented_layer_marked():
    reg = {
        "L0": {"name": "工具", "group": "fast", "entries": []},
        "L4": {"name": "性能预算", "group": "fast", "entries": [], "status": "未实现 — Spec 02"},
    }
    report, code = run_group(reg, "fast")
    assert code == 0
    assert report["layers"]["L4"]["unimplemented"] is True
    assert report["layers"]["L4"]["note"] == "未实现 — Spec 02"
    assert report["summary"]["total"] == 0


def test_report_structure():
    entry = _callable("ok", lambda: _cases([("c1", True)]))
    report, _ = run_group(_reg(entry), "fast")
    assert set(report) >= {"timestamp", "group", "layers", "summary", "warnings", "cost", "gate", "elapsed_seconds"}
    assert report["cost"] == {"judge_calls": 0, "estimated_yuan": 0}
    assert report["gate"]["verdict"] in ("pass", "blocked")


def test_entry_exception_becomes_failure():
    def boom():
        raise RuntimeError("boom")

    report, code = run_group(_reg(_callable("boom", boom)), "fast")
    assert code == 1
    case = _flatten(report)[0]
    assert case["status"] == "fail"
    assert "boom" in case["details"]


def test_function_entry_normalizes_results(monkeypatch):
    class FakeMod:
        @staticmethod
        def run():
            class R:
                results = [{"name": "c1", "passed": True}]

            return R()

    monkeypatch.setitem(sys.modules, "fake", FakeMod)
    entry = {"name": "f", "kind": "function", "module": "fake", "func": "run"}
    report, code = run_group(_reg(entry), "fast")
    assert code == 0
    assert report["summary"]["passed"] == 1


# ── only filter ──────────────────────────────────────────────────────────

def test_only_filter_runs_single_entry():
    reg = _reg(
        _callable("a", lambda: _cases([("a1", True)])),
        _callable("b", lambda: _cases([("b1", False)])),
    )
    report, code = run_group(reg, "fast", only="a")
    assert code == 0
    assert report["summary"] == {
        "total": 1, "passed": 1, "failed": 0, "severe": 0, "pending": 0, "warnings": 0,
    }


def test_only_unknown_entry_raises():
    with pytest.raises(ValueError):
        run_group(_reg(_callable("a", lambda: [])), "fast", only="nope")


def test_extra_warnings_land_in_report():
    entry = _callable("ok", lambda: _cases([("c1", True)]))
    report, code = run_group(_reg(entry), "fast", extra_warnings=["tool 'x' missing from coverage"])
    assert code == 0
    assert report["warnings"] == ["tool 'x' missing from coverage"]
    assert report["summary"]["warnings"] == 0, "extra warnings do not count as case warnings"


def test_coverage_warnings_flags_missing_tools():
    from evals.tool_coverage import coverage_warnings
    manifest = {"tool_a": {"category": "l0", "where": "x"}}
    warnings = coverage_warnings(manifest=manifest, tool_names=["tool_a", "tool_b"])
    assert warnings == ["tool 'tool_b' missing from L0 coverage manifest (evals/tool_coverage.py)"]
    assert coverage_warnings(manifest=manifest, tool_names=["tool_a"]) == []


# ── trend archiving ──────────────────────────────────────────────────────

def test_save_report_archives_and_indexes(tmp_path):
    entry = _callable("ok", lambda: _cases([("c1", True)]))
    report, code = run_group(_reg(entry), "fast", report_dir=tmp_path)
    assert code == 0

    files = list(tmp_path.glob("*-fast.json"))
    assert len(files) == 1
    saved = json.loads(files[0].read_text(encoding="utf-8"))
    assert saved["gate"]["verdict"] == "pass"

    index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert len(index["runs"]) == 1
    assert index["runs"][0]["file"] == files[0].name

    # second run appends to the same index (trend series)
    run_group(_reg(_callable("ok", lambda: _cases([("c1", True)]))), "fast", report_dir=tmp_path)
    index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert len(index["runs"]) == 2

"""
L2 judge harness tests (Spec 04) — fake providers, canned responses, zero API.

Pins the external contract of the judge seam:
  judge(sample, rubric_family) -> {score, confidence, rationale, severe_flags}
plus parse robustness, the 200-call cap, cost ledger, calibration schema
validation and enablement rules.
"""
import asyncio
import json

import pytest

from evals.judge import (
    AGREEMENT_TOLERANCE,
    ENABLE_THRESHOLD,
    FAMILY_NAMES,
    MAX_JUDGE_CALLS,
    MIN_CALIBRATION_SAMPLES,
    JudgeRunner,
    ScriptedJudgeProvider,
    build_prompt,
    parse_judge_response,
)


def _resp(score=80, confidence="high", rationale="ok", flags=None):
    return json.dumps({"score": score, "confidence": confidence,
                       "rationale": rationale, "severe_flags": flags or []})


# ── parse robustness ─────────────────────────────────────────────────────

def test_parse_valid_json():
    r = parse_judge_response(_resp(85), "question_gen")
    assert r["score"] == 85 and r["confidence"] == "high" and r["parse_error"] is False


def test_parse_code_fenced_json():
    r = parse_judge_response(f"```json\n{_resp(72, 'medium')}\n```", "grading")
    assert r["score"] == 72 and r["confidence"] == "medium"


def test_parse_invalid_marks_parse_error():
    r = parse_judge_response("抱歉，我无法评估。", "question_gen")
    assert r["score"] is None and r["confidence"] == "low" and r["parse_error"] is True


def test_parse_clamps_and_defaults_confidence():
    assert parse_judge_response(_resp(150), "plan")["score"] == 100
    assert parse_judge_response(_resp(-5), "plan")["score"] == 0
    assert parse_judge_response(_resp(80, "unsure"), "plan")["confidence"] == "low"


def test_severe_flag_only_for_family_severe():
    r = parse_judge_response(_resp(10, "high", "化学错误", ["chemical_error"]), "question_gen")
    assert r["severe_flags"] == ["chemical_error"]
    # grading 族没有 chemical_error 语义，应被过滤
    r2 = parse_judge_response(_resp(10, "high", "", ["chemical_error"]), "grading")
    assert r2["severe_flags"] == []


def test_unknown_family_raises():
    with pytest.raises(ValueError):
        build_prompt({"input": "x"}, "nonexistent")


def test_prompt_contains_dimensions_and_contract():
    p = build_prompt({"input": "出题", "output": "..."}, "question_gen")
    assert "化学正确性" in p and "权重 0.5" in p
    assert "severe_flags" in p
    for family in FAMILY_NAMES:
        assert build_prompt({"input": "x"}, family)  # all five build


# ── runner: cap, cost, errors ────────────────────────────────────────────

def test_judge_with_scripted_provider_counts_calls():
    provider = ScriptedJudgeProvider([_resp(88)])
    runner = JudgeRunner(provider)

    async def go():
        return await runner.judge({"input": "出题", "output": "..."}, "question_gen")

    r = asyncio.run(go())
    assert r["score"] == 88 and runner.calls == 1 and runner.cost_yuan > 0


def test_batch_call_cap_truncates():
    samples = [{"input": f"x{i}", "output": "y"} for i in range(5)]

    async def go():
        provider = ScriptedJudgeProvider([_resp(70)] * 5)
        runner = JudgeRunner(provider)
        results, truncated = await runner.judge_batch(samples, "grading", max_calls=2)
        return results, truncated, runner

    results, truncated, runner = asyncio.run(go())
    assert runner.calls == 2 and truncated == 3
    assert sum(1 for r in results if r.get("truncated")) == 3
    assert results[-1]["confidence"] == "low"


def test_provider_error_becomes_soft_failure():
    class BoomProvider(ScriptedJudgeProvider):
        async def complete(self, prompt):
            raise RuntimeError("api down")

    async def go():
        return await JudgeRunner(BoomProvider([])).judge({"input": "x"}, "grading")

    r = asyncio.run(go())
    assert r["score"] is None and r.get("provider_error") is True


# ── calibration rules ────────────────────────────────────────────────────

def test_calibration_sets_schema_valid():
    from evals.calibrate import load_calibration_set
    for family in FAMILY_NAMES:
        samples, errors, warnings = load_calibration_set(family)
        assert errors == [], f"{family}: {errors}"
        # 参考集（build_reference.py 生成）补齐后各族应达到启用样本门槛
        assert len(samples) >= MIN_CALIBRATION_SAMPLES, \
            f"{family}: {len(samples)} < {MIN_CALIBRATION_SAMPLES}"
        assert not any("样本不足" in w for w in warnings)


def test_calibration_set_schema_rejects_bad_sample(tmp_path, monkeypatch):
    from evals import calibrate
    bad = tmp_path / "question_gen.yaml"
    bad.write_text("family: question_gen\nsamples:\n  - id: x\n    input: a\n", encoding="utf-8")
    monkeypatch.setattr(calibrate, "CALIBRATION_DIR", tmp_path)
    samples, errors, warnings = calibrate.load_calibration_set("question_gen")
    assert any("缺 output" in e for e in errors)
    assert any("human_score" in e for e in errors)


def test_agreement_with_tolerance():
    from evals.calibrate import compute_agreement
    samples = [{"human_score": 80}, {"human_score": 50}]
    results = [{"score": 87}, {"score": 60}]  # 87-80<=10 一致；60-50=10 一致
    rate, agrees = compute_agreement(results, samples)
    assert rate == 1.0 and agrees == 2
    results = [{"score": 95}, {"score": None}]  # 95-80>10 不一致；解析失败不一致
    rate, agrees = compute_agreement(results, samples)
    assert rate == 0.0 and agrees == 0


def test_enablement_requires_samples_and_rate():
    from evals.calibrate import compute_agreement
    # 小样本 + 100% 一致率 → 仍不可启用
    samples = [{"human_score": 80}] * 5
    results = [{"score": 80}] * 5
    rate, _ = compute_agreement(results, samples)
    enabled = len(samples) >= MIN_CALIBRATION_SAMPLES and rate >= ENABLE_THRESHOLD
    assert not enabled, "样本不足时即使一致率 100% 也不得启用"
    # 足量 + 一致率达标 → 启用
    samples = [{"human_score": 80}] * 20
    results = [{"score": 80}] * 20
    rate, _ = compute_agreement(results, samples)
    assert len(samples) >= MIN_CALIBRATION_SAMPLES and rate >= ENABLE_THRESHOLD


def test_agreement_tolerance_constant():
    assert AGREEMENT_TOLERANCE == 10 and ENABLE_THRESHOLD == 0.8
    assert MAX_JUDGE_CALLS == 200

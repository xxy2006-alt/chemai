# ChemAI Evals 体系

> **Authoritative source:** `评测文档/evals/` — 111 scenarios × 14 dimensions × 3 layers
>
> This document is a navigation index. Scenario definitions and CI gates live in `评测文档/evals/`.
> Executable tests live in `evals/` and `tests/`.

## 体系架构

```
评测文档/evals/              ← Authoritative (YAML definitions, CI gates, coverage)
  ├── baseline/              4 dims, 59 scenarios
  ├── boundary/              5 dims, 29 scenarios
  └── regression/            5 dims, 23+ scenarios

evals/                        ← Executable test runners
  run_evals.py                Unified runner
  test_unit_tools.py          Capability
  test_classifier.py          Routing
  test_agent_routing.py       Routing (needs API)
  test_sse_streaming.py       State
  test_safety_isolation.py    Safety
  test_regression_defects.py  Regression

tests/                        ← Unit/integration (pytest)
  test_tool_filtering.py      test_tutor_factory.py
  test_practice_pipeline.py   test_ocr_pipeline.py
  test_llm_grading.py         conftest.py
```

## 14 维度

See `评测文档/evals/README.md` for complete taxonomy. Quick reference:

| # | 维度 | 层 | 场景数 | CI警告 | CI阻断 | 可执行? |
|---|------|-----|:---:|:---:|:---:|:---:|
| 1 | 路由准确性 | Baseline | 32 | 0.90 | 0.80 | ✅ |
| 2 | 工具调用准确性 | Baseline | 8 | 0.85 | 0.75 | ✅ |
| 3 | 工作流完整性 | Baseline | 12 | 0.80 | 0.70 | partial |
| 4 | 行为约束 | Baseline | 7 | 0.85 | 0.75 | partial |
| 5 | 边界情况 | Boundary | 12 | 0.80 | 0.65 | — |
| 6 | 错误恢复 | Boundary | 8 | 0.75 | 0.60 | — |
| 7 | 工具结果利用 | Boundary | 2 | 0.80 | 0.65 | — |
| 8 | 计划连贯性 | Boundary | 4 | 0.80 | 0.65 | — |
| 9 | 状态转换 | Boundary | 3 | 0.85 | 0.70 | — |
| 10 | 跨角色权限 | Regression | 6 | 0.85 | 0.70 | ✅ |
| 11 | SSE流式传输 | Regression | 5 | 1.00 | 0.90 | ✅ |
| 12 | 一致性(Pass@k) | Regression | 7 | 0.80 | 0.65 | — |
| 13 | 性能基线 | Regression | 9 metrics | 0.85 | 0.70 | — |
| 14 | 已知缺陷回归 | Regression | 5+ | 1.00 | 0.95 | ✅ |

## 当前真实覆盖

```
Capability:   57 tests ✅  (tests/ 41 + evals/unit 16)
Routing:      18 tests ✅  (evals/classifier 12 + evals/agent 6)
Safety:        7 tests ✅  (evals/test_safety_isolation)
State:         5 tests ⚠  (evals/sse 2 + tests/practice 3)
Quality:       0 tests ❌  (LLM-as-judge not yet implemented)
Regression:    9 tests ✅  (evals/test_regression_defects)
─────────────────────────
Total:        96 tests (93 pass, 2 pre-existing broken, 1 needs env)
```

## 快速开始

```bash
# Deterministic (no LLM, <5s)
pytest tests/ evals/test_safety_isolation.py evals/test_regression_defects.py -q

# Routing (needs DeepSeek API, ~2min)
python evals/run_evals.py --agent --classifier

# SSE (needs DeepSeek API, ~15s)
python evals/run_evals.py --sse

# Full suite
python evals/run_evals.py --save
```

## 相关文档

| 路径 | 内容 |
|------|------|
| `评测文档/evals/README.md` | **Authoritative** — 14 dimension taxonomy |
| `评测文档/evals/baseline/` | Baseline YAML: routing, tool_call, workflow, constraint |
| `评测文档/evals/boundary/` | Boundary YAML: edge_case, error_recovery, plan, result, state |
| `评测文档/evals/regression/` | Regression YAML: cross_role, sse, consistency, perf, monitoring |
| `docs/evals/rubric.md` | Scoring standards + LLM-as-judge template |
| `docs/evals/regression.md` | Regression set management strategy |

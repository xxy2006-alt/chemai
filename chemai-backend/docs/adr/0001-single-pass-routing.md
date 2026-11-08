# ADR-0001: Single-Pass Intent Routing

**Date**: 2026-06-25
**Status**: Accepted

## Context

The ChemAI agent routing pipeline passes every user message through three LLM decision points:

1. **Gateway** (`agent/gateway.py`): LLM classifier → `(intent_type, suggested_tools, provider)`. Has a keyword fallback for parse failures.
2. **Coordinator** (`agent/langgraph_agent.py:_coordinator_node`): LLM with `route_to_*` tools → selects a sub-agent.
3. **Sub-Agent** (`agent/langgraph_agent.py:create_sub_agent_node`): LLM with domain tools → picks which tool to call.

Each layer re-evaluates the same user message through a different prompt. The layers do not share their decisions as structured state. When any layer produces an unexpected output (missing prompt rule, hallucination), the entire chain fails silently.

A concrete failure: user says "我有几个班". Gateway routes correctly. Coordinator routes correctly. But the diagnosis_expert sub-agent's hand-written prompt rules don't cover this phrasing, so the LLM generates "请告诉我您想查看哪个班级的学生" instead of calling `show_students()` — despite `show_students`'s docstring explicitly covering "问有几个班".

Additionally, the sub-agent prompts duplicate the guidance already in tool docstrings, creating an unsustainable maintenance burden where every new user expression requires a new prompt rule.

## Decision

Replace the three-pass routing with a single-pass design in three phases:

### Phase 1: Trust tool descriptions over hand-written prompt rules

- Remove numbered "规则" lists from all 6 sub-agent prompts in `_SUB_AGENT_DEFS`.
- Replace with a unified template: "你必须调用一个工具。阅读每个工具的描述来决定用哪个。"
- Each sub-agent keeps at most one line of domain-specific guidance (e.g., `delete_bank` needs approval).
- Rewrite `_SUB_AGENT_OUTPUT_CONTRACT` as a positive constraint: "必须先调用至少一个工具" instead of only "严禁闲聊".

### Phase 2: Golden routing test suite

- Create `evals/golden_routing.yaml` with 20 routing test cases.
- Create `evals/test_routing.py` as the test runner.
- Each entry: `(input, expected_agent, expected_tool)`.
- Covers: known bugs, each sub-agent's core patterns, boundary cases.

### Phase 3: Collapse Gateway + Coordinator

- Gateway absorbs Coordinator's routing responsibility.
- Gateway output becomes `(intent_type, target_agent, suggested_tools, provider)`.
- Keyword router becomes the primary dispatcher with confidence-graded LLM fallback:
  - **High confidence** (multi-keyword, no ambiguity): dispatch directly, no LLM call.
  - **Low confidence** (single keyword or ambiguous word): call LLM for verification.
  - **No match**: call LLM.
- Coordinator becomes a deterministic state-reader (~10 lines, no LLM call).
- Gateway results are passed as structured `shared_context` in graph state — no longer discarded.
- Sub-agent behavior unchanged.

## Alternatives Considered

### Keep prompt rules but expand them
Adding more rules to cover missing cases is an infinite game. Each user expression variant requires a new rule. Rejected as unsustainable.

### LLM + keyword mutual verification on every request
Both systems check every message and cross-validate. This eliminates the primary benefit of Phase 3 (removing an LLM call) and introduces a new arbitration problem when they disagree. Rejected in favor of confidence-graded dispatch.

### Coordinator absorbs Gateway
Moving classification logic into the Coordinator's system prompt would lose the keyword fallback (which lives in Gateway) and the navigate shortcut optimization. Rejected.

## Consequences

- **Positive**: One LLM call instead of two for the routing path (Phase 3). Sub-agents trust tool descriptions, eliminating the prompt-rule maintenance burden (Phase 1).
- **Positive**: Routing behavior becomes testable via golden datasets (Phase 2).
- **Negative**: Phase 3 requires restructuring the Gateway interface and graph state schema. Higher implementation risk.
- **Negative**: Removing hand-written prompt rules shifts trust to LLM function-calling fidelity. The golden test suite (Phase 2) mitigates this by catching regressions.

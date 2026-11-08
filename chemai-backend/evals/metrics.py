"""
L4 performance budget — instrumentation seam (Spec 02, seam 4).

Design: docs/evals/eval-system-design.md §2 L4 — latency / tokens / iterations SLO.
Spec:   docs/specs/evals/spec-02-fast-layer.md — soft warnings first, thresholds
        in one place so they can be tightened later.

The agent body is NOT modified: invoke_with_metrics wraps any agent.ainvoke.
tokens are read from message usage_metadata where the LLM runtime provides it;
when absent they stay None ("未测量") — honesty over pretending.
"""
import time

DEFAULT_SLO = {
    "max_latency_s": 60,   # p95 目标，先按单次调用软警告
    "max_tokens": 40000,   # 单次运行 token 上限
    "max_iterations": 12,  # 与 v2 recursion_limit 对齐
}


def _usage_of(msg):
    if isinstance(msg, dict):
        return msg.get("usage_metadata")
    return getattr(msg, "usage_metadata", None)


def _type_of(msg):
    if isinstance(msg, dict):
        return msg.get("type")
    return getattr(msg, "type", None)


def extract_metrics(agent_result, start_time):
    """Extract {latency_s, tokens, iterations} from a LangGraph invoke result.

    iterations = number of AI messages (ReAct turns).
    tokens = sum of input+output usage_metadata across messages; None if the
    runtime reported nothing (the SLO checker then skips the token check).
    """
    latency = round(time.time() - start_time, 2)
    messages = agent_result.get("messages", []) if isinstance(agent_result, dict) else []
    iterations = sum(1 for m in messages if _type_of(m) == "ai")
    tokens = None
    for m in messages:
        usage = _usage_of(m)
        if usage:
            tok = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
            tokens = (tokens or 0) + tok
    return {"latency_s": latency, "tokens": tokens, "iterations": iterations}


def check_slo(metrics, thresholds=None):
    """Return warn lines for SLO violations. None value -> metric not measured."""
    thresholds = thresholds or DEFAULT_SLO
    warnings = []
    if metrics.get("latency_s") is not None and metrics["latency_s"] > thresholds["max_latency_s"]:
        warnings.append(
            f"SLO warn: latency {metrics['latency_s']}s > {thresholds['max_latency_s']}s"
        )
    if metrics.get("tokens") is not None and metrics["tokens"] > thresholds["max_tokens"]:
        warnings.append(
            f"SLO warn: tokens {metrics['tokens']} > {thresholds['max_tokens']}"
        )
    if metrics.get("iterations") is not None and metrics["iterations"] > thresholds["max_iterations"]:
        warnings.append(
            f"SLO warn: iterations {metrics['iterations']} > {thresholds['max_iterations']}"
        )
    return warnings


async def invoke_with_metrics(agent, input_payload, config=None):
    """Thin wrapper: invoke the agent and return (result, metrics)."""
    started = time.time()
    if config is None:
        result = await agent.ainvoke(input_payload)
    else:
        result = await agent.ainvoke(input_payload, config=config)
    return result, extract_metrics(result, started)

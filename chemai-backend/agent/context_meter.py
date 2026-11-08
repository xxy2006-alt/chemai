"""上下文占用计量 — DSH token-meter 的轻量移植版.

数据流:模型流式响应末尾的 usage(provider 权威值)作为已用 token 锚点,
system/tools/messages 三段构成用固定启发式估算(4 字符 ≈ 1 token + 结构开销),
与 DSH 的 contextPressure / contextBreakdown 投影同思路。
占用百分比是用户参考值,不做任何计费或门禁决策。
"""

import logging

logger = logging.getLogger(__name__)

# 固定文本密度估算(DSH estimate.ts 同款)
CHARS_PER_TOKEN = 4
ROLE_OVERHEAD = 4  # role 字段框开销
BLOCK_OVERHEAD = 4  # 内容块结构开销


def estimate_tokens(text: str) -> int:
    """按固定密度估算一段文本的 token 数。"""
    import math
    return math.ceil(len(text or "") / CHARS_PER_TOKEN) + BLOCK_OVERHEAD


def estimate_message_tokens(role: str, content: str) -> int:
    """估算一条消息的 token 数(内容 + role 框开销)。"""
    return estimate_tokens(content or "") + ROLE_OVERHEAD


def estimate_surface(messages: list) -> tuple[int, int, int]:
    """按角色估算会话表面的三段构成 (system, tools, messages)。

    与 DSH 的 contextBreakdown 对齐:system=系统提示, tools=工具调用/结果,
    messages=普通对话。LangChain 消息对象兼容 (getattr content/type)。
    """
    system_tokens = 0
    tools_tokens = 0
    message_tokens = 0
    for m in messages or []:
        content = str(getattr(m, "content", "") or "")
        role = str(getattr(m, "type", "") or "")
        if role == "system":
            system_tokens += estimate_message_tokens("system", content)
        elif role in ("tool", "tool_result") or getattr(m, "tool_calls", None):
            tools_tokens += estimate_message_tokens("tool", content)
        else:
            message_tokens += estimate_message_tokens(role, content)
    return system_tokens, tools_tokens, message_tokens


def extract_prompt_tokens(output) -> int | None:
    """从 LangChain 模型输出(AIMessage/事件 output)提取 provider 报告的 prompt token 数。

    流式场景取 usage_metadata.input_tokens(langchain 聚合,含 cache 输入);
    非流式/原始字段兜底 response_metadata.token_usage.prompt_tokens。
    """
    if output is None:
        return None
    # 多输出(list)取最后一个
    if isinstance(output, list):
        return extract_prompt_tokens(output[-1] if output else None)
    try:
        usage_metadata = getattr(output, "usage_metadata", None)
        if isinstance(usage_metadata, dict):
            tokens = usage_metadata.get("input_tokens")
            if isinstance(tokens, int) and tokens > 0:
                return tokens
        response_metadata = getattr(output, "response_metadata", None) or {}
        token_usage = response_metadata.get("token_usage") or {}
        if isinstance(token_usage, dict):
            tokens = token_usage.get("prompt_tokens")
            if isinstance(tokens, int) and tokens > 0:
                return tokens
    except Exception:
        logger.debug("extract_prompt_tokens failed", exc_info=True)
    return None


def build_context_event(prompt_tokens: int | None, messages: list, context_window: int) -> dict:
    """构造 SSE context 事件负载。

    used_tokens 优先取 provider 报告的 prompt_tokens(权威锚点);
    拿不到时回退三段启发式估算之和。percent 与 DSH 一致:
    min(100, round(used / window * 100))。
    """
    system_tokens, tools_tokens, message_tokens = estimate_surface(messages)
    if prompt_tokens is not None:
        used_tokens = prompt_tokens
        # 三段构成自洽:provider 计费含系统提示+工具 schema,但二者不在会话消息里,
        # 把扣除对话/工具消息估算后的余量归入 system_tokens
        remainder = used_tokens - tools_tokens - message_tokens
        if remainder > 0:
            system_tokens = remainder
    else:
        used_tokens = system_tokens + tools_tokens + message_tokens
    percent = min(100, round(used_tokens / context_window * 100)) if context_window > 0 else 0
    return {
        "type": "context",
        "used_tokens": used_tokens,
        "context_window": context_window,
        "percent": percent,
        "breakdown": {
            "system_tokens": system_tokens,
            "tools_tokens": tools_tokens,
            "message_tokens": message_tokens,
        },
    }

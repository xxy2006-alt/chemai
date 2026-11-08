"""Smart context management — TrimMessages strategy + LLM summarization.

Replaces hardcoded 30-message truncation with:
1. Unconditional retention: last 6 messages (3 turns)
2. Conditional retention: messages containing student/diagnosis/exam keywords
3. LLM summarization at 30-message (15-turn) threshold for non-retained messages
"""

import logging

logger = logging.getLogger(__name__)

# Keywords that trigger conditional message retention
_KEEP_KEYWORDS = [
    "学生", "诊断", "障碍", "考试", "题目", "知识点", "分数", "薄弱",
    "学习计划", "错题", "成绩", "练习", "班级", "教师",
]


async def trim_context(agent, config, keep_last: int = 6, max_messages: int = 30):
    """Trim conversation context using hybrid strategy.

    Args:
        agent: LangGraph compiled graph
        config: Invocation config with thread_id
        keep_last: Unconditionally retain last N messages
        max_messages: Trigger threshold for trim operation
    """
    try:
        state = await agent.aget_state(config)
    except Exception:
        return

    if not state or not state.values:
        return

    messages = list(state.values.get("messages", []))
    if len(messages) <= max_messages:
        return

    # Phase 1: Identify messages to keep（middle_kept 限量，避免化学关键词
    # 几乎命中全部消息导致上下文不减、每轮重复摘要——2026-08 性能修复）
    recent = messages[-keep_last:]
    middle_kept = []
    to_discard = []

    for msg in messages[:-keep_last]:
        content = str(getattr(msg, "content", ""))
        if any(kw in content for kw in _KEEP_KEYWORDS):
            middle_kept.append(msg)
        else:
            to_discard.append(msg)
    middle_kept = middle_kept[-10:]  # 关键词保留上限：最多 10 条

    # Phase 2: Summarize if there are enough discarded messages
    new_messages = list(messages)  # default: keep all
    if len(to_discard) >= 10:
        try:
            summary = await _llm_summarize(to_discard)
            from langchain_core.messages import SystemMessage
            summary_msg = SystemMessage(content=f"[对话摘要] {summary}")
            new_messages = [summary_msg] + middle_kept + recent
        except Exception as e:
            logger.warning(f"Summary failed, falling back to trim: {e}")
            new_messages = middle_kept + recent
    else:
        new_messages = middle_kept + recent

    # Apply trimmed messages
    try:
        await agent.aupdate_state(config, {"messages": new_messages})
    except Exception as e:
        logger.warning(f"Context trim update failed: {e}")


async def _llm_summarize(messages: list) -> str:
    """Call LLM to compress messages into a short Chinese summary.

    性能（2026-08）：单条截断 120 字、最多 20 条 → 摘要输入 ≈1.5k tokens，
    摘要调用 2-4s 而非 10s+。"""
    from agent.langgraph_agent import get_langchain_model
    from langchain_core.messages import SystemMessage, HumanMessage

    model = get_langchain_model("deepseek")
    recent_msgs = messages[-20:]
    text = "\n".join(
        f"[{getattr(m, 'type', 'msg')}]: {str(getattr(m, 'content', ''))[:120]}"
        for m in recent_msgs
    )

    resp = await model.ainvoke([
        SystemMessage(
            content="将以下对话历史压缩为中文摘要。保留: 学生姓名、知识点、诊断结果、教师偏好、关键决定。最多200字。"
        ),
        HumanMessage(content=text),
    ])
    return resp.content

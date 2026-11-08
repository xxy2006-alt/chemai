/* context-meter.ts — 上下文占用前端工具(DSH token-meter 启发式移植)
 * 流式回复结束时后端下发 provider usage 锚定的精确值;
 * 历史加载/新会话用同款启发式(4 字符 ≈ 1 token + 结构开销)估算占位。 */

import type { ChatItem } from '../components/chat/MessageList'
import type { ContextEvent } from './agent-sse'

/** deepseek-chat 当前上下文容量(与后端 app/config.py CONTEXT_WINDOW 默认一致) */
export const DEFAULT_CONTEXT_WINDOW = 128_000

const CHARS_PER_TOKEN = 4
const ROLE_OVERHEAD = 4
const BLOCK_OVERHEAD = 4

export function estimateTokens(text: string): number {
  return Math.ceil((text || '').length / CHARS_PER_TOKEN) + BLOCK_OVERHEAD
}

/** 按历史消息估算上下文占用(三段构成:系统提示/工具/对话) */
export function estimateContextFromHistory(
  items: ChatItem[],
  windowSize = DEFAULT_CONTEXT_WINDOW,
): ContextEvent {
  let system = 0
  let tools = 0
  let messages = 0
  for (const it of items) {
    const text =
      it.kind === 'tool' ? JSON.stringify(it.card?.data ?? '') : (it as { text?: string }).text ?? ''
    const tokens = estimateTokens(text) + ROLE_OVERHEAD
    if (it.kind === 'system') system += tokens
    else if (it.kind === 'tool') tools += tokens
    else messages += tokens
  }
  const used = system + tools + messages
  return {
    type: 'context',
    used_tokens: used,
    context_window: windowSize,
    percent: windowSize > 0 ? Math.min(100, Math.round((used / windowSize) * 100)) : 0,
    breakdown: { system_tokens: system, tools_tokens: tools, message_tokens: messages },
  }
}

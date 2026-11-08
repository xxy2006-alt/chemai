/* ChatPanel.tsx — 移动端流式对话面板（学生 AI 助教 / 家长 AI 助手共用）。
 * 协议：POST /api/agent/chat/langgraph/stream（persona 参数化）+ streamAgent 解析。
 * 气泡（P-01）：用户 = 主色实底胶囊（on-primary 深字）；AI = surface 底 + 品牌青描边。
 * R-I1：发送后输入框清空并禁用至回合结束。 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { Send, Sparkles } from 'lucide-react'
import { postStream, streamAgent, type AgentEvent } from '../../lib/agent-sse'
import { api } from '../../lib/api'
import { ChemMd } from '../ChemMd'

type ChatMsg =
  | { id: string; kind: 'msg'; role: 'user' | 'ai'; text: string }
  | { id: string; kind: 'tool'; name: string; status: 'running' | 'ok' | 'error' }

let uid = 0
const nid = () => `mm${Date.now()}_${uid++}`

export function ChatPanel({
  persona,
  cid,
  studentId,
  intro,
  quickPrompts = [],
  placeholder = '输入问题…',
  loadHistory = true,
  footerPadding = true,
}: {
  persona: 'student' | 'parent'
  cid: string
  studentId?: string
  intro?: React.ReactNode
  quickPrompts?: string[]
  placeholder?: string
  loadHistory?: boolean
  footerPadding?: boolean
}) {
  const [messages, setMessages] = useState<ChatMsg[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [error, setError] = useState('')
  const bodyRef = useRef<HTMLDivElement>(null)
  const cidRef = useRef(cid)
  cidRef.current = cid

  const scrollBottom = () => {
    requestAnimationFrame(() => {
      const el = bodyRef.current
      if (el) el.scrollTop = el.scrollHeight
    })
  }

  /* 切换会话 → 加载历史 */
  useEffect(() => {
    if (!loadHistory || !cid) return
    let cancelled = false
    api.get<{ messages?: { role?: string; type?: string; content?: string }[] }>(
      `/api/agent/chat/history/${cid}`,
    )
      .then((d) => {
        if (cancelled) return
        const items: ChatMsg[] = (d.messages || [])
          .map((m) => {
            const isUser = m.role === 'user' || m.role === 'human' || m.type === 'user'
            return { id: nid(), kind: 'msg' as const, role: isUser ? ('user' as const) : ('ai' as const), text: m.content || '' }
          })
          .filter((m) => m.text.trim())
        setMessages(items)
        scrollBottom()
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [cid, loadHistory])

  const send = useCallback(
    (raw?: string) => {
      const text = (raw ?? input).trim()
      if (!text || streaming) return
      setInput('')
      setError('')
      setStreaming(true)
      setMessages((prev) => [...prev, { id: nid(), kind: 'msg', role: 'user', text }])
      scrollBottom()

      const apply = (fn: (prev: ChatMsg[]) => ChatMsg[]) => {
        setMessages((prev) => {
          const next = fn(prev)
          scrollBottom()
          return next
        })
      }
      const patchLastAi = (append: string) =>
        apply((prev) => {
          const last = prev[prev.length - 1]
          if (last && last.kind === 'msg' && last.role === 'ai') {
            return [...prev.slice(0, -1), { ...last, text: last.text + append }]
          }
          return [...prev, { id: nid(), kind: 'msg', role: 'ai', text: append }]
        })

      const handleEvent = (evt: AgentEvent) => {
        if (evt.type === 'text' || evt.type === 'subagent_text') {
          patchLastAi(evt.content || '')
        } else if (evt.type === 'tool_call') {
          apply((prev) => [...prev, { id: nid(), kind: 'tool', name: evt.name || '', status: 'running' }])
        } else if (evt.type === 'tool_result') {
          apply((prev) => {
            const idx = [...prev].reverse().findIndex((m) => m.kind === 'tool' && m.status === 'running')
            if (idx === -1) return prev
            const real = prev.length - 1 - idx
            const next = [...prev]
            const tool = next[real]
            if (tool.kind === 'tool') {
              next[real] = { ...tool, status: evt.success === false ? 'error' : 'ok' }
            }
            return next
          })
        } else if (evt.type === 'component') {
          const p = (evt.params || {}) as { report?: unknown; summary?: string }
          const msg = p.report ? '已生成学习报告' : p.summary || ''
          if (msg) apply((prev) => [...prev, { id: nid(), kind: 'msg', role: 'ai', text: msg }])
        } else if (evt.type === 'error') {
          setError(evt.message || '出错了，请重试')
        }
      }

      postStream('/api/agent/chat/langgraph/stream', {
        message: text,
        conversationId: cidRef.current,
        persona,
        studentId,
      })
        .then((resp) =>
          streamAgent(resp, {
            onEvent: handleEvent,
            onDone: () => setStreaming(false),
            onError: (m) => {
              setError(m)
              setStreaming(false)
            },
          }),
        )
        .catch((e: Error) => {
          setError(e.message || '发送失败，请重试')
          setStreaming(false)
        })
    },
    [input, streaming, persona, studentId],
  )

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* 消息区 */}
      <div ref={bodyRef} className="flex-1 min-h-0 overflow-y-auto px-3.5 pt-3 flex flex-col gap-2">
        {messages.length === 0 && intro}
        {messages.map((m) =>
          m.kind === 'tool' ? (            <div
              key={m.id}
              className="self-center max-w-[90%] flex items-center gap-1.5 text-[11.5px] text-ink-muted bg-surface-muted/70 border border-border/50 rounded-full px-3 py-1"
            >
              <Sparkles size={12} className={m.status === 'ok' ? 'text-success' : m.status === 'error' ? 'text-error' : 'text-teal'} />
              {m.name}
              {m.status === 'running' ? ' · 处理中' : m.status === 'ok' ? ' · 完成' : ' · 失败'}
            </div>
          ) : m.kind === 'msg' && m.role === 'user' ? (
            <div
              key={m.id}
              className="self-end max-w-[84%] px-3.5 py-2 bg-primary text-on-primary text-[14px] leading-relaxed rounded-[20px] rounded-br-[6px] break-words whitespace-pre-wrap"
            >
              {m.text}
            </div>
          ) : (
            <div
              key={m.id}
              className="self-start max-w-[88%] px-3.5 py-2 bg-surface border border-teal/30 text-[14px] leading-relaxed rounded-[20px] rounded-bl-[6px] break-words shadow-[var(--shadow-sm)]"
            >
              <ChemMd text={m.text} className="!text-[color:var(--color-ink)]" />
            </div>
          ),
        )}
        {streaming && (
          <div className="self-start flex items-center gap-1.5 px-3.5 py-2.5 bg-surface border border-teal/30 rounded-[20px] rounded-bl-[6px]">
            <span className="w-1.5 h-1.5 rounded-full bg-ink-muted animate-bounce [animation-delay:0ms]" />
            <span className="w-1.5 h-1.5 rounded-full bg-ink-muted animate-bounce [animation-delay:150ms]" />
            <span className="w-1.5 h-1.5 rounded-full bg-ink-muted animate-bounce [animation-delay:300ms]" />
          </div>
        )}
        {error && (
          <div className="self-center text-[12px] text-error bg-error-soft rounded-full px-3 py-1">
            {error}
          </div>
        )}
      </div>

      {/* 快捷提示 chips */}
      {quickPrompts.length > 0 && (
        <div className="shrink-0 flex gap-2 px-3.5 py-2 overflow-x-auto [scrollbar-width:none]">
          {quickPrompts.map((q) => (
            <button
              key={q}
              onClick={() => send(q)}
              disabled={streaming}
              className="shrink-0 px-3.5 py-1.5 rounded-full border border-border bg-surface text-[12.5px] text-ink-secondary active:bg-primary-soft active:text-primary active:border-primary transition-colors disabled:opacity-40"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* 输入区 */}
      <div
        className={`shrink-0 flex gap-2 px-3.5 pt-2 bg-bg border-t border-border/60 ${
          footerPadding ? 'pb-[max(10px,env(safe-area-inset-bottom))]' : 'pb-2.5'
        }`}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') send()
          }}
          placeholder={placeholder}
          disabled={streaming}
          className="flex-1 min-w-0 h-11 px-4 rounded-full border-[1.5px] border-border bg-surface-muted text-[14px] text-ink placeholder:text-ink-muted outline-none focus:border-primary transition-colors disabled:opacity-50"
        />
        <button
          onClick={() => send()}
          disabled={streaming || !input.trim()}
          className="w-11 h-11 shrink-0 rounded-full bg-primary text-on-primary flex items-center justify-center active:scale-90 transition-transform disabled:opacity-40"
          aria-label="发送"
        >
          <Send size={17} />
        </button>
      </div>
    </div>
  )
}

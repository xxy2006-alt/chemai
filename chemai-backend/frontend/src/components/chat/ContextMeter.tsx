/* ContextMeter.tsx — 发送键下方的上下文占用圆环(DSH ContextMeter 同款)
 * 圆环按占用百分比画弧,悬停 title 提示,点击展开构成面板:
 * 已用/总量 + 分段条 + 系统提示/工具/对话 三段明细。 */

import { useEffect, useRef, useState } from 'react'
import type { ContextEvent } from '../../lib/agent-sse'

/** 环几何:14px viewBox,2px stroke(DSH 同款) */
const RADIUS = 5.5
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

/** 紧凑 token 数:517 / 12.2K / 517K / 1.2M(DSH formatTokens 同款) */
export function formatTokens(n: number): string {
  const scaled = (v: number) => (v >= 100 ? String(Math.round(v)) : String(Math.round(v * 10) / 10))
  if (n < 1_000) return String(n)
  if (n < 1_000_000) return `${scaled(n / 1_000)}K`
  return `${scaled(n / 1_000_000)}M`
}

const SYSTEM_COLOR = 'var(--color-primary)'
const TOOLS_COLOR = 'var(--color-teal)'
const MESSAGES_COLOR = 'var(--color-text-secondary)'

export function ContextMeter({ info }: { info: ContextEvent | null }) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLSpanElement | null>(null)

  // 无数据时关闭面板(模型切换/清空会话可能临时移除数据)
  useEffect(() => {
    if (!info && open) setOpen(false)
  }, [info, open])

  // 外点 / Escape 关闭(DSH 同款)
  useEffect(() => {
    if (!open || !info) return
    const onPointerDown = (e: PointerEvent) => {
      if (e.target instanceof Node && rootRef.current?.contains(e.target)) return
      setOpen(false)
    }
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open, info])

  if (!info) return null
  const { used_tokens, context_window, percent, breakdown } = info
  const reading = `${percent}%`
  // ≥90% 砖红预警,≥70% 琥珀提醒,其余品牌蓝
  const arcColor =
    percent >= 90 ? 'var(--color-error)' : percent >= 70 ? 'var(--color-warning)' : SYSTEM_COLOR

  const breakdownTotal =
    breakdown.system_tokens + breakdown.tools_tokens + breakdown.message_tokens
  const segments =
    breakdownTotal === 0
      ? [{ key: 'total', color: arcColor, width: percent }]
      : (
          [
            { key: 'system', color: SYSTEM_COLOR, width: (percent * breakdown.system_tokens) / breakdownTotal },
            { key: 'tools', color: TOOLS_COLOR, width: (percent * breakdown.tools_tokens) / breakdownTotal },
            { key: 'messages', color: MESSAGES_COLOR, width: (percent * breakdown.message_tokens) / breakdownTotal },
          ] as const
        ).filter((s) => s.width > 0)

  const rows = [
    { key: '系统提示与工具', color: SYSTEM_COLOR, tokens: breakdown.system_tokens },
    { key: '工具调用与结果', color: TOOLS_COLOR, tokens: breakdown.tools_tokens },
    { key: '对话消息', color: MESSAGES_COLOR, tokens: breakdown.message_tokens },
  ]

  return (
    <span ref={rootRef} className="relative inline-flex">
      <button
        type="button"
        title={`上下文已用 ${reading}（${formatTokens(used_tokens)} / ${formatTokens(context_window)}）`}
        aria-label={`上下文已用 ${reading}`}
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="cursor-pointer p-0.5 rounded-full hover:bg-surface-muted transition-colors"
      >
        <svg viewBox="0 0 14 14" width="14" height="14" aria-hidden>
          <circle cx="7" cy="7" r={RADIUS} fill="none" stroke="var(--color-border-strong)" strokeWidth="2" />
          <circle
            cx="7"
            cy="7"
            r={RADIUS}
            fill="none"
            stroke={arcColor}
            strokeWidth="2"
            strokeLinecap="round"
            strokeDasharray={`${CIRCUMFERENCE * (percent / 100)} ${CIRCUMFERENCE}`}
            transform="rotate(-90 7 7)"
          />
        </svg>
      </button>
      {open && (
        <div
          role="dialog"
          aria-label={`上下文已用 ${reading}`}
          className="absolute bottom-full right-0 mb-2 w-60 rounded-[var(--radius-md)] bg-surface border border-border shadow-lg p-3 z-50"
        >
          <div className="flex items-baseline gap-1.5 mb-1.5">
            <span className="text-xs text-ink-secondary">上下文已用</span>
            <span className="text-sm font-semibold" style={{ color: arcColor }}>
              {reading}
            </span>
            <span className="ml-auto text-[11px] text-ink-muted font-mono">
              ~{formatTokens(used_tokens)} / {formatTokens(context_window)}
            </span>
          </div>
          <div className="flex h-1.5 rounded-full overflow-hidden bg-surface-muted mb-2">
            {segments.map((s) => (
              <div key={s.key} style={{ width: `${s.width}%`, background: s.color }} />
            ))}
          </div>
          <dl className="space-y-1">
            {rows.map((r) => (
              <div key={r.key} className="flex items-center gap-2 text-[11px] text-ink-secondary">
                <span className="w-2 h-2 rounded-full shrink-0" style={{ background: r.color }} />
                <dt className="flex-1">{r.key}</dt>
                <dd className="font-mono text-ink-muted">~{formatTokens(r.tokens)}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </span>
  )
}

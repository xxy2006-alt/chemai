import { useEffect, useRef, useState } from 'react'
import { FileUp, ChevronDown, ChevronRight, FlaskConical } from 'lucide-react'
import { ThinkingOrb, type OrbState } from 'thinking-orbs'
import { reorganizeQuestionImages } from '../../lib/exam-utils'
import { ChemMd } from '../ChemMd'
import { ToolCard, type ToolCardData } from './ToolCard'
import { ApprovalCard, type ApprovalData, type GateDecision } from './ApprovalCard'
import { InlinePanel } from './InlinePanels'
import type { PlanStepStatus } from '../../lib/agent-stream-reducer'

export type ChatItem =
  | { id: string; kind: 'user'; text: string }
  | { id: string; kind: 'ai'; text: string; streaming?: boolean }
  | { id: string; kind: 'think'; text: string; streaming?: boolean }
  | { id: string; kind: 'tool'; card: ToolCardData }
  | { id: string; kind: 'approval'; approval: ApprovalData }
  | {
      id: string
      kind: 'upload'
      file_name: string
      preview: string
      upload_id: string
      actions: { id: string; label: string }[]
    }
  | { id: string; kind: 'panel'; component: string; params: Record<string, unknown> }
  | {
      id: string
      kind: 'plan'
      plan: {
        goal: string
        total_steps: number
        steps: { step: number; skill: string; description: string; status: PlanStepStatus }[]
      }
    }
  | { id: string; kind: 'system'; text: string }

/** AI 气泡：思考状态显示在气泡内（原位置），文本经 KaTeX/Markdown 渲染。
 * orb 为 thinking-orbs 动画状态（breathing=思考 / working=执行 / composing=回复）。 */
export function AiBubble({
  text,
  streaming,
  phase = '',
  orb = '',
  elapsed,
}: {
  text: string
  streaming?: boolean
  phase?: string
  orb?: OrbState | ''
  elapsed?: number
}) {
  return (
    <div className="shrink-0 flex gap-2.5 max-w-[85%] self-start">
      {/* AI 头像（v2：品牌青烧杯 tile，替代棋盘格位图） */}
      <div className="w-8 h-8 rounded-[var(--radius-md)] bg-teal-soft flex items-center justify-center shrink-0 mt-1 border border-border">
        <FlaskConical size={15} className="text-teal" aria-hidden />
      </div>
      <div className="bg-surface border border-border rounded-[var(--radius-lg)] rounded-tl-[4px] px-4 py-3 shadow-[var(--shadow-sm)] min-w-[120px]">
        {streaming && phase ? (
          /* 执行中状态行：thinking-orbs 动画 + 当前活动 + 计时（DSH 式，2026-08） */
          <div className="flex items-center gap-2 text-[13px] text-teal mb-1.5">
            {orb ? <ThinkingOrb state={orb} size={20} aria-label={phase} /> : null}
            <span>{phase}</span>
            {elapsed !== undefined && (
              <span className="live-timer ticking text-[11px] text-ink-muted chem-mono">
                {elapsed.toFixed(1)}s
              </span>
            )}
          </div>
        ) : null}
        {text ? (
          /* AI 回复中的真题配图按"题干后"位置整理（OCR 数据配图常在解析之后） */
          <ChemMd text={reorganizeQuestionImages(text)} />
        ) : streaming && !phase ? (
          <div className="flex gap-1.5 py-1.5">
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className="w-1.5 h-1.5 rounded-full bg-teal animate-bounce"
                style={{ animationDelay: `${i * 0.15}s` }}
              />
            ))}
          </div>
        ) : null}
      </div>
    </div>
  )
}

function UserBubble({ text }: { text: string }) {
  return (
    <div className="shrink-0 max-w-[75%] self-end bg-primary text-white rounded-[var(--radius-lg)] rounded-br-[4px] px-4 py-2.5 text-[14px] leading-relaxed whitespace-pre-wrap shadow-[var(--shadow-sm)]">
      {text}
    </div>
  )
}

function UploadCard({ item }: { item: Extract<ChatItem, { kind: 'upload' }> }) {
  return (
    <div className="shrink-0 self-start max-w-[92%] bg-surface border border-teal/25 rounded-[var(--radius-md)] p-3.5 animate-fade-in-up">
      <div className="flex items-center gap-2 text-[13px] font-semibold text-ink">
        <FileUp size={15} className="text-teal" />
        {item.file_name}
      </div>
      {item.preview && (
        <p className="mt-1.5 text-xs text-ink-secondary m-0 line-clamp-3">{item.preview}</p>
      )}
      <div className="flex gap-2 mt-2.5">
        {item.actions.map((a) => (
          <button
            key={a.id}
            onClick={() => {
              const labels: Record<string, string> = { import: '导入题库', grade: '批改判卷', search: '搜题解析' }
              const prompt = `${labels[a.id] || a.label} [upload_id=${item.upload_id}]`
              window.dispatchEvent(new CustomEvent('chemai:send', { detail: prompt }))
            }}
            className="px-3 py-1.5 rounded-[var(--radius-sm)] border border-border text-xs text-ink-secondary hover:border-teal hover:text-teal transition-colors cursor-pointer"
          >
            {a.label}
          </button>
        ))}
      </div>
    </div>
  )
}

/** 任务计划卡（Spec 06 + ADR-0013）：步骤列表 + 状态（等待/执行中/等待确认/修订中/完成/失败/已放弃）+ 执行中实时计时 */
function PlanCard({ plan, elapsed }: { plan: Extract<ChatItem, { kind: 'plan' }>['plan']; elapsed?: number }) {
  const icons = {
    pending: '○',
    running: '◐',
    awaiting_confirmation: '⏸',
    revising: '✎',
    completed: '✓',
    failed: '✕',
    cancelled: '⊘',
    unknown: '?',
  } as const
  const colors = {
    pending: 'text-ink-muted border-border',
    running: 'text-teal border-teal',
    awaiting_confirmation: 'text-warning border-warning',
    revising: 'text-amber-600 border-amber-500',
    completed: 'text-success border-success',
    failed: 'text-error border-error',
    cancelled: 'text-ink-muted border-border',
    unknown: 'text-ink-muted border-border bg-surface-muted/60',
  } as const
  const labels = {
    pending: '等待中',
    running: '执行中…',
    awaiting_confirmation: '等待确认',
    revising: '修订中',
    completed: '完成',
    failed: '失败',
    cancelled: '已放弃',
    unknown: '未知',
  } as const
  const runningStep = plan.steps.find((s) => s.status === 'running')
  const failedStep = plan.steps.find((s) => s.status === 'failed')
  const gateStep = plan.steps.find((s) => s.status === 'awaiting_confirmation')
  const revisingStep = plan.steps.find((s) => s.status === 'revising')
  return (
    <div className="shrink-0 self-start max-w-[92%] bg-surface border border-border rounded-[var(--radius-md)] shadow-[var(--shadow-sm)] overflow-hidden animate-fade-in-up">
      <div className="px-3.5 py-2.5 border-b border-border/60 flex items-center gap-2">
        <span className="text-[13px] font-semibold text-ink">📋 {plan.goal || '执行计划'}</span>
        <span className="text-[11px] text-ink-muted chem-mono ml-auto">{plan.total_steps} 步</span>
      </div>
      {/* 执行中状态行（DSH「Deep diving… 24秒」同款，2026-08） */}
      {runningStep && (
        <div className="px-3.5 py-1.5 bg-teal-soft/40 border-b border-teal/15 flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-teal animate-pulse shrink-0" />
          <span className="text-[12px] text-teal font-medium">
            正在执行第 {runningStep.step} 步：{runningStep.description}
          </span>
          {elapsed !== undefined && (
            <span className="live-timer ticking text-[11px] text-ink-muted chem-mono ml-auto">
              {elapsed.toFixed(1)}s
            </span>
          )}
        </div>
      )}
      {/* 等待确认 / 修订中状态行（ADR-0013 确认门循环）。
       * 门开着时无条件显示——不允许被残留的 running 步骤遮住（issue #18 阶段 4） */}
      {gateStep && (
        <div className="px-3.5 py-1.5 bg-warning-soft border-b border-warning/15 flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-warning shrink-0 animate-pulse" />
          <span className="text-[12px] text-warning font-medium">
            第 {gateStep.step} 步等待确认：{gateStep.description}
          </span>
        </div>
      )}
      {revisingStep && !runningStep && (
        <div className="px-3.5 py-1.5 bg-amber-50 border-b border-amber-200/50 flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0 animate-pulse" />
          <span className="text-[12px] text-amber-600 font-medium">
            第 {revisingStep.step} 步按意见修订中
          </span>
        </div>
      )}
      {/* 失败状态行（2026-08 卡死治理：步骤失败显式展示，不再永远"执行中"） */}
      {failedStep && !runningStep && (
        <div className="px-3.5 py-1.5 bg-error-soft/30 border-b border-error/15 flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-error shrink-0" />
          <span className="text-[12px] text-error font-medium">
            第 {failedStep.step} 步执行失败：{failedStep.description}
          </span>
        </div>
      )}
      {/* 全部完成状态行（2026-09-21 架构审查 B：纯推导——无待办/执行中/门挂起
          且至少一步完成即整单完成；此前最后一步打勾后卡片无终态提示，
          老师看不出任务已收尾） */}
      {!runningStep && !failedStep && !gateStep && !revisingStep &&
        plan.steps.length > 0 &&
        plan.steps.every((s) => s.status === 'completed' || s.status === 'cancelled') &&
        plan.steps.some((s) => s.status === 'completed') && (
        <div className="px-3.5 py-1.5 bg-success-soft/30 border-b border-success/15 flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-success shrink-0" />
          <span className="text-[12px] text-success font-medium">
            任务已全部完成（{plan.steps.filter((s) => s.status === 'completed').length}/{plan.total_steps} 步）
          </span>
        </div>
      )}
      <div className="px-3.5 py-2.5 space-y-1.5">
        {plan.steps.map((s) => (
          <div key={s.step} className="flex items-center gap-2.5 text-[13px]">
            <span
              className={`w-5 h-5 rounded-full border flex items-center justify-center text-[11px] shrink-0 ${colors[s.status]}`}
            >
              {icons[s.status]}
            </span>
            <span className="flex-1 text-ink-secondary truncate">
              {s.step}. {s.description}
            </span>
            <span className="text-[11px] text-ink-muted shrink-0">{labels[s.status]}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

/** 思考行（DSH 式，2026-08）：工具调用前的推理文本折叠为一行，点击展开全文。
 * 流式时摘要跟随最新一行，静止时显示首行。 */
export function ThinkRow({ text, streaming }: { text: string; streaming?: boolean }) {
  const [open, setOpen] = useState(false)
  const firstLine = text.split('\n')[0] || text
  const latestLine = text.trimEnd().split('\n').pop() || ''
  return (
    <div className="shrink-0 self-start w-full max-w-[92%]">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-3 py-1.5 rounded-[var(--radius-md)] hover:bg-surface-muted/60 transition-colors cursor-pointer text-left"
        aria-expanded={open}
      >
        <span className="w-[18px] h-[18px] rounded-full border border-border flex items-center justify-center text-[10px] text-ink-muted shrink-0">
          ⊗
        </span>
        <span className="text-[12px] font-medium text-ink-muted shrink-0">思考</span>
        <span className="h-3 w-px bg-border shrink-0" />
        <span className="flex-1 truncate text-[12px] text-ink-muted">
          {streaming ? latestLine : firstLine}
        </span>
        {open ? (
          <ChevronDown size={13} className="text-ink-muted shrink-0" />
        ) : (
          <ChevronRight size={13} className="text-ink-muted shrink-0" />
        )}
      </button>
      {open && (
        <div className="mt-1 ml-2.5 pl-3 border-l-2 border-border text-[12px] text-ink-secondary whitespace-pre-wrap">
          {text}
        </div>
      )}
    </div>
  )
}

/** 消息列表：用户气泡 / AI 气泡 / 思考行 / 工具卡片 / 审批卡 / 上传卡 / 内联面板 / 系统提示 */
export function MessageList({
  items,
  phase,
  orb = '',
  streaming,
  elapsed,
  onApproval,
}: {
  items: ChatItem[]
  phase?: string
  orb?: OrbState | ''
  streaming?: boolean
  elapsed?: number
  onApproval: (decision: GateDecision, feedback?: string, draftId?: string, gateId?: string) => void
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const last = items[items.length - 1]
    if (last?.kind === 'panel') {
      // 面板类消息：滚动到面板顶部（而非列表底部，否则只能看到面板尾部）
      const el = containerRef.current?.querySelector(`[data-panel="${last.id}"]`)
      el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      return
    }
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [items])

  return (
    <div ref={containerRef} className="flex-1 overflow-y-auto min-h-0 px-4 py-5 flex flex-col gap-3">
      {items.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center text-center px-6">
          <div className="w-[300px] max-w-full mb-4 mx-auto flex items-center justify-center aspect-[16/9] rounded-[var(--radius-lg)] bg-surface-muted border border-dashed border-border-strong">
            <FlaskConical size={44} className="text-ink-muted/70" aria-hidden />
          </div>
          <h2 className="text-lg font-semibold text-ink m-0">你好，老师</h2>
          <p className="mt-1.5 text-[13px] text-ink-secondary max-w-md">
            我能帮你：配平化学方程式 · 生成练习题 · 诊断学习障碍 · 搜索历年真题 · 模拟化学实验 · 生成学习报告
          </p>
        </div>
      ) : (
        items.map((item) => {
          switch (item.kind) {
            case 'user':
              return <UserBubble key={item.id} text={item.text} />
            case 'ai':
              return <AiBubble key={item.id} text={item.text} streaming={item.streaming} phase={phase} orb={orb} elapsed={elapsed} />
            case 'think':
              return <ThinkRow key={item.id} text={item.text} streaming={item.streaming} />
            case 'tool':
              return <ToolCard key={item.id} card={item.card} />
            case 'approval':
              return (
                <ApprovalCard
                  key={item.id}
                  approval={item.approval}
                  disabled={streaming}
                  onResolve={(decision, feedback) =>
                    onApproval(decision, feedback, item.approval.draft_id, item.approval.gate_id)
                  }
                />
              )
            case 'upload':
              return <UploadCard key={item.id} item={item} />
            case 'panel':
              return <InlinePanel key={item.id} panelId={item.id} component={item.component} params={item.params} />
            case 'plan':
              return <PlanCard key={item.id} plan={item.plan} elapsed={elapsed} />
            case 'system':
              return (
                <div key={item.id} className="shrink-0 self-center text-xs text-ink-muted bg-surface-muted/60 rounded-full px-3.5 py-1.5">
                  {item.text}
                </div>
              )
          }
        })
      )}
      {/* 工具执行阶段（无 AI 气泡）的状态行：AI 气泡被折叠成工具卡后 phase
       * 无处显示（2026-08：v2 后端只发 thinking/reply，工具执行中最长的
       * 一段必须持续可见——「执行中：搜索真题」+ thinking-orbs + 计时） */}
      {streaming && phase && !items.some((it) => it.kind === 'ai' && it.streaming) && (
        <div className="shrink-0 self-start flex items-center gap-2 text-[13px] text-teal">
          {orb ? <ThinkingOrb state={orb} size={20} aria-label={phase} /> : null}
          <span>{phase}</span>
          {elapsed !== undefined && (
            <span className="live-timer ticking text-[11px] text-ink-muted chem-mono">
              {elapsed.toFixed(1)}s
            </span>
          )}
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  )
}

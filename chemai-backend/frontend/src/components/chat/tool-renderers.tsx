/* tool-renderers.tsx — js/agent-renderers.js 的 React 移植
 * 工具结果富渲染：题目卡片 / 搜索 / 障碍分布 / 学习计划 / 配平 / 实验 / 表格等 */

import type { ReactNode } from 'react'
import { FlaskConical } from 'lucide-react'
import { Tag } from '../ui'
import { QuestionMd } from '../QuestionMd'
import { AnswerMd } from '../AnswerMd'
import { OptionsRow } from '../OptionsRow'
import { filterExamImages, type ExamImageEntry } from '../../lib/exam-utils'

/* ── 通用小件 ── */

function MiniStat({ value, label, color }: { value: ReactNode; label: string; color?: string }) {
  return (
    <div className="flex-1 min-w-[72px] text-center">
      <div className={`text-xl font-semibold leading-none ${color ?? 'text-ink'}`}>{value}</div>
      <div className="mt-1 text-[11px] text-ink-muted">{label}</div>
    </div>
  )
}

/* ── 题目卡片 ── */

export interface QuestionItem {
  content?: string
  options?: string[] | string
  answer?: string
  difficulty?: string
  knowledge_points?: string[]
  analysis?: string
  overall_status?: 'passed' | 'warning' | 'blocked' | string
}

export function QuestionCards({ data }: { data: Record<string, unknown> | QuestionItem[] }) {
  const qs: QuestionItem[] = Array.isArray(data) ? data : ((data.questions as QuestionItem[]) || [])
  if (!qs.length) return <p className="text-sm text-ink-muted m-0">暂无题目</p>
  return (
    <div className="space-y-2">
      {qs.map((q, i) => {
        const status = q.overall_status || 'passed'
        const label = { passed: '✓ 通过', warning: '⚠ 需确认', blocked: '✗ 拦截' }[status] || status
        const tone = status === 'blocked' ? 'red' : status === 'warning' ? 'amber' : 'green'
        return (
          <div
            key={i}
            className="bg-surface border border-border rounded-[var(--radius-md)] p-3.5 shadow-[var(--shadow-sm)] animate-fade-in-up"
            style={{ animationDelay: `${i * 0.05}s` }}
          >
            <div className="flex items-center gap-2 mb-1.5">
              <Tag tone={tone as 'green'} size="sm">
                {label}
              </Tag>
              <span className="text-[13px] font-semibold text-ink">#{i + 1}</span>
            </div>
            <QuestionMd text={q.content || ''} />
            <OptionsRow options={q.options} className="mt-1" />
            <div className="flex items-center gap-2 mt-2 flex-wrap">
              <AnswerMd text={q.answer || ''} />
              {q.difficulty && (
                <Tag
                  tone={q.difficulty === 'hard' ? 'red' : q.difficulty === 'easy' ? 'teal' : 'blue'}
                  size="sm"
                >
                  {q.difficulty}
                </Tag>
              )}
            </div>
            {q.analysis && <p className="text-xs text-ink-secondary mt-2 m-0">{q.analysis}</p>}
            {(q.knowledge_points?.length ?? 0) > 0 && (
              <div className="flex gap-1.5 flex-wrap mt-2">
                {q.knowledge_points!.map((k) => (
                  <Tag key={k} tone="gray" size="sm">
                    {k}
                  </Tag>
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

/* ── 搜索结果 ── */

export function SearchResults({ data }: { data: Record<string, unknown> }) {
  const text = String(data.text || data.raw || '')
  const qs = (data.questions as Record<string, unknown>[]) || (Array.isArray(data) ? data : [])
  const total = (data.total as number) || qs.length
  // 题目附图（exam_images 事件）：正文已内联展示的图不重复显示
  const images = filterExamImages(text, data.images as unknown[])
  if (!qs.length && !images.length)
    return <p className="text-sm text-ink-muted m-0">题库中暂无匹配结果</p>
  return (
    <div>
      {qs.length > 0 && (
        <>
          <div className="text-xs text-ink-muted mb-1.5">找到 {total} 道真题</div>
          <div className="space-y-2">
            {qs.slice(0, 5).map((q, i) => (
              <div key={i} className="bg-surface border border-border rounded-[var(--radius-md)] p-3 text-[13px]">
                <span className="font-semibold text-ink">
                  {String(q.source || '')} · {String(q.year || '')}
                </span>
                <div className="my-1.5">
                  <QuestionMd text={String(q.content || '')} />
                </div>
                <AnswerMd text={String(q.answer || '')} />
              </div>
            ))}
          </div>
          {qs.length > 5 && (
            <div className="text-xs text-ink-muted text-center mt-2">…还有 {qs.length - 5} 题</div>
          )}
        </>
      )}
      {images.length > 0 && (
        <div className={qs.length > 0 ? 'mt-3 border-t border-border/60 pt-2.5' : ''}>
          {qs.length === 0 && (
            <div className="text-xs text-ink-muted mb-1.5">真题已在上方列出，以下为题目附图</div>
          )}
          {images.map((img: ExamImageEntry, i) => (
            <div key={i} className="mb-2.5">
              {img.title && <div className="text-xs text-ink-secondary mb-1">{img.title}</div>}
              <div className="flex flex-wrap gap-2">
                {(img.urls || []).map((u) => (
                  <img
                    key={u}
                    src={u}
                    alt={img.title || '题目附图'}
                    className="max-h-[140px] max-w-[220px] object-contain rounded-[var(--radius-sm)] border border-border bg-white"
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/* ── 障碍分布 ── */

/** 学生诊断结果（diagnose_barrier 学生场景）：
 * 旧版 renderDiagnosis 行为恢复——图形化障碍条 + 成绩趋势 + 薄弱知识点表格 +
 * 「针对障碍出题练习」按钮（2026-08-14 用户反馈：以前能看到渲染的图和表格） */
export function StudentBarrierResult({ data }: { data: Record<string, unknown> }) {
  const barrier = (data.barrier_distribution as Record<string, number> | undefined) || {}
  const dominant = String(data.dominant_barrier || '')
  const barrierLabels: Record<string, string> = {
    concept: '概念理解',
    reading: '审题仔细',
    expression: '答题表述',
  }
  const barrierColors: Record<string, string> = {
    concept: 'bg-primary',
    reading: 'bg-teal',
    expression: 'bg-success',
  }
  const weak = (data.weak_knowledge_points as { name?: string; errors?: number }[] | undefined) || []
  const trend = (data.score_trend as { date?: string; cumulative_rate?: number }[] | undefined) || []
  const acc = Number(data.accuracy || 0)
  const total = Number(data.total_answers || 0)
  const correct = Number(data.correct_answers || 0)

  return (
    <div className="text-[13px]">
      <div className="flex gap-2.5 flex-wrap mb-3">
        <div className="flex-1 min-w-[72px] bg-surface-muted rounded-[var(--radius-md)] py-2.5 text-center">
          <div className="text-lg font-semibold text-ink">{Number(data.exercises_completed || 0)}</div>
          <div className="text-[11px] text-ink-muted mt-0.5">完成练习</div>
        </div>
        <div className="flex-1 min-w-[72px] bg-surface-muted rounded-[var(--radius-md)] py-2.5 text-center">
          <div className="text-lg font-semibold text-ink">{total ? `${correct}/${total}` : '—'}</div>
          <div className="text-[11px] text-ink-muted mt-0.5">作答/正确</div>
        </div>
        <div className="flex-1 min-w-[72px] bg-surface-muted rounded-[var(--radius-md)] py-2.5 text-center">
          <div className={`text-lg font-semibold ${acc >= 0.7 ? 'text-success' : acc >= 0.5 ? 'text-primary' : 'text-error'}`}>
            {Math.round(acc * 100)}%
          </div>
          <div className="text-[11px] text-ink-muted mt-0.5">正确率</div>
        </div>
      </div>

      {/* 障碍分布条（图） */}
      {Object.keys(barrier).length > 0 && (
        <div className="mb-3">
          {(['concept', 'reading', 'expression'] as const).map((k) => {
            const val = barrier[k] || 0
            return (
              <div key={k} className="flex items-center gap-2.5 mb-1.5">
                <span className="text-xs text-ink-secondary w-[60px] shrink-0">{barrierLabels[k]}</span>
                <div className="flex-1 h-2.5 rounded-full bg-surface-muted overflow-hidden">
                  <div
                    className={`h-full rounded-full ${barrierColors[k]} transition-all duration-500`}
                    style={{ width: `${Math.round(val * 100)}%` }}
                  />
                </div>
                <span className="text-xs text-ink-secondary chem-mono w-[38px] text-right">
                  {Math.round(val * 100)}%
                </span>
              </div>
            )
          })}
          {dominant && (
            <div className="text-[11px] text-ink-muted mt-1">
              主导障碍：<span className="text-warning">{barrierLabels[dominant] || dominant}</span>
            </div>
          )}
        </div>
      )}

      {/* 成绩趋势（图） */}
      {trend.length >= 2 && (
        <div className="mb-3">
          <div className="text-xs font-semibold text-ink-secondary mb-1.5">成绩趋势</div>
          <div className="flex items-end gap-[3px] h-[56px] px-1">
            {trend.map((t, i) => (
              <div key={i} className="flex-1 flex flex-col items-center justify-end gap-1 min-w-0">
                <div
                  className="w-full rounded-t-[3px] bg-teal/70"
                  style={{ height: `${Math.max(Math.round((t.cumulative_rate || 0) * 100) * 0.5, 2)}px` }}
                  title={`${t.date || ''} ${Math.round((t.cumulative_rate || 0) * 100)}%`}
                />
              </div>
            ))}
          </div>
          <div className="flex justify-between mt-1 text-[10px] text-ink-muted">
            <span>{trend[0]?.date || ''}</span>
            <span>{trend[trend.length - 1]?.date || ''}</span>
          </div>
        </div>
      )}

      {/* 薄弱知识点（表格） */}
      {weak.length > 0 && (
        <div className="mb-3">
          <div className="text-xs font-semibold text-ink-secondary mb-1.5">薄弱知识点</div>
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr>
                <th className="text-left font-medium text-ink-muted py-1 border-b border-border">知识点</th>
                <th className="text-right font-medium text-ink-muted py-1 border-b border-border w-[64px]">错误次数</th>
              </tr>
            </thead>
            <tbody>
              {weak.map((k, i) => (
                <tr key={i} className="border-b border-border/60">
                  <td className="py-1.5 text-ink">{String(k.name || '')}</td>
                  <td className="py-1.5 text-right">
                    <span className="px-1.5 py-0.5 rounded-[var(--radius-sm)] bg-error-soft text-error text-[11px]">
                      {Number(k.errors || 0)} 次
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 旧版 _diagToExam 行为：针对障碍出题练习 */}
      <button
        onClick={() =>
          window.dispatchEvent(
            new CustomEvent('chemai:send', {
              detail: `针对${String(data.student_name || '')}的学习障碍出题练习`,
            }),
          )
        }
        className="w-full flex items-center justify-center gap-1.5 px-3 py-2 rounded-[var(--radius-md)] border border-teal/30 bg-teal-soft/40 text-teal text-[13px] font-medium hover:bg-teal-soft transition-colors cursor-pointer"
      >
        <FlaskConical size={13} />
        针对障碍出题练习
      </button>
    </div>
  )
}

export function BarrierOverview({ data }: { data: Record<string, unknown> }) {
  const dist = (data.class_barrier_distribution || {}) as Record<string, number>
  const concept = dist.concept || 0
  const reading = dist.reading || 0
  const expression = dist.expression || 0
  const maxVal = Math.max(concept, reading, expression, 1)
  const students = (data.students || []) as Record<string, unknown>[]
  const avgMastery = (data.avg_mastery as number) || 0

  const bars = [
    { label: '概念理解', val: concept, color: 'bg-primary' },
    { label: '审题障碍', val: reading, color: 'bg-teal' },
    { label: '表述障碍', val: expression, color: 'bg-success' },
  ]

  return (
    <div>
      <div className="flex items-end gap-5 h-[140px] px-1 py-2">
        {bars.map((b) => (
          <div key={b.label} className="flex-1 flex flex-col items-center gap-1.5">
            <span className="font-bold text-base text-ink">{b.val}</span>
            <div className="flex-1 w-full max-w-[60px] bg-surface-muted rounded-t-[6px] relative overflow-hidden">
              <div
                className={`absolute bottom-0 w-full rounded-t-[6px] transition-all duration-500 ${b.color}`}
                style={{ height: `${Math.max(Math.round((b.val / maxVal) * 100), 4)}%` }}
              />
            </div>
            <span className="text-[11px] text-ink-secondary">{b.label}</span>
          </div>
        ))}
      </div>
      <div className="flex gap-2.5 mt-3">
        <div className="flex-1 bg-surface-muted rounded-[var(--radius-md)] py-2.5 text-center">
          <span className="text-lg font-bold text-ink">{Math.round(avgMastery * 100)}%</span>
          <p className="text-[11px] text-ink-muted m-0">掌握度</p>
        </div>
        <div className="flex-1 bg-surface-muted rounded-[var(--radius-md)] py-2.5 text-center">
          <span className="text-lg font-bold text-ink">{students.length}</span>
          <p className="text-[11px] text-ink-muted m-0">诊断学生</p>
        </div>
      </div>
      {students.length > 0 && (
        <div className="mt-3">
          <div className="text-xs font-semibold text-ink mb-1.5">需关注学生</div>
          {[...students]
            .sort(
              (a, b) =>
                ((b.barrier_type as Record<string, number>)?.[String(b.dominant_barrier)] || 0) -
                ((a.barrier_type as Record<string, number>)?.[String(a.dominant_barrier)] || 0),
            )
            .slice(0, 5)
            .map((s, i) => {
              const dom = String(s.dominant_barrier || '')
              const names: Record<string, string> = { concept: '概念', reading: '审题', expression: '表述' }
              return (
                <div
                  key={i}
                  className="flex items-center gap-2.5 px-3 py-2 mt-1.5 border border-border rounded-[var(--radius-sm)] text-[13px]"
                >
                  <span className="font-medium text-ink">{String(s.student_name)}</span>
                  <Tag tone="amber" size="sm">
                    {names[dom] || dom}{' '}
                    {Math.round(((s.barrier_type as Record<string, number>)?.[dom] || 0) * 100)}%
                  </Tag>
                  <span className="text-[11px] text-ink-muted">
                    {(s.weak_knowledge_points as unknown[])?.length ?? 0} 弱知识点
                  </span>
                </div>
              )
            })}
        </div>
      )}
    </div>
  )
}

/* ── 学习计划 ── */

export function LearningPlan({ data }: { data: Record<string, unknown> }) {
  const plan = (data.plan_data || data.plan || data) as Record<string, unknown>
  const studentName = String(data.student_name || '')
  const title = String(plan.plan_title || '个性化学习计划')
  const period = String(plan.plan_period || '')
  const tasks = (plan.daily_tasks || []) as Record<string, unknown>[]
  const weeks = (plan.weekly_goals || []) as (string | Record<string, unknown>)[]
  const barriers = plan.barrier_interventions as Record<string, unknown> | unknown[]
  const tips = (plan.motivation_tips || []) as (string | Record<string, unknown>)[]

  return (
    <div className="border-l-4 border-success rounded-r-[var(--radius-md)] bg-success-soft/50 p-3.5">
      <div className="font-bold text-[15px] text-success">{title}</div>
      {studentName && (
        <div className="text-xs text-ink-secondary mt-1">
          学生: {studentName}
          {period ? ` · 周期: ${period}` : ''}
        </div>
      )}
      {weeks.length > 0 && (
        <div className="mt-2.5">
          <div className="text-xs font-semibold text-ink-secondary mb-1">🎯 周目标</div>
          {weeks.map((w, i) => {
            const goal = typeof w === 'string' ? w : String(w.milestone || w.goal || w.text || '')
            const wk = typeof w === 'string' ? '' : String(w.week || w.label || '')
            return (
              <div key={i} className="text-xs text-ink-secondary py-0.5">
                {wk ? <b className="text-ink">{wk}</b> : null}
                {wk ? ': ' : ''}
                {goal}
              </div>
            )
          })}
        </div>
      )}
      {tasks.length > 0 && (
        <div className="mt-2">
          <div className="text-xs font-semibold text-ink-secondary mb-1">📅 每日任务</div>
          {tasks.slice(0, 14).map((t, i) => (
            <div key={i} className="flex gap-2 text-xs text-ink-secondary py-0.5">
              <span className="chem-mono text-[11px] text-success min-w-[50px]">{String(t.day || '')}</span>
              <span>{String(t.task || t.content || '')}</span>
            </div>
          ))}
        </div>
      )}
      {!Array.isArray(barriers) && barriers && typeof barriers === 'object' && Object.keys(barriers).length > 0 && (
        <div className="mt-2">
          <div className="text-xs font-semibold text-ink-secondary mb-1">🧠 障碍干预</div>
          {Object.entries(barriers as Record<string, unknown>).map(([bt, v]) => (
            <div key={bt} className="flex gap-2 text-xs py-0.5">
              <span className="chem-mono text-[11px] text-warning min-w-[60px]">
                {{ concept: '概念理解', reading: '审题仔细', expression: '答题表述' }[bt] || bt}
              </span>
              <span className="text-ink-secondary">{String(v)}</span>
            </div>
          ))}
        </div>
      )}
      {tips.length > 0 && (
        <div className="flex gap-1.5 flex-wrap mt-2">
          {tips.map((m, i) => {
            const t = typeof m === 'string' ? m : String(m.tip || m.text || '')
            return (
              <Tag key={i} tone="teal" size="sm">
                {t}
              </Tag>
            )
          })}
        </div>
      )}
    </div>
  )
}

/* ── 配平结果 ── */

export function BalanceResult({ data }: { data: Record<string, unknown> }) {
  if (data.error) return <ErrorBox message={String(data.error)} />
  const status = String(data.overall_status || 'unknown')
  const labels: Record<string, string> = {
    passed: '✓ 配平正确',
    warning: '⚠ 需确认',
    blocked: '✗ 配平错误',
    error: '✗ 解析失败',
  }
  const tones: Record<string, 'green' | 'amber' | 'red' | 'gray'> = {
    passed: 'green',
    warning: 'amber',
    blocked: 'red',
    error: 'red',
  }
  const balance = (data.balance || []) as Record<string, unknown>[]
  return (
    <div>
      <Tag tone={tones[status] || 'gray'}>{labels[status] || status}</Tag>
      {data.equation ? <p className="chem-mono text-xs text-ink-muted mt-2 m-0">方程式: {String(data.equation)}</p> : null}
      {balance.length > 0 && (
        <table className="w-full mt-2.5 text-xs border-collapse">
          <thead>
            <tr>
              {['元素', '左侧原子数', '右侧原子数', '状态'].map((h) => (
                <th key={h} className="text-left font-medium text-ink-muted py-1.5 border-b border-border">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {balance.map((b, i) => {
              const ok = b.left_count === b.right_count
              return (
                <tr key={i} className="border-b border-border/60">
                  <td className="py-1.5 text-ink">{String(b.element)}</td>
                  <td className="py-1.5">{String(b.left_count)}</td>
                  <td className="py-1.5">{String(b.right_count)}</td>
                  <td className={`py-1.5 ${ok ? 'text-success' : 'text-error'}`}>
                    {ok ? '✓' : `✗ 差 ${Math.abs(Number(b.left_count) - Number(b.right_count))}`}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}

/* ── 模拟实验 ── */

export function Experiment({ data }: { data: Record<string, unknown> }) {
  if (data.error) return <ErrorBox message={String(data.error)} />
  const section = (label: string, items: unknown[], li?: (s: string) => ReactNode) => {
    if (!items?.length) return null
    return (
      <div className="mt-2">
        <div className="text-xs font-semibold text-ink-secondary mb-1">{label}</div>
        <ul className="m-0 pl-4 text-xs text-ink-secondary space-y-0.5">
          {items.map((x, i) => (
            <li key={i}>{li ? li(String(x)) : String(x)}</li>
          ))}
        </ul>
      </div>
    )
  }
  return (
    <div>
      {data.experiment_name ? <div className="font-semibold text-[15px] text-ink">{String(data.experiment_name)}</div> : null}
      {section('实验目的', data.objectives as unknown[])}
      {(data.equipment as unknown[])?.length ? (
        <div className="mt-2">
          <div className="text-xs font-semibold text-ink-secondary mb-1">仪器与药品</div>
          <div className="flex gap-1.5 flex-wrap">
            {(data.equipment as string[]).map((e, i) => (
              <Tag key={i} tone="gray" size="sm">
                {e}
              </Tag>
            ))}
          </div>
        </div>
      ) : null}
      {section('实验步骤', data.steps as unknown[])}
      {section('预期现象', data.expected_phenomena as unknown[])}
      {section('化学方程式', data.equations as unknown[], (s) => <span className="chem-mono">{s}</span>)}
      {(data.safety as unknown[])?.length ? (
        <div className="mt-2.5 px-3 py-2 bg-warning-soft rounded-[var(--radius-sm)] text-xs text-warning">
          <b>安全提醒</b>
          <ul className="m-1 pl-4 space-y-0.5">
            {(data.safety as string[]).map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {section('高考考点', data.exam_tips as unknown[], (s) => <span className="text-teal">{s}</span>)}
    </div>
  )
}

/* ── 其他简单渲染 ── */

function ErrorBox({ message }: { message: string }) {
  return <p className="text-sm text-error m-0">{message}</p>
}

/** show_* 面板类工具：展示返回的 message 文本（2026-08：不落 JSON fallback 乱码）
 *  2026-09-21：show_students 成功时返回 result/students 字段（无 message），
 *  此前只读 message → 查找成功的卡片渲染成空白。 */
export function ShowPanelResult({ data }: { data: Record<string, unknown> }) {
  const msg = String(data.message || data.result || '')
  if (msg) return <p className="text-sm text-ink-secondary m-0">{msg}</p>
  if (Array.isArray(data.students) && data.students.length > 0) {
    return (
      <ul className="text-sm text-ink-secondary m-0 pl-4 list-disc space-y-0.5">
        {(data.students as Array<Record<string, unknown>>).map((s, i) => (
          <li key={i}>
            {String(s.name ?? '')}
            {s.student_id ? <span className="text-ink-muted">（学号 {String(s.student_id)}）</span> : null}
            {s.class_name ? <span className="text-ink-muted"> · {String(s.class_name)}</span> : null}
          </li>
        ))}
      </ul>
    )
  }
  return null
}

export function TutorAnswer({ data }: { data: Record<string, unknown> }) {
  const answer = String(data.answer || '')
  if (!answer) return <p className="text-sm text-ink-muted m-0">暂无回复</p>
  return (
    <div>
      <div className="text-[13px] leading-relaxed whitespace-pre-wrap text-ink-secondary">{answer}</div>
      {data.model ? <div className="mt-1.5 text-[10px] text-ink-muted">模型: {String(data.model)}</div> : null}
    </div>
  )
}

export function WebSearchView({ data }: { data: Record<string, unknown> }) {
  if (data.error) return <ErrorBox message={`搜索异常: ${String(data.error)}`} />
  const result = String(data.result || data.content || '')
  if (!result) return <p className="text-sm text-ink-muted m-0">搜索完成，未获取到相关内容</p>
  return (
    <div className="text-[13px]">
      <div className="font-medium text-teal mb-1.5">已获取搜索结果 ({String(data.query || '')})</div>
      <div className="max-h-[200px] overflow-y-auto whitespace-pre-wrap text-xs text-ink-secondary">
        {result.slice(0, 2000)}
      </div>
    </div>
  )
}

export function ExamStats({ data }: { data: Record<string, unknown> }) {
  const students = (data.students || []) as Record<string, unknown>[]
  return (
    <div>
      <div className="flex gap-2.5 flex-wrap mb-3">
        <MiniStat value={Number(data.total_students || 0)} label="学生总数" />
        <MiniStat value={Number(data.completed_count || 0)} label="已完成" />
        <MiniStat value={Number(data.total_questions || 0)} label="题目数" color="text-success" />
        <MiniStat
          value={`${((data.class_avg_accuracy as number) || 0) * 100}%`}
          label="均分"
          color="text-error"
        />
      </div>
      {students.length > 0 && (
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr>
              {['#', '学生', '答题', '正确', '正确率', '得分'].map((h) => (
                <th key={h} className="text-left font-medium text-ink-muted py-1.5 border-b border-border">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {students.map((s, i) => {
              const acc = (s.accuracy as number) || 0
              return (
                <tr key={i} className="border-b border-border/60">
                  <td className="py-1.5">{i + 1}</td>
                  <td className="py-1.5 text-ink">{String(s.student_name)}</td>
                  <td className="py-1.5">
                    {String(s.answered)}/{Number(data.total_questions || 0)}
                  </td>
                  <td className="py-1.5">{String(s.correct)}</td>
                  <td className={`py-1.5 font-semibold ${acc >= 0.8 ? 'text-success' : acc >= 0.6 ? 'text-primary' : 'text-error'}`}>
                    {(acc * 100).toFixed(1)}%
                  </td>
                  <td className="py-1.5">{Number(s.score).toFixed(1)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}

export function OcrTableView({ data }: { data: Record<string, unknown> }) {
  const results = (data.results || (Array.isArray(data) ? data : [])) as Record<string, unknown>[]
  if (!results.length) return <p className="text-sm text-ink-muted m-0">无识别结果</p>
  const qNums: string[] = []
  const seen: Record<string, boolean> = {}
  results.forEach((r) => {
    Object.keys((r.answers || {}) as Record<string, unknown>).forEach((k) => {
      if (!seen[k]) {
        seen[k] = true
        qNums.push(k)
      }
    })
  })
  qNums.sort()
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr>
            <th className="text-left font-medium text-ink-muted py-1.5 border-b border-border">学号</th>
            <th className="text-left font-medium text-ink-muted py-1.5 border-b border-border">姓名</th>
            {qNums.map((q) => (
              <th key={q} className="text-left font-medium text-ink-muted py-1.5 border-b border-border">
                {q}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {results.map((r, i) => (
            <tr key={i} className="border-b border-border/60">
              <td className="chem-mono text-[11px] py-1.5">{String(r.student_id)}</td>
              <td className="py-1.5 text-ink">{String(r.student_name || '')}</td>
              {qNums.map((q) => {
                const a = ((r.answers || {}) as Record<string, Record<string, unknown>>)[q] || {}
                const conf = (a.confidence as number) || 0
                return (
                  <td key={q} className="py-1.5">
                    <span>{String(a.answer || '--')}</span>
                    <div className={`text-[10px] ${conf >= 0.85 ? 'text-success' : conf >= 0.6 ? 'text-warning' : 'text-error'}`}>
                      {Math.round(conf * 100)}%
                    </div>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function ImportResult({ data }: { data: Record<string, unknown> }) {
  if (data.error) return <ErrorBox message={String(data.error)} />
  return (
    <div>
      <div className="flex gap-2.5 flex-wrap mb-2">
        <MiniStat value={Number(data.extracted || 0)} label="提取题目" />
        <MiniStat value={Number(data.passed_audit || 0)} label="审核通过" color="text-success" />
        <MiniStat value={Number(data.saved || 0)} label="已入库" color="text-primary" />
      </div>
      {data.mineru_used !== undefined && (
        <p className="text-[11px] text-ink-muted m-0">MinerU: {data.mineru_used ? '✓' : '✗ 未启用'}</p>
      )}
      {data.needs_review ? (
        <p className="text-xs text-warning mt-1 m-0">⚠ {String(data.needs_review)} 题需人工复核</p>
      ) : null}
    </div>
  )
}

export function AssignResult({ data }: { data: Record<string, unknown> }) {
  if (data.error) return <ErrorBox message={String(data.error)} />
  const assigned = (data.assigned || []) as Record<string, unknown>[]
  const exists = data.status === 'exists' || assigned.some((a) => a.status === 'exists')
  return (
    <div>
      <Tag tone="green">
        {exists
          ? '该任务此前已布置，沿用原卷（未重复建卷）'
          : `已为 ${Number(data.assigned_count || 0)} 名学生布置练习`}
      </Tag>
      {assigned.length > 0 && (
        <table className="w-full mt-2.5 text-xs border-collapse">
          <thead>
            <tr>
              {['学生', '难度(ZPD)', '题数', '障碍类型'].map((h) => (
                <th key={h} className="text-left font-medium text-ink-muted py-1.5 border-b border-border">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {assigned.map((a, i) => (
              <tr key={i} className="border-b border-border/60">
                <td className="py-1.5 text-ink">{String(a.student_name)}</td>
                <td className="py-1.5">{String(a.zpd_difficulty || '')}</td>
                <td className="py-1.5">{String(a.question_count || 0)}</td>
                <td className="py-1.5">{String(a.barrier || '')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

export function WeeklyReport({ data }: { data: Record<string, unknown> }) {
  if (data.error) return <ErrorBox message={String(data.error)} />
  return (
    <div>
      {data.student_name ? (
        <div className="font-semibold text-[15px] text-ink mb-1">{String(data.student_name)} 的学习周报</div>
      ) : null}
      {data.exam_count !== undefined && <p className="text-xs text-ink-muted m-0 mb-2">本周参加 {String(data.exam_count)} 次练习</p>}
      {data.report ? (
        <div className="text-[13px] leading-relaxed whitespace-pre-wrap text-ink-secondary">{String(data.report)}</div>
      ) : null}
    </div>
  )
}

export function JsonFallback({ data }: { data: unknown }) {
  return (
    <pre className="chem-mono text-[11px] whitespace-pre-wrap max-h-[300px] overflow-y-auto text-ink-secondary m-0">
      {JSON.stringify(data, null, 2)}
    </pre>
  )
}

/* ── 文件/命令工具结果（DSH 式：内容直接可读，不落 JSON） ── */

export function FileReadResult({ data }: { data: Record<string, unknown> }) {
  if (data.error) return <ErrorBox message={String(data.error)} />
  // 工作区外按次审批：工具返回 approval_needed 时展示请求批准文案，
  // 而非「（空文件）」误导（2026-08 read 卡死修复配套）
  if (data.approval_needed)
    return (
      <div className="text-[13px] text-warning">
        ⏸ 等待批准：{String(data.message || '工作区外访问需要批准')}
        <div className="text-xs text-ink-muted mt-1 chem-mono">{String(data.target || '')}</div>
      </div>
    )
  const content = String(data.content || '')
  const raw = typeof data.raw === 'string' ? data.raw : ''
  const display = content || (raw ? `（结果解析失败，原始内容片段）\n${raw.slice(0, 600)}` : '')
  return (
    <div>
      <div className="text-xs text-ink-muted mb-1.5">
        {String(data.path || '')} · {String(data.total_lines ?? '?')} 行
        {data.truncated ? ' · 已分页截断' : ''}
      </div>
      <pre className="chem-mono text-[11px] whitespace-pre-wrap max-h-[240px] overflow-y-auto text-ink-secondary m-0 bg-surface-muted/40 rounded-[var(--radius-sm)] p-2.5">
        {display || '（空文件）'}
      </pre>
    </div>
  )
}

export function FileWriteResult({ data }: { data: Record<string, unknown> }) {
  if (data.error) return <ErrorBox message={String(data.error)} />
  return (
    <div className="text-[13px] text-ink-secondary">
      {data.edited !== undefined ? '✏️ 已编辑' : '📄 已写入'}：
      <span className="chem-mono text-xs">{String(data.path || '')}</span>
      {data.chars !== undefined && <> · {String(data.chars)} 字</>}
      {data.replacements !== undefined && <> · {String(data.replacements)} 处替换</>}
    </div>
  )
}

export function BashResult({ data }: { data: Record<string, unknown> }) {
  if (data.error) return <ErrorBox message={String(data.error)} />
  if (data.timed_out) return <ErrorBox message="命令超时已终止" />
  const stdout = String(data.stdout || '')
  const stderr = String(data.stderr || '')
  return (
    <div>
      {stdout && (
        <pre className="chem-mono text-[11px] whitespace-pre-wrap max-h-[240px] overflow-y-auto text-ink-secondary m-0 bg-surface-muted/40 rounded-[var(--radius-sm)] p-2.5">
          {stdout}
        </pre>
      )}
      {stderr && (
        <pre className="chem-mono text-[11px] whitespace-pre-wrap max-h-[120px] overflow-y-auto text-error m-0 mt-1.5 bg-error-soft/30 rounded-[var(--radius-sm)] p-2.5">
          {stderr}
        </pre>
      )}
      {data.truncated ? <div className="text-[11px] text-ink-muted mt-1">输出已截断</div> : null}
    </div>
  )
}

export function FindResult({ data }: { data: Record<string, unknown> }) {
  if (data.error) return <ErrorBox message={String(data.error)} />
  const matches = (data.matches || []) as string[]
  if (!matches.length) return <p className="text-sm text-ink-muted m-0">没有匹配的文件</p>
  return (
    <div>
      <div className="text-xs text-ink-muted mb-1">找到 {String(data.count ?? matches.length)} 个文件</div>
      <ul className="m-0 pl-4 text-xs text-ink-secondary space-y-0.5">
        {matches.slice(0, 30).map((m, i) => (
          <li key={i} className="chem-mono">{String(m)}</li>
        ))}
      </ul>
    </div>
  )
}

export function GrepResult({ data }: { data: Record<string, unknown> }) {
  if (data.error) return <ErrorBox message={String(data.error)} />
  const matches = (data.matches || []) as { file?: string; line?: number; text?: string }[]
  if (!matches.length) return <p className="text-sm text-ink-muted m-0">没有匹配内容</p>
  return (
    <div>
      <div className="text-xs text-ink-muted mb-1">{String(data.count ?? matches.length)} 处匹配</div>
      <div className="space-y-1 max-h-[240px] overflow-y-auto">
        {matches.slice(0, 50).map((m, i) => (
          <div key={i} className="text-xs text-ink-secondary">
            <span className="chem-mono text-[11px] text-teal">{String(m.file || '')}:{String(m.line ?? '')}</span>
            <span className="ml-1.5">{String(m.text || '')}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export function PlanTaskResult({ data }: { data: Record<string, unknown> }) {
  if (data.error) return <ErrorBox message={String(data.error)} />
  const steps = (data.steps || []) as { step?: number; description?: string }[]
  return (
    <div>
      <div className="text-[13px] font-medium text-ink mb-1">📋 {String(data.goal || '执行计划')}（{String(data.total_steps ?? steps.length)} 步）</div>
      <ol className="m-0 pl-4 text-xs text-ink-secondary space-y-0.5">
        {steps.map((s, i) => (
          <li key={i}>{s.step}. {s.description}</li>
        ))}
      </ol>
    </div>
  )
}

/* ── 分发 ── */

const RENDERERS: Record<string, (data: Record<string, unknown>) => ReactNode> = {
  search_exam_bank: (d) => <SearchResults data={d} />,
  web_search: (d) => <WebSearchView data={d} />,
  generate_questions: (d) => <QuestionCards data={d} />,
  diagnose_barrier: (d) =>
    d.student_name ? <StudentBarrierResult data={d} /> : <BarrierOverview data={d} />,
  chemistry_tutor: (d) => <TutorAnswer data={d} />,
  simulate_experiment: (d) => <Experiment data={d} />,
  balance_equation: (d) => <BalanceResult data={d} />,
  weekly_report: (d) => <WeeklyReport data={d} />,
  import_exam_paper: (d) => <ImportResult data={d} />,
  assign_adaptive_practice: (d) => <AssignResult data={d} />,
  // Legacy 兼容
  exam_generate: (d) => <QuestionCards data={d} />,
  exam_audit: (d) => <QuestionCards data={d} />,
  exam_search_historical: (d) => <SearchResults data={d} />,
  exam_results: (d) => <ExamStats data={d} />,
  diagnosis_barrier_class: (d) => <BarrierOverview data={d} />,
  diagnosis_plan_generate: (d) => <LearningPlan data={d} />,
  diagnosis_plan: (d) => <LearningPlan data={d} />,
  generate_learning_plan: (d) => <LearningPlan data={d} />,
  parser_ocr: (d) => <OcrTableView data={d} />,
  ocr_result: (d) => <OcrTableView data={d} />,
  /* 面板类工具：展示 message 文本（不落 JSON fallback） */
  show_exam_workbench: (d) => <ShowPanelResult data={d} />,
  // 诊断：工具卡内也渲染图表（后端在返回体保留 data 副本）
  show_diagnosis: (d) => {
    const dd = (d.data as Record<string, unknown> | undefined) ?? d
    return dd.student_name ? (
      <StudentBarrierResult data={dd} />
    ) : (
      <BarrierOverview data={dd} />
    )
  },
  show_students: (d) => <ShowPanelResult data={d} />,
  /* 文件与命令（DSH 式：内容直接可读） */
  read: (d) => <FileReadResult data={d} />,
  write: (d) => <FileWriteResult data={d} />,
  edit: (d) => <FileWriteResult data={d} />,
  find: (d) => <FindResult data={d} />,
  grep: (d) => <GrepResult data={d} />,
  bash: (d) => <BashResult data={d} />,
  plan_task: (d) => <PlanTaskResult data={d} />,
  /* 补齐渲染器（2026-08 S1：不裸 JSON） */
  save_to_bank: (d) => <BankSaveResult data={d} />,
  list_banks: (d) => <BankListResult data={d} />,
  delete_bank: (d) => <BankDeleteResult data={d} />,
  memory_student_get: (d) => <MemoryStudentResult data={d} />,
  memory_teacher_get: (d) => <MemoryTeacherResult data={d} />,
  send_learning_plan: (d) => <SendPlanResult data={d} />,
  generate_parent_report: (d) => <ParentReportResult data={d} />,
  send_report_to_parent: (d) => <SendReportResult data={d} />,
  query_ocr_progress: (d) => <OcrProgressResult data={d} />,
  grade_answer_sheets: (d) => <GradeSheetsResult data={d} />,
  save_grading_results: (d) => <SaveGradesResult data={d} />,
  query_batch_grades: (d) => <BatchGradesResult data={d} />,
  list_teacher_exams: (d) => <TeacherExamsResult data={d} />,
  parse_chemistry_document: (d) => <ParseDocResult data={d} />,
  import_question_bank: (d) => <ImportBankResult data={d} />,
  check_parser_services: (d) => <ParserServicesResult data={d} />,
  browse_navigate: (d) => <BrowseNavigateResult data={d} />,
  browse_read: (d) => <BrowseReadResult data={d} />,
  browse_click: (d) => <BrowseClickResult data={d} />,
  browse_input: (d) => <BrowseInputResult data={d} />,
  browse_screenshot: (d) => <BrowseScreenshotResult data={d} />,
}

/* ── 补齐渲染器（2026-08 S1 标准：全部工具可读展示，不裸 JSON） ── */

function ConfirmBox({ ok, text }: { ok: boolean; text: string }) {
  return (
    <div className={`flex items-start gap-2 text-[13px] ${ok ? 'text-ink-secondary' : 'text-error'}`}>
      <span>{ok ? '✅' : '⚠️'}</span>
      <span className="flex-1 leading-relaxed">{text}</span>
    </div>
  )
}

function KeyValueList({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data).filter(([, v]) => v !== null && v !== undefined && v !== '')
  if (entries.length === 0) return <div className="text-xs text-ink-muted">（暂无记录）</div>
  return (
    <div className="space-y-1.5">
      {entries.map(([k, v]) => (
        <div key={k} className="flex gap-2 text-[12px]">
          <span className="text-ink-muted shrink-0">{k}:</span>
          <span className="text-ink-secondary break-all">
            {typeof v === 'object' ? JSON.stringify(v) : String(v)}
          </span>
        </div>
      ))}
    </div>
  )
}

function SimpleTable({ rows }: { rows: string[][] }) {
  return (
    <table className="w-full text-[12px] border-collapse">
      <tbody>
        {rows.map((r, i) => (
          <tr key={i} className="border-b border-border/40 last:border-0">
            {r.map((c, j) => (
              <td key={j} className={`py-1 pr-2 align-top ${j === 0 ? 'text-ink-muted whitespace-nowrap' : 'text-ink-secondary'}`}>
                {c}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function BankSaveResult({ data }: { data: Record<string, unknown> }) {
  if (data.error) return <ErrorBox message={String(data.error)} />
  const count = Number(data.count ?? data.saved_count ?? 0)
  return (
    <ConfirmBox
      ok
      text={`已保存 ${count} 题到题库「${String(data.set_name ?? data.set_id ?? '')}」${data.message ? `：${data.message}` : ''}`}
    />
  )
}

export function BankListResult({ data }: { data: Record<string, unknown> }) {
  if (data.error) return <ErrorBox message={String(data.error)} />
  const banks = Array.isArray(data.banks) ? (data.banks as Record<string, unknown>[]) : []
  if (banks.length === 0) return <div className="text-xs text-ink-muted">（题库为空）</div>
  return (
    <SimpleTable
      rows={banks.map((b) => [
        String(b.name ?? b.set_name ?? b.set_id ?? ''),
        `${String(b.question_count ?? b.count ?? 0)} 题`,
        String(b.created_at ?? ''),
      ])}
    />
  )
}

export function BankDeleteResult({ data }: { data: Record<string, unknown> }) {
  if (data.error) return <ErrorBox message={String(data.error)} />
  return (
    <ConfirmBox
      ok={Boolean(data.deleted)}
      text={`${data.deleted ? '已删除' : '删除失败'}：${String(data.name ?? data.set_id ?? '')}${data.question_count !== undefined ? `（${data.question_count} 题）` : ''}${data.message ? ` ${data.message}` : ''}`}
    />
  )
}

export function MemoryStudentResult({ data }: { data: Record<string, unknown> }) {
  if (data.error) return <ErrorBox message={String(data.error)} />
  const diags = Array.isArray(data.diagnoses) ? (data.diagnoses as unknown[]) : []
  const plan = data.learning_plan
  return (
    <div className="space-y-2">
      <div className="text-[12px] text-ink-muted">学号：{String(data.student_id ?? '-')}</div>
      <div className="text-[13px] text-ink-secondary">
        诊断记录 <span className="font-medium text-ink">{diags.length}</span> 次
        {plan ? ' · 已有学习计划' : ''}
      </div>
      {diags.length > 0 && (
        <div className="space-y-1">
          {diags.slice(-3).map((d, i) => {
            const dd = (d ?? {}) as Record<string, unknown>
            return (
              <div key={i} className="text-[12px] text-ink-secondary border-l-2 border-teal/30 pl-2">
                {String(dd.key ?? dd.type ?? `记录 ${i + 1}`)}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export function MemoryTeacherResult({ data }: { data: Record<string, unknown> }) {
  if (data.error) return <ErrorBox message={String(data.error)} />
  return <KeyValueList data={data} />
}

export function SendPlanResult({ data }: { data: Record<string, unknown> }) {
  if (data.error) return <ErrorBox message={String(data.error)} />
  const ok = data.result === 'success' || Boolean(data.success)
  return (
    <ConfirmBox
      ok={ok}
      text={`${ok ? '已发送学习计划' : String(data.result ?? '发送失败')}${data.student_name ? `给 ${data.student_name}` : ''}`}
    />
  )
}

export function ParentReportResult({ data }: { data: Record<string, unknown> }) {
  if (data.error) return <ErrorBox message={String(data.error)} />
  const preview = String(data.preview ?? '')
  return (
    <div className="space-y-2">
      <div className="text-[12px] text-ink-muted">
        {String(data.student_name ?? '')} · {String(data.next_action ?? '')}
      </div>
      {preview && (
        <div className="text-[13px] text-ink-secondary whitespace-pre-wrap max-h-[300px] overflow-y-auto bg-surface-muted/40 rounded-[var(--radius-sm)] p-2.5">
          {preview}
        </div>
      )}
    </div>
  )
}

export function SendReportResult({ data }: { data: Record<string, unknown> }) {
  if (data.error) return <ErrorBox message={String(data.error)} />
  const ok = data.result === 'success' || Boolean(data.success)
  return (
    <ConfirmBox
      ok={ok}
      text={`${ok ? '已发送报告' : String(data.result ?? '发送失败')}${data.parent_name ? `给家长 ${data.parent_name}` : ''}${data.student_name ? `（${data.student_name}）` : ''}`}
    />
  )
}

export function OcrProgressResult({ data }: { data: Record<string, unknown> }) {
  if (data.error) return <ErrorBox message={String(data.error)} />
  const batches = (data.batches ?? {}) as Record<string, unknown>
  return (
    <div className="space-y-2">
      <div className="text-[13px] text-ink-secondary">{String(data.summary ?? '')}</div>
      <div className="text-[12px] text-ink-muted">
        {data.all_done ? '✅ 全部完成' : '⏳ 处理中'} · {String(data.next_action ?? '')}
      </div>
      <SimpleTable
        rows={Object.entries(batches).map(([k, v]) => {
          const b = (v ?? {}) as Record<string, unknown>
          const total = Number(b.total ?? 0)
          const done = Number(b.done ?? 0)
          const progress = total > 0 ? `${done}/${total}` : `${Array.isArray(b.tasks) ? b.tasks.length : 0} 个任务`
          return [String(b.batch_id ?? k), progress]
        })}
      />
    </div>
  )
}

export function GradeSheetsResult({ data }: { data: Record<string, unknown> }) {
  if (data.error) return <ErrorBox message={String(data.error)} />
  const results = Array.isArray(data.results) ? (data.results as Record<string, unknown>[]) : []
  return (
    <div className="space-y-2">
      <div className="text-[13px] text-ink-secondary">{String(data.message ?? data.summary ?? '')}</div>
      {results.length > 0 && (
        <SimpleTable
          rows={results.map((r) => [
            String(r.student_name ?? r.student_id ?? ''),
            `${String(r.score ?? '-')} / ${String(r.total ?? '-')}`,
            String(r.summary ?? ''),
          ])}
        />
      )}
    </div>
  )
}

export function SaveGradesResult({ data }: { data: Record<string, unknown> }) {
  if (data.error) return <ErrorBox message={String(data.error)} />
  const stats = [
    ['已保存', String(data.saved_count ?? 0)],
    ['总数', String(data.total ?? 0)],
  ]
  return (
    <div className="space-y-2">
      <div className="flex gap-3">
        {stats.map(([label, v]) => (
          <div key={label} className="flex-1 text-center">
            <div className="text-lg font-semibold text-ink leading-none">{v}</div>
            <div className="mt-1 text-[11px] text-ink-muted">{label}</div>
          </div>
        ))}
      </div>
      <div className="text-[12px] text-ink-secondary">{String(data.message ?? '')}</div>
    </div>
  )
}

export function BatchGradesResult({ data }: { data: Record<string, unknown> }) {
  if (data.error) return <ErrorBox message={String(data.error)} />
  const results = Array.isArray(data.results) ? (data.results as Record<string, unknown>[]) : []
  return (
    <div className="space-y-2">
      <div className="text-[13px] text-ink-secondary">
        {String(data.message ?? '')}
        {data.source ? <span className="ml-1.5 text-[11px] text-ink-muted">（{String(data.source)}）</span> : null}
      </div>
      {results.length > 0 && (
        <SimpleTable
          rows={results.map((r) => [
            String(r.student_name ?? r.student_id ?? ''),
            String(r.score ?? '-'),
          ])}
        />
      )}
    </div>
  )
}

export function TeacherExamsResult({ data }: { data: Record<string, unknown> }) {
  if (data.error) return <ErrorBox message={String(data.error)} />
  const classes = Array.isArray(data.classes) ? (data.classes as Record<string, unknown>[]) : []
  return (
    <div className="space-y-2">
      <div className="text-[12px] text-ink-muted">共 {String(data.total ?? classes.length)} 场考试</div>
      {classes.map((c, i) => {
        const exams = Array.isArray(c.exams) ? (c.exams as Record<string, unknown>[]) : []
        return (
          <div key={i} className="text-[12px]">
            <div className="font-medium text-ink text-[13px]">{String(c.class_name ?? c.class_id ?? '')}</div>
            {exams.map((e, j) => (
              <div key={j} className="text-ink-secondary pl-3 border-l-2 border-teal/30 my-1">
                {String(e.name ?? e.exam_name ?? '')}
              </div>
            ))}
          </div>
        )
      })}
    </div>
  )
}

export function ParseDocResult({ data }: { data: Record<string, unknown> }) {
  if (data.error) return <ErrorBox message={String(data.error)} />
  const result = (data.result ?? {}) as Record<string, unknown>
  const questions = Array.isArray(result.questions) ? result.questions : []
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-[12px]">
        <span className="text-teal font-medium">{String(data.provider ?? '')}</span>
        {data.fallback_used ? <span className="text-warning">（回退解析）</span> : null}
        {data.warning ? <span className="text-ink-muted">{String(data.warning)}</span> : null}
      </div>
      {questions.length > 0 ? (
        <div className="text-[13px] text-ink-secondary">
          解析出 <span className="font-medium text-ink">{questions.length}</span> 道题
        </div>
      ) : (
        result.preview ? (
          <div className="text-[12px] text-ink-secondary whitespace-pre-wrap max-h-[200px] overflow-y-auto">
            {String(result.preview)}
          </div>
        ) : null
      )}
    </div>
  )
}

export function ImportBankResult({ data }: { data: Record<string, unknown> }) {
  if (data.error) return <ErrorBox message={String(data.error)} />
  const questions = Array.isArray(data.questions) ? data.questions : []
  const preview = (data.preview ?? {}) as Record<string, unknown>
  return (
    <div className="space-y-2">
      <div className="text-[13px] text-ink-secondary">
        <span className="text-teal font-medium">{String(data.provider ?? '')}</span> · {String(data.source_name ?? '')}
        {data.year ? ` ${String(data.year)}` : ''}{data.region ? ` · ${String(data.region)}` : ''}
      </div>
      <div className="text-[13px]">
        待确认 <span className="font-medium text-ink">{String(data.question_count ?? questions.length)}</span> 道题
      </div>
      {preview.title ? <div className="text-[12px] text-ink-muted">{String(preview.title)}</div> : null}
    </div>
  )
}

export function ParserServicesResult({ data }: { data: Record<string, unknown> }) {
  // 真实形状：{ocr: {available, provider, note}, ...}；布尔/字符串为旧形状兼容
  const rows = ['ocr', 'mineru', 'vision'].map((k) => {
    const v = data[k]
    let ok: boolean
    if (typeof v === 'object' && v !== null) {
      const rec = v as Record<string, unknown>
      ok = (rec.available ?? rec.ok ?? true) !== false
    } else {
      ok = v === true || v === 'ok'
    }
    return [k, ok ? '✅ 正常' : '❌ 不可用']
  })
  return <SimpleTable rows={rows} />
}

function BrowseBox({ children }: { children: ReactNode }) {
  return <div className="text-[12px] text-ink-secondary whitespace-pre-wrap break-all max-h-[200px] overflow-y-auto">{children}</div>
}

export function BrowseNavigateResult({ data }: { data: Record<string, unknown> }) {
  if (data.error) return <ErrorBox message={String(data.error)} />
  return (
    <div className="space-y-1.5">
      <div className="text-[13px] font-medium text-ink">{String(data.title ?? '')}</div>
      <div className="text-[11px] text-ink-muted break-all">{String(data.url ?? '')}</div>
      <BrowseBox>{String(data.text ?? '').slice(0, 600)}</BrowseBox>
    </div>
  )
}

export function BrowseReadResult({ data }: { data: Record<string, unknown> }) {
  if (data.error) return <ErrorBox message={String(data.error)} />
  return (
    <div className="space-y-1.5">
      <div className="text-[11px] text-ink-muted">selector: {String(data.selector ?? '')}</div>
      <BrowseBox>{String(data.text ?? '')}</BrowseBox>
    </div>
  )
}

export function BrowseClickResult({ data }: { data: Record<string, unknown> }) {
  if (data.error) return <ErrorBox message={String(data.error)} />
  return (
    <div className="space-y-1.5">
      <div className="text-[13px] text-ink-secondary">已点击 {String(data.selector ?? '')}</div>
      {data.title ? <div className="text-[12px] font-medium text-ink">{String(data.title)}</div> : null}
      {data.after ? <BrowseBox>{String(data.after).slice(0, 400)}</BrowseBox> : null}
    </div>
  )
}

export function BrowseInputResult({ data }: { data: Record<string, unknown> }) {
  if (data.error) return <ErrorBox message={String(data.error)} />
  return <div className="text-[13px] text-ink-secondary">已输入：{String(data.text ?? '')}</div>
}

export function BrowseScreenshotResult({ data }: { data: Record<string, unknown> }) {
  if (data.error) return <ErrorBox message={String(data.error)} />
  const shot = String(data.screenshot ?? '')
  return shot.startsWith('data:image') ? (
    <img src={shot} alt="页面截图" className="max-w-full rounded-[var(--radius-sm)] border border-border" />
  ) : (
    <div className="text-[13px] text-ink-secondary">截图已捕获（{shot.length} 字符）</div>
  )
}

export function ToolResultView({ tool, data }: { tool: string; data: unknown }) {
  // 2026-09-21 文案契约分离（架构审查 C）：带 ui_label 的拦截结果走中性
  // 展示（等待确认等），不落 ErrorBox/JsonFallback——llm_brief 是给模型
  // 的事实，error 是机器码，都不是给老师看的文案
  if (data && typeof data === 'object' && 'ui_label' in (data as Record<string, unknown>)) {
    const d = data as Record<string, unknown>
    return <p className="text-sm text-ink-secondary m-0">{String(d.ui_label)}</p>
  }
  const render = RENDERERS[tool]
  if (render && typeof data === 'object' && data !== null) {
    return render(data as Record<string, unknown>)
  }
  return <JsonFallback data={data} />
}

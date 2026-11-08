/* InlinePanels.tsx — component 事件的内联面板（旧版 renderExamWorkbench 等移植）
 * 旧版行为：Agent 打开面板时在对话气泡内渲染，不跳页。 */

import { useEffect, useState } from 'react'
import { Ban, Check, Pencil, Plus, Save, Send, Sparkles, Trash2, Undo2, X } from 'lucide-react'
import { InputNumber, Tag as AntdTag } from 'antd'
import { api } from '../../lib/api'
import { useLiveTimer } from '../../lib/use-live-timer'
import { EXAM_TYPE_CHIPS, EXAM_TYPE_LABELS } from '../../lib/exam-types'
import { Badge, Button, Input, Select, Tag, useToast } from '../ui'
import { QuestionMd } from '../QuestionMd'
import { AnswerMd } from '../AnswerMd'
import { OptionsRow } from '../OptionsRow'
import { VariantBrowserModal } from './VariantBrowserModal'
import { BarrierOverview, LearningPlan } from './tool-renderers'

/* ── 类型 ── */

interface KpItem {
  name: string
  active: boolean
}

interface TypeChip {
  val: string
  label: string
  active: boolean
  qty: number
}

interface GenQuestion {
  content?: string
  options?: string[] | string
  answer?: string
  knowledge_points?: string[]
  difficulty?: string
  overall_status?: string
  _saved?: boolean
  _removed?: boolean
}

interface ExamSet {
  set_id: string
  name?: string
  question_count?: number
}

const TYPE_LABELS = EXAM_TYPE_LABELS

/** 合并 Agent 预填题型与完整题型清单（用户反馈：内联出题界面没有题型选择）。
 * 始终展示全部 6 种题型 chips；Agent 预填的（params.types）保持选中与数量，
 * 未预填的用默认值；预填了清单外题型（如 choice）也保留。 */
function mergePanelTypes(paramsTypes: unknown): TypeChip[] {
  const byVal = new Map<string, Partial<TypeChip>>()
  if (Array.isArray(paramsTypes)) {
    for (const t of paramsTypes) {
      if (t && typeof t === 'object' && typeof (t as TypeChip).val === 'string') {
        byVal.set((t as TypeChip).val, t as Partial<TypeChip>)
      }
    }
  }
  const merged = EXAM_TYPE_CHIPS.map((d) => {
    const t = byVal.get(d.val)
    if (!t) return { ...d }
    return {
      val: d.val,
      label: t.label || d.label,
      active: t.active !== undefined ? Boolean(t.active) : d.active,
      qty: Number(t.qty) > 0 ? Number(t.qty) : d.qty,
    }
  })
  for (const [val, t] of byVal) {
    if (!merged.some((m) => m.val === val)) {
      merged.push({
        val,
        label: t.label || TYPE_LABELS[val] || val,
        active: t.active !== undefined ? Boolean(t.active) : true,
        qty: Number(t.qty) > 0 ? Number(t.qty) : 1,
      })
    }
  }
  return merged
}

/** 内联出题工作台（旧版 renderExamWorkbench 的 React 移植） */
function InlineExamWorkbench({ params }: { params: Record<string, unknown> }) {
  const toast = useToast()
  const preKps = (params.knowledge_points as string[] | undefined) || []
  const [kps, setKps] = useState<KpItem[]>([])
  const [kpSearch, setKpSearch] = useState('')
  const [types, setTypes] = useState<TypeChip[]>(mergePanelTypes(params.types))
  const [difficulty, setDifficulty] = useState(String(params.difficulty || 'medium'))
  const [generating, setGenerating] = useState(false)
  const [questions, setQuestions] = useState<GenQuestion[]>(
    ((params.questions as GenQuestion[] | undefined) || []).map((q) => ({ ...q, _saved: false, _removed: false })),
  )
  const [folders, setFolders] = useState<ExamSet[]>([])
  const [selectedFolder, setSelectedFolder] = useState('')
  // 旧版面板生成计时器（⚡ AI 出题 + live-timer）
  const genSec = useLiveTimer(generating)
  // 变种题（基于高考真题作蓝本，旧版内联面板功能）
  const [useVariant, setUseVariant] = useState(Boolean(params.variant_source))
  const [variantQid, setVariantQid] = useState(String(params.variant_source || ''))
  const [variantLabel, setVariantLabel] = useState(String(params.variant_label || ''))
  const [variantOpen, setVariantOpen] = useState(false)

  useEffect(() => {
    api
      .get<{ knowledge_points?: { name?: string }[]; data?: { name?: string }[] }>('/api/knowledge/list')
      .then((d) => {
        const items = d.knowledge_points || d.data || []
        const names = items.map((k) => k.name || String(k))
        const merged: KpItem[] = names.map((name) => ({ name, active: preKps.includes(name) }))
        // Agent 预填但接口列表缺失的知识点补为已选（旧版内联面板行为）
        for (const k of preKps) {
          if (!names.includes(k)) merged.push({ name: k, active: true })
        }
        setKps(merged)
      })
      .catch(() => setKps(preKps.map((name) => ({ name, active: true }))))
    api
      .get<{ data?: { exam_sets?: ExamSet[] } }>('/api/exam-bank/exam-sets')
      .then((d) => {
        const list = d.data?.exam_sets || []
        setFolders(list)
        const set = String(params.set_name || '')
        const matched = list.find((f) => f.name === set) || list[0]
        if (matched) setSelectedFolder(matched.set_id)
      })
      .catch(() => setFolders([]))
  }, [])

  async function generate() {
    // 变种题模式：基于蓝本题目生成（旧版内联面板功能）
    if (useVariant && variantQid) {
      setGenerating(true)
      try {
        const d = await api.post<{ questions?: GenQuestion[] }>('/api/question/generate', {
          knowledge_points: [],
          difficulty,
          quantity: 3,
          question_types: ['choice'],
          variant_source_id: variantQid,
        })
        setQuestions(
          (d.questions || []).map((q) => ({ ...q, _saved: false, _removed: false })),
        )
        toast.success(`已生成 ${(d.questions || []).length} 道变种题`)
      } catch {
        toast.error('生成失败')
      } finally {
        setGenerating(false)
      }
      return
    }
    const kpNames = kps.filter((k) => k.active).map((k) => k.name)
    const activeTypes = types.filter((t) => t.active)
    if (!kpNames.length) {
      toast.warning('请选择至少一个知识点')
      return
    }
    if (!activeTypes.length) {
      toast.warning('请选择至少一种题型')
      return
    }
    setGenerating(true)
    const all: GenQuestion[] = []
    let pending = activeTypes.length
    for (const t of activeTypes) {
      try {
        const d = await api.post<{ questions?: GenQuestion[] }>('/api/question/generate', {
          knowledge_points: kpNames,
          difficulty,
          quantity: t.qty || 2,
          question_types: [t.val],
        })
        all.push(...(d.questions || []).map((q) => ({ ...q, _saved: false, _removed: false })))
      } catch {
        /* 单类型失败继续 */
      } finally {
        pending--
        if (!pending) {
          setQuestions(all)
          setGenerating(false)
          toast.success(`已生成 ${all.length} 题`)
        }
      }
    }
  }

  async function saveOne(i: number) {
    const q = questions[i]
    if (!q || q._removed || q._saved) return
    if (!selectedFolder) {
      toast.warning('请先选择保存目标题库')
      return
    }
    try {
      const d = await api.post<{ success?: boolean; message?: string }>('/api/exam-bank/import-questions', {
        set_id: selectedFolder,
        questions: [
          {
            content: q.content,
            options: Array.isArray(q.options) ? q.options : typeof q.options === 'string' ? q.options.split(',').filter(Boolean) : [],
            answer: q.answer || '',
            analysis: '',
            knowledge_points: q.knowledge_points || [],
            difficulty: q.difficulty || 'medium',
          },
        ],
      })
      if (d.success !== false) {
        setQuestions((prev) => prev.map((x, idx) => (idx === i ? { ...x, _saved: true, _removed: true } : x)))
        toast.success('已保存到题库')
      } else {
        toast.error(d.message || '保存失败')
      }
    } catch {
      toast.error('保存失败')
    }
  }

  async function saveAll() {
    const active = questions.filter((q) => !q._removed && !q._saved)
    if (!active.length || !selectedFolder) {
      toast.warning('请先选择保存目标题库')
      return
    }
    let ok = 0
    for (const q of active) {
      try {
        await api.post('/api/exam-bank/import-questions', {
          set_id: selectedFolder,
          questions: [
            {
              content: q.content,
              options: Array.isArray(q.options) ? q.options : typeof q.options === 'string' ? q.options.split(',').filter(Boolean) : [],
              answer: q.answer || '',
              analysis: '',
              knowledge_points: q.knowledge_points || [],
              difficulty: q.difficulty || 'medium',
            },
          ],
        })
        ok++
      } catch {
        /* 继续 */
      }
    }
    setQuestions((prev) => prev.map((q) => (q._removed || q._saved ? q : { ...q, _saved: true, _removed: true })))
    toast.success(`已保存 ${ok}/${active.length} 题`)
  }

  /* ── 新建题库（旧版 "+ 新建" 行为） ── */
  async function createFolder() {
    const name = window.prompt('新题库名称：', '')
    if (!name || !name.trim()) return
    try {
      const d = await api.post<{ success?: boolean; set_id?: string; message?: string }>('/api/exam-bank/exam-sets', {
        name: name.trim(),
      })
      if (d.success !== false) {
        toast.success(`已创建题库「${name.trim()}」`)
        const list = await api.get<{ data?: { exam_sets?: ExamSet[] } }>('/api/exam-bank/exam-sets')
        const sets = list.data?.exam_sets || []
        setFolders(sets)
        const created = sets.find((f) => f.name === name.trim()) || sets[sets.length - 1]
        if (created) setSelectedFolder(created.set_id)
      } else {
        toast.error(d.message || '创建失败')
      }
    } catch (e) {
      toast.error(`创建失败: ${e instanceof Error ? e.message : ''}`)
    }
  }

  const filteredKps = kps.filter((k) => !kpSearch || k.name.toLowerCase().includes(kpSearch.toLowerCase()))

  return (
    <div className="self-start max-w-[95%] w-full bg-surface border border-teal/25 rounded-[var(--radius-lg)] shadow-[var(--shadow-md)] animate-fade-in-up overflow-hidden flex flex-col max-h-[72vh]">
      {/* 面板头（固定） */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-teal-soft/60 border-b border-teal/15 shrink-0">
        <div className="flex items-center gap-2 text-[13px] font-semibold text-teal">
          <Sparkles size={14} />
          出题工作台
        </div>
        <span className="text-[11px] text-ink-muted">
          {generating ? (
            <span className="flex items-center gap-1.5">
              ⚡ AI 出题
              <span className="live-timer ticking text-ink-muted chem-mono">{genSec.toFixed(1)}s</span>
            </span>
          ) : questions.length ? (
            `已生成 ${questions.length} 道题目`
          ) : (
            '等待生成'
          )}
        </span>
      </div>

      <div className="p-3.5 space-y-3 overflow-y-auto min-h-0">
        {/* 知识点 */}
        <div>
          <div className="text-xs font-medium text-ink-secondary mb-1.5">知识点（点击选择）</div>
          <Input value={kpSearch} onChange={(e) => setKpSearch(e.target.value)} placeholder="搜索知识点…" className="h-8 text-[13px] mb-1.5" />
          <div className="max-h-[120px] overflow-y-auto flex gap-1.5 flex-wrap">
            {filteredKps.slice(0, 40).map((k) => (
              <button
                key={k.name}
                onClick={() => setKps((prev) => prev.map((x) => (x.name === k.name ? { ...x, active: !x.active } : x)))}
                className={`px-2.5 py-1 rounded-[var(--radius-full)] text-xs border transition-colors cursor-pointer ${
                  k.active
                    ? 'border-primary bg-primary-soft text-primary font-medium'
                    : 'border-border text-ink-secondary hover:border-border-strong'
                }`}
              >
                {k.name}
              </button>
            ))}
            {filteredKps.length === 0 && <span className="text-xs text-ink-muted">加载中…</span>}
          </div>
        </div>

        {/* 题型 + 难度（antd CheckableTag + InputNumber，2026-08 第二轮） */}
        <div className="flex items-center gap-2 flex-wrap">
          {types.map((t) => (
            <AntdTag.CheckableTag
              key={t.val}
              checked={t.active}
              onChange={() => setTypes((prev) => prev.map((x) => (x.val === t.val ? { ...x, active: !x.active } : x)))}
              className={`!rounded-[var(--radius-md)] !px-2.5 !py-0.5 !text-xs !border !border-solid transition-all ${
                t.active ? '!border-primary !bg-primary-soft !text-primary !font-medium' : '!border-border !text-ink-secondary'
              }`}
            >
              <span className="flex items-center gap-1">
                <span className="text-[9px]">{t.active ? '●' : '○'}</span>
                {t.label}
                {t.active && (
                  <InputNumber
                    size="small"
                    min={1}
                    max={10}
                    value={t.qty}
                    onClick={(e) => e.stopPropagation()}
                    onChange={(v) =>
                      setTypes((prev) =>
                        prev.map((x) =>
                          x.val === t.val ? { ...x, qty: Math.max(1, Math.min(10, Number(v) || 1)) } : x,
                        ),
                      )
                    }
                    className="!w-[56px] !text-xs"
                  />
                )}
              </span>
            </AntdTag.CheckableTag>
          ))}
          <Select value={difficulty} onChange={(e) => setDifficulty(e.target.value)} className="h-8 w-[100px] text-xs ml-auto">
            <option value="easy">容易</option>
            <option value="medium">中等</option>
            <option value="hard">困难</option>
          </Select>
        </div>

        {/* 保存目标 + 操作 */}
        <div className="flex items-center gap-2 flex-wrap">
          <Select value={selectedFolder} onChange={(e) => setSelectedFolder(e.target.value)} className="h-8 w-[180px] text-xs">
            {folders.map((f) => (
              <option key={f.set_id} value={f.set_id}>
                {f.name}（{f.question_count || 0} 题）
              </option>
            ))}
          </Select>
          <Button size="sm" variant="ghost" onClick={createFolder} title="新建题库">
            <Plus size={13} />
            新建
          </Button>
          {useVariant && (
            <Tag tone="teal" size="sm">
              蓝本: {variantLabel || '已设置'}
              <button className="ml-1.5 hover:text-teal-hover cursor-pointer" onClick={() => setUseVariant(false)}>
                <X size={11} />
              </button>
            </Tag>
          )}
          <Button size="sm" variant="secondary" onClick={() => setVariantOpen(true)} title="基于高考真题生成变种题">
            <Pencil size={12} />
            选蓝本
          </Button>
          <Button size="sm" variant="ai" onClick={generate} loading={generating}>
            <Sparkles size={13} />
            生成题目
          </Button>
          {questions.filter((q) => !q._removed && !q._saved).length > 0 && (
            <Button size="sm" onClick={saveAll}>
              <Save size={13} />
              全部保存
            </Button>
          )}
        </div>

        {/* 题目结果 */}
        {questions.filter((q) => !q._removed).length > 0 && (
          <div className="space-y-2">
            {questions.map((q, i) => {
              if (q._removed) return null
              const status = q.overall_status || 'passed'
              return (
                <div key={i} className="border border-border rounded-[var(--radius-md)] p-3">
                  <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                    <Tag tone="blue" size="sm">
                      {TYPE_LABELS[types.find((t) => t.val === 'single_choice')?.val || ''] || '题目'} #{i + 1}
                    </Tag>
                    {status === 'passed' ? (
                      <Badge status="pass" label="四维审核通过" />
                    ) : status === 'warning' ? (
                      <Badge status="warning" label="需人工确认" />
                    ) : (
                      <Badge status="blocked" label="审核拦截" />
                    )}
                  </div>
                  <QuestionMd text={q.content || ''} />
                  <OptionsRow options={q.options} className="mt-1.5" />
                  <div className="flex items-center gap-2 mt-2 flex-wrap">
                    <AnswerMd text={q.answer || ''} />
                    {(q.knowledge_points || []).map((k) => (
                      <Tag key={k} tone="gray" size="sm">
                        {k}
                      </Tag>
                    ))}
                    <div className="ml-auto flex gap-1.5">
                      {q._saved ? (
                        <span className="text-xs text-success flex items-center gap-1">
                          <Check size={13} /> 已保存
                        </span>
                      ) : (
                        <>
                          <Button size="sm" variant="secondary" onClick={() => saveOne(i)}>
                            <Save size={12} />
                            保存
                          </Button>
                          <button
                            onClick={() => setQuestions((prev) => prev.map((x, idx) => (idx === i ? { ...x, _removed: true } : x)))}
                            className="p-1.5 rounded text-ink-muted hover:text-error hover:bg-error-soft transition-colors cursor-pointer"
                          >
                            <Trash2 size={13} />
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* 选真题作蓝本（变种题入口） */}
      <VariantBrowserModal
        open={variantOpen}
        onClose={() => setVariantOpen(false)}
        onPick={(q, label) => {
          setVariantQid(q.exam_id || q.question_id || '')
          setVariantLabel(label)
          setUseVariant(true)
          setVariantOpen(false)
          toast.success(`已设置蓝本: ${label}`)
        }}
      />
    </div>
  )
}

/** 内联诊断面板（params.data 存在时渲染障碍分布，否则给引导）
 * 支持两种数据形态（agent/tools/diagnosis.py）：
 *  - 班级场景：{class_id, barrier_distribution/class_barrier_distribution, students}
 *  - 学生场景：{student_id, student_name, barrier_distribution, weak_knowledge_points, score_trend} */
function InlineDiagnosis({ params }: { params: Record<string, unknown> }) {
  // 兼容两种结构：后端统一发 {data: {...}}；旧平铺结构做回退
  const data = (params.data as Record<string, unknown> | undefined) ?? params
  const hasStudentData = !!data && !!data.student_name
  // 学生优先（2026-08 修复「0% 掌握度」）：barrier_distribution 两种场景都有，
  // 不能作为班级判据——只有无 student_name 且带班级字段时才走班级视图
  const hasClassData =
    !hasStudentData &&
    !!data &&
    (!!(data.students as unknown[])?.length || !!data.class_barrier_distribution || !!data.barrier_distribution)
  const barrier = (data?.barrier_distribution as Record<string, number> | undefined) || {}
  if (hasClassData || hasStudentData) {
    return (
      <div className="self-start max-w-[95%] w-full bg-surface border border-teal/25 rounded-[var(--radius-lg)] shadow-[var(--shadow-md)] animate-fade-in-up p-3.5">
        <div className="text-[13px] font-semibold text-teal mb-2.5 flex items-center gap-2">
          <Sparkles size={14} />
          {hasStudentData ? `学生诊断 · ${String(data!.student_name || '')}` : '班级障碍诊断'}
        </div>
        {hasClassData ? (
          <BarrierOverview
            data={{
              ...data,
              class_barrier_distribution:
                (data!.class_barrier_distribution as Record<string, number>) || barrier,
            }}
          />
        ) : (
          <div>
            <div className="flex items-center gap-2.5 mb-2">
              {(['concept', 'reading', 'expression'] as const).map((k) => {
                const val = barrier[k] || 0
                const labels: Record<string, string> = { concept: '概念理解', reading: '审题仔细', expression: '答题表述' }
                const colors: Record<string, string> = {
                  concept: 'bg-primary',
                  reading: 'bg-teal',
                  expression: 'bg-success',
                }
                return (
                  <div key={k} className="flex-1 bg-surface-muted rounded-[var(--radius-md)] py-2 text-center">
                    <div className={`text-lg font-semibold ${colors[k]}`}>{Math.round(val * 100)}%</div>
                    <div className="text-[11px] text-ink-muted mt-0.5">{labels[k]}</div>
                  </div>
                )
              })}
            </div>
            {(data!.weak_knowledge_points as { name?: string }[] | undefined)?.length ? (
              <div className="flex gap-1.5 flex-wrap mb-1">
                {(data!.weak_knowledge_points as { name?: string }[]).map((k, i) => (
                  <Tag key={i} tone="gray" size="sm">
                    {String(k.name || '')}
                  </Tag>
                ))}
              </div>
            ) : null}
          </div>
        )}
        {/* 旧版行为恢复（agent-renderers.js _diagToExam）：
            一键针对障碍出题练习 → 发消息给 Agent 打开出题面板 */}
        <button
          onClick={() =>
            window.dispatchEvent(
              new CustomEvent('chemai:send', {
                detail: `针对${hasStudentData ? String(data!.student_name) + '的' : ''}学习障碍出题练习`,
              }),
            )
          }
          className="mt-3 w-full flex items-center justify-center gap-1.5 px-3 py-2 rounded-[var(--radius-md)] border border-teal/30 bg-teal-soft/40 text-teal text-[13px] font-medium hover:bg-teal-soft transition-colors cursor-pointer"
        >
          <Sparkles size={13} />
          针对障碍出题练习
        </button>
      </div>
    )
  }
  return (
    <div className="self-start max-w-[95%] bg-surface border border-teal/25 rounded-[var(--radius-lg)] p-3.5 animate-fade-in-up">
      <div className="text-[13px] font-semibold text-teal mb-1 flex items-center gap-2">
        <Sparkles size={14} />
        障碍诊断
      </div>
      <p className="text-xs text-ink-secondary m-0">
        {params.class_id ? `班级 ${String(params.class_id)} · 考试 ${String(params.exam_id || '—')}` : '请告诉 Agent 要诊断的班级与考试'}
      </p>
    </div>
  )
}

/** 内联家长报告面板（issue #12）：channel 打回修订后按名替换此面板 */
function InlineParentReport({ params }: { params: Record<string, unknown> }) {
  const data = params.data as Record<string, unknown> | undefined
  const report = (data?.report_data || {}) as Record<string, unknown>
  const weak = (report.weak_knowledge_points as { name: string; errors: number }[] | undefined) || []
  const version = Number(params.version || 0)
  return (
    <div className="self-start max-w-[95%] w-full bg-surface border border-teal/25 rounded-[var(--radius-lg)] p-3.5 animate-fade-in-up">
      <div className="text-[13px] font-semibold text-teal mb-1.5 flex items-center gap-2">
        <Sparkles size={14} />
        家长报告{version ? ` · 第 ${version} 版` : ''}
      </div>
      <div className="grid grid-cols-2 gap-2 text-[13px]">
        <span className="text-ink-secondary">本周练习：<b className="text-ink">{String(report.week_practice_count ?? '—')}</b> 道</span>
        <span className="text-ink-secondary">正确率：<b className="text-ink">{String(report.week_accuracy ?? '—')}%</b></span>
        <span className="text-ink-secondary">主要特点：<b className="text-ink">{String(report.dominant_barrier || '—')}</b></span>
        <span className="text-ink-secondary">累计练习：<b className="text-ink">{String(report.exercises_completed ?? '—')}</b> 道</span>
      </div>
      {weak.length > 0 && (
        <p className="mt-2 text-[13px] text-ink-secondary m-0">
          薄弱知识点：{weak.map((k) => `${k.name}(${k.errors}次)`).join('、')}
        </p>
      )}
      {String(report.suggestion || '') !== '' && (
        <p className="mt-1.5 text-[13px] text-ink-secondary m-0">💡 {String(report.suggestion)}</p>
      )}
      {String(report.teacher_note || '') !== '' && (
        <p className="mt-1 text-[13px] text-teal m-0">📝 {String(report.teacher_note)}</p>
      )}
    </div>
  )
}

/** 内联学习计划面板（2026-08：不跳页，聊天内预览 + 保存/发送；
 * ADR-0013：带 draft_id 的草稿走三值门——确认发送/打回/放弃，与聊天确认卡同一条 service 接缝） */
function InlineLearningPlan({ params }: { params: Record<string, unknown> }) {
  const toast = useToast()
  const [saving, setSaving] = useState(false)
  const [sending, setSending] = useState(false)
  const [gateBusy, setGateBusy] = useState<'' | 'approve' | 'reject' | 'abandon'>('')
  const [feedback, setFeedback] = useState('')
  const [rejectOpen, setRejectOpen] = useState(false)
  const [resolved, setResolved] = useState<'' | 'approved' | 'rejected' | 'abandoned'>('')
  // #10：面板内打回后 service 返回的 v2 —— 原地替换预览并重开门（多轮循环不离面板）
  const [draftOverride, setDraftOverride] = useState<{ version: number; content: Record<string, unknown> } | null>(null)
  const [histOpen, setHistOpen] = useState(false)
  const [history, setHistory] = useState<{ draft_id: string; version: number; content: Record<string, unknown>; feedback: string; created_at: string }[]>([])
  const [histLoading, setHistLoading] = useState(false)
  const [histOpenIdx, setHistOpenIdx] = useState<number | null>(null)
  const data = params.data as Record<string, unknown> | undefined
  const sid = String(data?.student_id || params.student_id || '')
  const plan = draftOverride?.content ?? ((data?.plan || data?.plan_data) as Record<string, unknown> | undefined)
  const draftId = String(params.draft_id || data?.draft_id || '')
  const version = draftOverride?.version ?? Number(params.version || 0)

  async function decide(action: 'approve' | 'reject' | 'abandon') {
    if (!sid || !draftId) return
    if (action === 'reject' && !feedback.trim()) return
    setGateBusy(action)
    try {
      const out = await api.post<{ success: boolean; sent?: unknown; draft?: { version: number; content: Record<string, unknown> } }>(
        `/api/diagnosis/learning-plan/draft/${sid}/${draftId}/decision`,
        { action, feedback: action === 'reject' ? feedback.trim() : '' },
      )
      if (action === 'reject' && out.draft) {
        // 打回 → 渲染修订版并重开门（版本号推进，反馈框清空）
        setDraftOverride({ version: out.draft.version, content: out.draft.content })
        setResolved('')
        setFeedback('')
        setRejectOpen(false)
        setHistory([]) // 新版本后强制重新拉取历史
        toast.success(`已打回，修订为第 ${out.draft.version} 版`)
        return
      }
      setResolved(action === 'approve' ? 'approved' : action === 'reject' ? 'rejected' : 'abandoned')
      toast.success(
        action === 'approve' ? '已确认发送给学生'
          : action === 'reject' ? '已打回，按意见修订' : '已放弃本次发送',
      )
    } catch (e) {
      toast.error(`操作失败: ${e instanceof Error ? e.message : ''}`)
    } finally {
      setGateBusy('')
    }
  }

  async function savePlan() {
    if (!sid || !plan) return
    setSaving(true)
    try {
      await api.post(`/api/diagnosis/learning-plan/apply/${sid}`, plan)
      toast.success('学习计划已保存到学生端')
    } catch (e) {
      toast.error(`保存失败: ${e instanceof Error ? e.message : ''}`)
    } finally {
      setSaving(false)
    }
  }

  async function sendPlan() {
    if (!sid) return
    setSending(true)
    try {
      await api.post(`/api/diagnosis/learning-plan/send-to-parent/${sid}`, plan || {})
      toast.success('学习计划已发送给家长')
    } catch (e) {
      toast.error(`发送失败: ${e instanceof Error ? e.message : ''}`)
    } finally {
      setSending(false)
    }
  }

  async function toggleHistory() {
    const next = !histOpen
    setHistOpen(next)
    if (!next || history.length > 0 || !sid || !draftId) return
    setHistLoading(true)
    try {
      const out = await api.get<{ success: boolean; versions: typeof history }>(
        `/api/diagnosis/learning-plan/draft/${sid}/${draftId}/versions`,
      )
      setHistory(out.versions || [])
    } catch {
      toast.error('修订历史加载失败')
    } finally {
      setHistLoading(false)
    }
  }

  if (data && (data.plan || data.plan_data)) {
    const gateResolved = resolved !== ''
    const effectiveData = { ...data, plan }
    return (
      <div className="self-start max-w-[95%] w-full animate-fade-in-up">
        <LearningPlan data={effectiveData} />
        {draftId && !gateResolved ? (
          <div className="mt-2.5">
            <div className="flex gap-2">
              <button
                onClick={() => decide('approve')}
                disabled={gateBusy !== ''}
                className="flex items-center gap-1.5 px-3 py-2 rounded-[var(--radius-md)] bg-primary text-white text-[13px] font-medium hover:opacity-90 transition-opacity cursor-pointer disabled:opacity-50"
              >
                <Send size={13} />
                {gateBusy === 'approve' ? '发送中…' : version ? `确认发送给学生（第 ${version} 版）` : '确认发送给学生'}
              </button>
              {!rejectOpen && (
                <button
                  onClick={() => setRejectOpen(true)}
                  disabled={gateBusy !== ''}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-[var(--radius-md)] border border-border text-ink-secondary text-[13px] hover:border-teal hover:text-teal transition-colors cursor-pointer disabled:opacity-50"
                >
                  <Undo2 size={13} />
                  打回修改
                </button>
              )}
              <button
                onClick={() => decide('abandon')}
                disabled={gateBusy !== ''}
                className="flex items-center gap-1.5 px-3 py-2 rounded-[var(--radius-md)] text-ink-muted text-[13px] hover:bg-surface-muted transition-colors cursor-pointer disabled:opacity-50"
              >
                <Ban size={13} />
                放弃
              </button>
            </div>
            {rejectOpen && (
              <div className="mt-2 flex gap-2 items-start">
                <textarea
                  value={feedback}
                  onChange={(e) => setFeedback(e.target.value)}
                  rows={2}
                  placeholder="写明要修改的地方，如：第二周改成盐类水解专题"
                  className="flex-1 text-[13px] px-2.5 py-2 rounded-[var(--radius-sm)] border border-border bg-surface focus:outline-none focus:border-teal resize-y"
                  autoFocus
                />
                <button
                  onClick={() => decide('reject')}
                  disabled={!feedback.trim() || gateBusy !== ''}
                  className="px-3 py-2 rounded-[var(--radius-md)] border border-teal/30 bg-teal-soft/40 text-teal text-[13px] font-medium hover:bg-teal-soft transition-colors cursor-pointer disabled:opacity-50"
                >
                  {gateBusy === 'reject' ? '提交中…' : '提交'}
                </button>
              </div>
            )}
          </div>
        ) : gateResolved ? (
          <p className="mt-2 text-[12px] text-ink-muted m-0">
            {resolved === 'approved' && '✅ 已确认发送给学生'}
            {resolved === 'rejected' && '↩ 已打回，修订版将重新呈现在此'}
            {resolved === 'abandoned' && '⊘ 已放弃本次发送（草稿保留）'}
          </p>
        ) : gateResolved && resolved === 'rejected' ? (
          <p className="mt-2 text-[12px] text-ink-muted m-0">↩ 已打回，修订版将重新呈现在此</p>
        ) : (
          <div className="flex gap-2 mt-2.5">
            <button
              onClick={savePlan}
              disabled={saving}
              className="flex items-center gap-1.5 px-3 py-2 rounded-[var(--radius-md)] bg-primary text-white text-[13px] font-medium hover:opacity-90 transition-opacity cursor-pointer disabled:opacity-50"
            >
              <Save size={13} />
              {saving ? '保存中…' : '保存到学生端'}
            </button>
            <button
              onClick={sendPlan}
              disabled={sending}
              className="flex items-center gap-1.5 px-3 py-2 rounded-[var(--radius-md)] border border-teal/30 bg-teal-soft/40 text-teal text-[13px] font-medium hover:bg-teal-soft transition-colors cursor-pointer disabled:opacity-50"
            >
              <Send size={13} />
              {sending ? '发送中…' : '发送给家长'}
            </button>
          </div>
        )}
        {draftId && (
          <div className="mt-2.5">
            <button
              onClick={toggleHistory}
              className="text-[12px] text-ink-secondary hover:text-teal transition-colors cursor-pointer flex items-center gap-1"
            >
              {histOpen ? '▾' : '▸'} 修订历史{history.length > 0 ? `（${history.length} 版）` : ''}
            </button>
            {histOpen && (
              <div className="mt-1.5 border-l-2 border-border pl-3 space-y-1.5">
                {histLoading && <p className="text-[12px] text-ink-muted m-0">加载中…</p>}
                {!histLoading && history.length === 0 && (
                  <p className="text-[12px] text-ink-muted m-0">暂无版本记录</p>
                )}
                {history.map((v, i) => (
                  <div key={v.version} className="text-[12px]">
                    <button
                      onClick={() => setHistOpenIdx(histOpenIdx === i ? null : i)}
                      className="flex items-center gap-2 text-ink-secondary hover:text-ink cursor-pointer w-full text-left"
                    >
                      <span className="chem-mono text-ink-muted shrink-0">v{v.version}</span>
                      <span className="truncate flex-1">
                        {v.feedback ? `意见：${v.feedback}` : String(v.content?.plan_title || '初版')}
                      </span>
                      <span className="text-ink-muted shrink-0">{v.created_at}</span>
                    </button>
                    {histOpenIdx === i && (
                      <div className="mt-1.5">
                        <LearningPlan data={{ plan: v.content }} />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    )
  }
  return (
    <div className="self-start max-w-[95%] bg-surface border border-teal/25 rounded-[var(--radius-lg)] p-3.5 animate-fade-in-up">
      <div className="text-[13px] font-semibold text-teal mb-1 flex items-center gap-2">
        <Sparkles size={14} />
        学习计划
      </div>
      <p className="text-xs text-ink-secondary m-0">
        {params.student_id ? `学生 ${String(params.student_id)} 的计划将在生成后显示` : '请告诉 Agent 要生成计划的学生'}
      </p>
    </div>
  )
}

/** 内联学生列表面板 */
function InlineStudentList({ params }: { params: Record<string, unknown> }) {
  const data = params.data as Record<string, unknown> | undefined
  const students = (data?.students as Record<string, unknown>[] | undefined) || []
  if (students.length) {
    return (
      <div className="self-start max-w-[95%] w-full bg-surface border border-teal/25 rounded-[var(--radius-lg)] shadow-[var(--shadow-md)] animate-fade-in-up p-3.5">
        <div className="text-[13px] font-semibold text-teal mb-2.5 flex items-center gap-2">
          <Sparkles size={14} />
          学生列表
        </div>
        <div className="space-y-1.5">
          {students.map((s, i) => (
            <div key={i} className="flex items-center gap-2.5 px-2.5 py-1.5 bg-surface-muted/50 rounded-[var(--radius-sm)] text-[13px]">
              <span className="w-6 h-6 rounded-full bg-primary-soft text-primary text-[11px] font-semibold flex items-center justify-center shrink-0">
                {String(s.student_name || '?').charAt(0)}
              </span>
              <span className="font-medium text-ink">{String(s.student_name || '')}</span>
              {(s.barrier_type as Record<string, number> | undefined) &&
                Object.entries(s.barrier_type as Record<string, number>)
                  .filter(([, v]) => v > 0)
                  .sort((a, b) => b[1] - a[1])
                  .slice(0, 1)
                  .map(([k, v]) => (
                    <Tag key={k} tone="amber" size="sm">
                      {k} {Math.round(v * 100)}%
                    </Tag>
                  ))}
            </div>
          ))}
        </div>
      </div>
    )
  }
  return (
    <div className="self-start max-w-[95%] bg-surface border border-teal/25 rounded-[var(--radius-lg)] p-3.5 animate-fade-in-up">
      <div className="text-[13px] font-semibold text-teal mb-1 flex items-center gap-2">
        <Sparkles size={14} />
        学生列表
      </div>
      <p className="text-xs text-ink-secondary m-0">暂无学生数据</p>
    </div>
  )
}

/** component 事件分发：内联面板（不跳页） */
export function InlinePanel({
  panelId,
  component,
  params,
}: {
  panelId: string
  component: string
  params: Record<string, unknown>
}) {
  return (
    <div data-panel={panelId} className="shrink-0">
      {component === 'exam-workbench' ? (
        <InlineExamWorkbench params={params} />
      ) : component === 'diagnosis' ? (
        <InlineDiagnosis params={params} />
      ) : component === 'learning_plan' ? (
        <InlineLearningPlan params={params} />
      ) : component === 'parent_report' ? (
        <InlineParentReport params={params} />
      ) : component === 'student-list' ? (
        <InlineStudentList params={params} />
      ) : (
        <div className="self-start max-w-[95%] bg-surface border border-teal/25 rounded-[var(--radius-lg)] p-3.5 animate-fade-in-up">
          <div className="text-[13px] font-semibold text-teal mb-1">{component}</div>
          <p className="text-xs text-ink-secondary m-0 chem-mono whitespace-pre-wrap">
            {JSON.stringify(params, null, 2)}
          </p>
        </div>
      )}
    </div>
  )
}

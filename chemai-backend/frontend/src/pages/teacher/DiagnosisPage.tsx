import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Activity,
  Search,
  ChevronDown,
  ChevronRight,
  Sparkles,
  Send,
  Trash2,
  ClipboardList,
  Loader2,
} from 'lucide-react'
import { App as AntApp, Statistic } from 'antd'
import { api } from '../../lib/api'
import { DraftGatePanel, type DraftGateState } from '../../components/chat/DraftGatePanel'
import { Button, Card, EmptyState, Input, Select, Tag, useToast } from '../../components/ui'
import { EChart, CHART_COLORS } from '../../components/ui/EChart'
import { Illo, assets } from '../../assets'

interface ExamInfo {
  record_id: string
  name: string
}

interface DiagStudent {
  student_id: string
  student_name?: string
  dominant_barrier?: string
  barrier_type?: Record<string, number>
  weak_knowledge_points?: string[]
}

interface DiagnosisResult {
  class_barrier_distribution?: { concept?: number; reading?: number; expression?: number }
  students?: DiagStudent[]
  avg_mastery?: number
}

interface StudentDetailData {
  success?: boolean
  data?: {
    student_name?: string
    barrier_type?: Record<string, number>
    dominant_barrier?: string
    weak_knowledge_points?: string[]
    recommended_intervention?: string
  }
}

interface PlanData {
  plan_title?: string
  plan_period?: string
  daily_tasks?: { day?: string; content?: string; duration?: string; resource_type?: string }[]
  weekly_goals?: { week?: string; milestone?: string }[]
  barrier_interventions?: { barrier?: string; strategy?: string; practice_tips?: string }[]
  motivation_tips?: string[]
}

const BARRIER_NAMES: Record<string, string> = {
  concept: '概念理解',
  reading: '审题障碍',
  expression: '表述障碍',
}

function loadSavedPlans(): Record<string, { student_name?: string; plan?: PlanData; generated_at?: string }> {
  try {
    return JSON.parse(localStorage.getItem('chemai_plans') || '{}')
  } catch {
    return {}
  }
}

/** 诊断分析 · Phase 2 迁移（原 pages/diagnosis.html + js/diagnosis.js） */
export function DiagnosisPage() {
  const toast = useToast()
  const { modal } = AntApp.useApp()
  const [classes, setClasses] = useState<{ class_id?: string; id?: string; name?: string; class_name?: string }[]>([])
  const [classId, setClassId] = useState('')
  const [exams, setExams] = useState<ExamInfo[]>([])
  const [examId, setExamId] = useState('')
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<DiagnosisResult | null>(null)
  const [studentKw, setStudentKw] = useState('')
  const [barrierFilter, setBarrierFilter] = useState('all')
  const [expanded, setExpanded] = useState<string | null>(null)
  const [detailData, setDetailData] = useState<StudentDetailData | null>(null)
  const [generating, setGenerating] = useState<string | null>(null)
  const [savedPlans, setSavedPlans] = useState<Record<string, { student_name?: string; plan?: PlanData; generated_at?: string }>>(loadSavedPlans)
  // #11：页面生成的草稿（发送须经三值确认门，与聊天入口同一 service 接缝）
  const [drafts, setDrafts] = useState<Record<string, DraftGateState>>({})
  const setDraft = (sid: string, d: DraftGateState | null) =>
    setDrafts((prev) => {
      const next = { ...prev }
      if (d) next[sid] = d
      else delete next[sid]
      return next
    })
  const [planPanel, setPlanPanel] = useState(false)

  /* 班级加载 + 考试联动 */
  const loadClasses = useCallback(async () => {
    try {
      const d = await api.get<{ classes?: { class_id?: string; id?: string; name?: string; class_name?: string }[] }>('/api/classes')
      const list = d.classes || []
      setClasses(list)
      if (list.length) setClassId(list[0].class_id || list[0].id || '')
    } catch {
      /* ignore */
    }
  }, [])

  useEffect(() => {
    loadClasses()
  }, [loadClasses])

  useEffect(() => {
    if (!classId) return
    setExamId('')
    setResult(null)
    setExams([])
    api
      .get<{ exams?: ExamInfo[] }>(`/api/exam/list/${classId}`)
      .then((d) => setExams(d.exams || []))
      .catch(() => setExams([]))
  }, [classId])

  /* 诊断执行 */
  async function runDiagnosis() {
    if (!classId) {
      toast.warning('请选择班级')
      return
    }
    if (!examId) {
      toast.warning('请选择考试')
      return
    }
    setRunning(true)
    setResult(null)
    setExpanded(null)
    try {
      const d = await api.get<DiagnosisResult>(`/api/diagnosis/barrier/${classId}/${examId}`)
      setResult(d)
    } catch (e) {
      toast.error(`诊断失败: ${e instanceof Error ? e.message : ''}`)
    } finally {
      setRunning(false)
    }
  }

  /* 学生详情展开 */
  async function toggleStudent(s: DiagStudent) {
    if (expanded === s.student_id) {
      setExpanded(null)
      setDetailData(null)
      return
    }
    setExpanded(s.student_id)
    setDetailData(null)
    try {
      const d = await api.get<StudentDetailData>(`/api/diagnosis/plan/${s.student_id}`)
      setDetailData(d)
    } catch {
      setDetailData({})
    }
  }

  /* 生成学习计划 → 待确认草稿（#11：发送须经三值确认门） */
  async function genPlan(s: DiagStudent) {
    setGenerating(s.student_id)
    try {
      const d = await api.post<{ success?: boolean; draft?: DraftGateState }>(
        `/api/diagnosis/learning-plan/draft/${s.student_id}`,
      )
      if (d.draft && d.draft.draft_id) {
        setDraft(s.student_id, d.draft)
        toast.success(`已为 ${s.student_name} 生成学习计划草稿（第 ${d.draft.version} 版），请确认后发送`)
      } else {
        toast.error('生成失败: 未返回有效草稿')
      }
    } catch (e) {
      toast.error(`生成失败: ${e instanceof Error ? e.message : ''}`)
    } finally {
      setGenerating(null)
    }
  }

  async function sendPlanToParent(s: DiagStudent) {
    try {
      const d = await api.post<{ success?: boolean; sent_count?: number; message?: string }>(
        `/api/diagnosis/learning-plan/send-to-parent/${s.student_id}`,
        {},
      )
      if (d.success !== false) toast.success(`已发送给 ${d.sent_count ?? 0} 位家长`)
      else toast.error(d.message || '发送失败')
    } catch (e) {
      toast.error(`发送失败: ${e instanceof Error ? e.message : ''}`)
    }
  }

  function deletePlan(sid: string) {
    modal.confirm({
      title: '删除学习计划',
      content: '确定删除该学习计划？',
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: () => {
        setSavedPlans((prev) => {
          const next = { ...prev }
          delete next[sid]
          localStorage.setItem('chemai_plans', JSON.stringify(next))
          return next
        })
      },
    })
  }

  /* 派生数据 */
  const dist = result?.class_barrier_distribution || {}
  const concept = dist.concept || 0
  const reading = dist.reading || 0
  const expression = dist.expression || 0
  const students = useMemo(() => {
    const list = [...(result?.students || [])]
    return list.sort(
      (a, b) =>
        (b.barrier_type?.[b.dominant_barrier || ''] || 0) - (a.barrier_type?.[a.dominant_barrier || ''] || 0),
    )
  }, [result])

  const filteredStudents = useMemo(() => {
    const kw = studentKw.trim().toLowerCase()
    return students.filter((s) => {
      if (kw && !(s.student_name || '').toLowerCase().includes(kw)) return false
      if (barrierFilter !== 'all' && s.dominant_barrier !== barrierFilter) return false
      return true
    })
  }, [students, studentKw, barrierFilter])

  const maxBar = Math.max(concept, reading, expression, 1)
  const bars = [
    { label: '概念理解型', val: concept, color: 'bg-primary' },
    { label: '审题障碍型', val: reading, color: 'bg-teal' },
    { label: '表述障碍型', val: expression, color: 'bg-success' },
  ]
  const dominant =
    concept >= reading && concept >= expression
      ? '概念理解型障碍占主导，建议加强基础概念教学。'
      : reading >= expression
        ? '审题障碍型占主导，建议增加题干分析训练。'
        : '表述障碍型占主导，建议强化规范化表达练习。'

  const doughnutOption = useMemo(() => {
    const counts = [concept, reading, expression]
    if (counts.every((v) => v === 0)) return null
    return {
      tooltip: { trigger: 'item' as const },
      legend: { bottom: 0, icon: 'circle', itemWidth: 8, textStyle: { color: '#5b616e', fontSize: 12 } }, // @token-allow chart(canvas)
      series: [
        {
          type: 'pie' as const,
          radius: ['55%', '75%'],
          center: ['50%', '44%'],
          itemStyle: { borderColor: '#fff', borderWidth: 2 }, // @token-allow chart(canvas)
          label: { show: true, formatter: '{c}', color: '#111318', fontWeight: 600 }, // @token-allow chart(canvas)
          data: [
            { name: '概念理解型', value: counts[0], itemStyle: { color: CHART_COLORS.doughnut[0] } },
            { name: '审题障碍型', value: counts[1], itemStyle: { color: CHART_COLORS.doughnut[1] } },
            { name: '表述障碍型', value: counts[2], itemStyle: { color: CHART_COLORS.doughnut[2] } },
          ],
        },
      ],
    }
  }, [concept, reading, expression])

  /* 计划内容渲染：有草稿 → 三值确认门面板；无草稿 → 旧计划只读回显 */
  function PlanContentView({ sid }: { sid: string }) {
    const draft = drafts[sid]
    if (draft && draft.draft_id) {
      const st = students.find((x) => x.student_id === sid)
      return (
        <div className="mt-3 animate-fade-in-up">
          <DraftGatePanel
            studentId={sid}
            draft={draft}
            onDraftChanged={(d) => setDraft(sid, d)}
            onDone={(action) => {
              if (action === 'approve') setDraft(sid, null)
            }}
          />
          {st && (
            <p className="mt-1 text-[11px] text-ink-muted m-0">
              生成者可见修订循环；发送给学生须过确认门
            </p>
          )}
        </div>
      )
    }
    const p = savedPlans[sid]
    if (!p?.plan) return null
    const plan = p.plan
    return (
      <div className="mt-3 bg-surface border border-teal/20 rounded-[var(--radius-md)] p-3.5 animate-fade-in-up">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 font-semibold text-[14px] text-ink">
            <ClipboardList size={15} className="text-teal" />
            {plan.plan_title || '个性化学习计划'}
          </div>
          <span className="text-xs text-ink-muted">周期: {plan.plan_period || '2周'}</span>
        </div>
        {plan.barrier_interventions?.length ? (
          <div className="mt-2.5">
            <div className="text-xs font-semibold text-ink-secondary mb-1">障碍干预策略</div>
            {plan.barrier_interventions.map((b, i) => (
              <div key={i} className="flex gap-2 py-1 text-[13px]">
                <Tag tone="amber" size="sm" className="shrink-0 mt-0.5">
                  {b.barrier || ''}
                </Tag>
                <span className="text-ink-secondary">
                  {b.strategy}
                  {b.practice_tips ? <span className="text-ink-muted"> · {b.practice_tips}</span> : null}
                </span>
              </div>
            ))}
          </div>
        ) : null}
        {plan.daily_tasks?.length ? (
          <div className="mt-2.5">
            <div className="text-xs font-semibold text-ink-secondary mb-1">每日任务</div>
            {plan.daily_tasks.map((t, i) => (
              <div key={i} className="flex gap-2 py-1 text-[13px]">
                <Tag tone="teal" size="sm" className="shrink-0 mt-0.5">
                  {t.day || ''}
                </Tag>
                <span className="text-ink-secondary">
                  {t.content}
                  {t.duration || t.resource_type ? (
                    <span className="text-ink-muted">
                      {' '}
                      · {t.duration || ''} {t.resource_type || ''}
                    </span>
                  ) : null}
                </span>
              </div>
            ))}
          </div>
        ) : null}
        {plan.weekly_goals?.length ? (
          <div className="mt-2.5">
            <div className="text-xs font-semibold text-ink-secondary mb-1">每周目标</div>
            {plan.weekly_goals.map((w, i) => (
              <div key={i} className="flex gap-2 py-1 text-[13px]">
                <Tag tone="blue" size="sm" className="shrink-0 mt-0.5">
                  {w.week || ''}
                </Tag>
                <span className="text-ink-secondary">里程碑: {w.milestone || ''}</span>
              </div>
            ))}
          </div>
        ) : null}
        {plan.motivation_tips?.length ? (
          <div className="flex gap-1.5 flex-wrap mt-2">
            {plan.motivation_tips.map((m, i) => (
              <Tag key={i} tone="teal" size="sm">
                {String(m)}
              </Tag>
            ))}
          </div>
        ) : null}
        <div className="flex gap-2 mt-3 flex-wrap">
          <Button size="sm" variant="ai" onClick={() => sendPlanToParent(students.find((x) => x.student_id === sid) || { student_id: sid })}>
            <Send size={13} />
            发给家长
          </Button>
          <button
            onClick={() => deletePlan(sid)}
            className="p-2 rounded-[var(--radius-sm)] text-ink-muted hover:text-error hover:bg-error-soft transition-colors cursor-pointer"
            title="删除计划"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="animate-fade-in-up">
      {/* 页头 + 选择器 */}
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div>
          <h1 className="text-[22px] font-semibold text-ink m-0">诊断分析</h1>
          <p className="mt-1 text-sm text-ink-secondary">选择班级与考试，AI 分析学习障碍并生成干预计划</p>
        </div>
        <Button
          variant="ai"
          onClick={runDiagnosis}
          loading={running}
          disabled={!classId || !examId}
        >
          <Activity size={15} />
          开始诊断
        </Button>
      </div>

      {/* 选择器 */}
      <div className="flex items-end gap-3 mb-6 flex-wrap">
        <div className="w-[200px]">
          <div className="text-[13px] font-medium text-ink-secondary mb-1.5">班级</div>
          <Select value={classId} onChange={(e) => setClassId(e.target.value)}>
            {classes.map((c) => (
              <option key={c.class_id || c.id} value={c.class_id || c.id}>
                {c.name || c.class_name || ''}
              </option>
            ))}
          </Select>
        </div>
        <div className="w-[220px]">
          <div className="text-[13px] font-medium text-ink-secondary mb-1.5">考试</div>
          <Select value={examId} onChange={(e) => setExamId(e.target.value)}>
            <option value="">选择考试…</option>
            {exams.map((e) => (
              <option key={e.record_id} value={e.record_id}>
                {e.name}
              </option>
            ))}
          </Select>
        </div>
        {exams.length === 0 && <span className="text-xs text-ink-muted mb-2.5">该班级暂无考试记录</span>}
      </div>

      {!result && !running ? (
        <div className="bg-surface border border-border rounded-[var(--radius-lg)]">
          <EmptyState
            illustration={<Illo src={assets.emptyClass} />}
            title="尚未执行诊断"
            description="选择班级与考试后点击「开始诊断」，系统将分析全班学生的障碍分布"
            action={
              <Button variant="ai" onClick={runDiagnosis} disabled={!classId || !examId}>
                <Activity size={15} />
                开始诊断
              </Button>
            }
          />
        </div>
      ) : null}

      {running ? (
        <Card>
          <div className="flex items-center gap-3 py-8 justify-center text-ink-secondary">
            <Loader2 size={20} className="animate-spin text-teal" />
            诊断中，正在分析学生作答数据…
          </div>
        </Card>
      ) : null}

      {result ? (
        <div className="space-y-5">
          {/* 概览（antd Statistic，2026-08 第二轮） */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-surface border border-border rounded-[var(--radius-lg)] p-4">
              <Statistic
                title={<span className="text-[13px] text-ink-secondary">诊断学生</span>}
                value={result.students?.length || 0}
                prefix={<Activity size={16} className="text-teal mr-1" />}
              />
            </div>
            <div className="bg-surface border border-border rounded-[var(--radius-lg)] p-4">
              <Statistic
                title={<span className="text-[13px] text-ink-secondary">班级平均掌握度</span>}
                value={Math.round((result.avg_mastery || 0) * 100)}
                suffix="%"
                prefix={<Activity size={16} className="text-success mr-1" />}
                styles={{ content: { color: 'var(--color-success)' } }}
              />
            </div>
            <div className="bg-surface border border-border rounded-[var(--radius-lg)] p-4">
              <Statistic
                title={<span className="text-[13px] text-ink-secondary">需关注学生合计</span>}
                value={concept + reading + expression}
                prefix={<Activity size={16} className="text-warning mr-1" />}
                styles={{ content: (concept + reading + expression) > 0 ? { color: 'var(--color-warning)' } : undefined }}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            {/* 障碍分布条形图 */}
            <Card title="班级障碍分布">
              <div className="flex items-end gap-6 h-[150px] px-2 py-2">
                {bars.map((b) => (
                  <div key={b.label} className="flex-1 flex flex-col items-center gap-1.5">
                    <span className="font-bold text-base text-ink">{b.val}</span>
                    <div className="flex-1 w-full max-w-[64px] bg-surface-muted rounded-t-[6px] relative overflow-hidden">
                      <div
                        className={`absolute bottom-0 w-full rounded-t-[6px] transition-all duration-500 ${b.color}`}
                        style={{ height: `${Math.max(Math.round((b.val / maxBar) * 100), 4)}%` }}
                      />
                    </div>
                    <span className="text-[11px] text-ink-secondary">{b.label}</span>
                  </div>
                ))}
              </div>
              <p className="text-xs text-ink-secondary mt-2">{dominant}</p>
            </Card>

            {/* 环形图 */}
            <Card title="障碍类型占比" flush>
              {doughnutOption ? (
                <div className="p-3">
                  <EChart option={doughnutOption} height={240} />
                </div>
              ) : (
                <EmptyState illustration={<Illo src={assets.emptyClass} width={160} />} title="暂无诊断数据" />
              )}
            </Card>
          </div>

          {/* 学生列表 */}
          <Card
            title={`需关注学生（${students.length} 人）`}
            action={
              <div className="flex items-center gap-2">
                <div className="relative">
                  <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-muted" />
                  <Input
                    value={studentKw}
                    onChange={(e) => setStudentKw(e.target.value)}
                    placeholder="搜索学生姓名…"
                    className="pl-7 h-8 w-[170px] text-[13px]"
                  />
                </div>
                <Select
                  value={barrierFilter}
                  onChange={(e) => setBarrierFilter(e.target.value)}
                  className="h-8 w-[130px] text-[13px]"
                >
                  <option value="all">全部类型</option>
                  <option value="concept">概念理解型</option>
                  <option value="reading">审题障碍型</option>
                  <option value="expression">表述障碍型</option>
                </Select>
              </div>
            }
            flush
          >
            {filteredStudents.length === 0 ? (
              <EmptyState title="暂无匹配学生" description="调整搜索或筛选条件" />
            ) : (
              <div>
                {filteredStudents.map((s) => {
                  const bt = s.barrier_type || {}
                  const dominantBarrier = s.dominant_barrier || 'concept'
                  const pct = Math.round((bt[dominantBarrier] || 0) * 100)
                  const severity = pct >= 60 ? 'bg-error' : pct >= 40 ? 'bg-warning' : 'bg-success'
                  const isOpen = expanded === s.student_id
                  return (
                    <div key={s.student_id} className="border-b border-border last:border-b-0">
                      <button
                        onClick={() => toggleStudent(s)}
                        className={`w-full flex items-center gap-3 px-4 py-3 text-left transition-colors cursor-pointer ${
                          isOpen ? 'bg-surface-muted/60' : 'hover:bg-surface-muted/40'
                        }`}
                      >
                        <span className={`w-2 h-2 rounded-full shrink-0 ${severity}`} />
                        <span className="flex-1 min-w-0">
                          <span className="font-medium text-[14px] text-ink">{s.student_name || ''}</span>
                          <Tag
                            tone={dominantBarrier === 'concept' ? 'blue' : dominantBarrier === 'reading' ? 'amber' : 'teal'}
                            size="sm"
                            className="ml-2"
                          >
                            {BARRIER_NAMES[dominantBarrier] || dominantBarrier} {pct}%
                          </Tag>
                        </span>
                        <span className="text-xs text-ink-muted shrink-0">
                          {(s.weak_knowledge_points || []).length} 弱知识点
                        </span>
                        {isOpen ? (
                          <ChevronDown size={16} className="text-ink-muted shrink-0" />
                        ) : (
                          <ChevronRight size={16} className="text-ink-muted shrink-0" />
                        )}
                      </button>

                      {isOpen && (
                        <div className="px-4 pb-4 animate-fade-in-up">
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                              <div className="text-xs font-semibold text-ink mb-2">障碍置信度分布</div>
                              {(['concept', 'reading', 'expression'] as const).map((k) => {
                                const val = (detailData?.data?.barrier_type || bt)[k] || 0
                                return (
                                  <div key={k} className="flex items-center gap-2 mb-1.5">
                                    <span className="text-xs text-ink-secondary w-[76px] shrink-0">
                                      {BARRIER_NAMES[k]}
                                    </span>
                                    <div className="flex-1 h-2 bg-surface-muted rounded-full overflow-hidden">
                                      <div
                                        className="h-full rounded-full bg-teal transition-all duration-500"
                                        style={{ width: `${Math.round(val * 100)}%` }}
                                      />
                                    </div>
                                    <span className="text-xs chem-mono text-ink-secondary w-[34px] text-right">
                                      {Math.round(val * 100)}%
                                    </span>
                                  </div>
                                )
                              })}
                            </div>
                            <div>
                              <div className="text-xs font-semibold text-ink mb-2">薄弱知识点</div>
                              <div className="flex gap-1.5 flex-wrap">
                                {detailData?.data?.weak_knowledge_points?.length ? (
                                  detailData.data.weak_knowledge_points.map((k) => (
                                    <Tag key={k} tone="gray" size="sm">
                                      {k}
                                    </Tag>
                                  ))
                                ) : (
                                  <span className="text-xs text-ink-muted">暂无数据</span>
                                )}
                              </div>
                              <div className="text-xs font-semibold text-ink mt-3 mb-1">干预建议</div>
                              <p className="text-[13px] text-ink-secondary m-0">
                                {detailData?.data?.recommended_intervention || '—'}
                              </p>
                            </div>
                          </div>
                          <div className="flex gap-2 mt-3 flex-wrap">
                            <Button size="sm" variant="ai" loading={generating === s.student_id} onClick={() => genPlan(s)}>
                              <Sparkles size={13} />
                              生成学习计划
                            </Button>
                            {savedPlans[s.student_id] && (
                              <Button size="sm" variant="secondary" onClick={() => setPlanPanel(true)}>
                                <ClipboardList size={13} />
                                查看计划
                              </Button>
                            )}
                          </div>
                          {savedPlans[s.student_id] && <PlanContentView sid={s.student_id} />}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </Card>
        </div>
      ) : null}

      {/* 已生成计划面板 */}
      <div className="mt-5">
        <Button variant="ghost" size="sm" onClick={() => setPlanPanel((v) => !v)}>
          <ClipboardList size={14} />
          已生成计划（{Object.keys(savedPlans).length}）
          {planPanel ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </Button>
        {planPanel && (
          <div className="mt-2 space-y-2">
            {Object.keys(savedPlans).length === 0 ? (
              <Card>
                <EmptyState title="暂无已生成的学习计划" description="展开学生详情生成计划后会显示在这里" />
              </Card>
            ) : (
              Object.entries(savedPlans).map(([sid, p]) => (
                <Card key={sid} padding="p-3.5" hoverable>
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm font-medium text-ink">{p.student_name || sid}</div>
                      <div className="text-xs text-ink-muted mt-0.5">{p.generated_at || ''}</div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => deletePlan(sid)}
                        className="p-2 rounded-[var(--radius-sm)] text-ink-muted hover:text-error hover:bg-error-soft transition-colors cursor-pointer"
                        title="删除计划"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                </Card>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  )
}

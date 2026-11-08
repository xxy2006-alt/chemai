import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Search,
  UserPlus,
  RefreshCw,
  KeyRound,
  CalendarClock,
  ClipboardList,
  Send,
  Copy,
  Check,
  ArrowLeftRight,
  History,
  Sparkles,
  TrendingUp,
} from 'lucide-react'
import { App as AntApp, Drawer as AntDrawer, Input as AntInput, Progress, Select as AntSelect, Statistic, Table as AntTable, Tag as AntTag, type TableColumnsType } from 'antd'
import { api } from '../../lib/api'
import { sortStudentsForDisplay } from '../../lib/student-utils'
import { Button, EmptyState, Input, Modal, Select, StatCard, useToast } from '../../components/ui'
import { Illo, assets } from '../../assets'
import { DraftGatePanel, type DraftGateState } from '../../components/chat/DraftGatePanel'

/* ── 类型 ── */

interface Student {
  student_id?: string
  id?: string
  name?: string
  class_id?: string
  class_name?: string
  barrier_type?: Record<string, number>
  weak_knowledge_points?: string[]
  weak_kps?: string[]
  exercises_completed?: number
  last_exercise_at?: string
  created_at?: string
  updated_at?: string
  accuracy?: number
  status?: string
}

interface StudentDetail {
  success?: boolean
  weak_knowledge_points?: string[]
  recent_activity?: { date?: string; desc?: string; is_correct?: boolean }[]
}

interface PlanData {
  plan_title?: string
  plan_period?: string
  daily_tasks?: ({ day?: string; task?: string } | string)[]
  weekly_goals?: (string | Record<string, unknown>)[]
  barrier_interventions?: Record<string, string>
  motivation_tips?: string[]
  raw_text?: string
}

interface PlanHistoryItem {
  plan_title?: string
  created_at?: string
  plan_data?: PlanData
}

const BARRIER_LABELS: Record<string, string> = { concept: '概念', reading: '审题', expression: '表述' }
const PAGE_SIZE = 12
const PLAN_TIPS = [
  '正在分析学生的学习特点…',
  '根据障碍类型匹配教学策略…',
  '生成个性化周目标和每日任务…',
  '设计针对性干预方案…',
  '准备激励建议…',
  '整理薄弱知识点强化路径…',
  '结合最近发展区理论优化难度…',
]

function topBarrier(s: Student): { key: string; pct: number } {
  const bt = s.barrier_type || {}
  const entries = Object.entries(bt).filter(([, v]) => v > 0)
  if (!entries.length) return { key: '', pct: 0 }
  const top = entries.sort((a, b) => b[1] - a[1])[0]
  return { key: top[0], pct: Math.round(top[1] * 100) }
}

function studentId(s: Student): string {
  return s.student_id || s.id || ''
}

/** 学生管理 · Phase 2 迁移（原 pages/students.html + js/students.js） */
export function StudentsPage() {
  const toast = useToast()
  const { modal } = AntApp.useApp()
  const [classes, setClasses] = useState<{ class_id?: string; id?: string; name?: string; class_name?: string }[]>([])
  const [students, setStudents] = useState<Student[]>([])
  const [kw, setKw] = useState('')
  const [clsFilter, setClsFilter] = useState<string | undefined>(undefined)
  const [barrierFilter, setBarrierFilter] = useState<string | undefined>(undefined)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)

  // Drawer
  const [drawerStudent, setDrawerStudent] = useState<Student | null>(null)
  const [detail, setDetail] = useState<StudentDetail | null>(null)

  // 添加学生
  const [addOpen, setAddOpen] = useState(false)
  const [addTab, setAddTab] = useState<'manual' | 'invite'>('manual')
  const [addName, setAddName] = useState('')
  const [addClass, setAddClass] = useState('')
  const [inviteClass, setInviteClass] = useState('')
  const [inviteCode, setInviteCode] = useState('')
  const [copied, setCopied] = useState(false)

  // 转班
  const [transferOpen, setTransferOpen] = useState(false)
  const [transferClass, setTransferClass] = useState('')

  // 学习计划（#11：生成走草稿流，发送须过三值确认门）
  const [planModal, setPlanModal] = useState<
    null | { mode: 'generating' } | { mode: 'view'; plan: PlanData } | { mode: 'draft'; draft: DraftGateState }
  >(null)
  const [historyModal, setHistoryModal] = useState(false)
  const [planHistory, setPlanHistory] = useState<PlanHistoryItem[]>([])
  const [planTipIdx, setPlanTipIdx] = useState(0)
  const [activeDraft, setActiveDraft] = useState<DraftGateState | null>(null)

  /* ── 数据加载 ── */
  const loadAll = useCallback(async () => {
    setLoading(true)
    try {
      type ClassInfo = { class_id?: string; id?: string; name?: string; class_name?: string }
      const [cData, sData] = await Promise.all([
        api
          .get<{ classes?: ClassInfo[]; data?: { classes?: ClassInfo[] } }>('/api/classes')
          .catch(() => ({ classes: [], data: undefined }) as { classes?: ClassInfo[]; data?: { classes?: ClassInfo[] } }),
        api.get<{ students?: Student[] } | Student[]>('/api/users/students').catch(() => ({ students: [] })),
      ])
      const clist = cData.classes || cData.data?.classes || []
      if (clist.length) setClasses(clist)
      const slist = Array.isArray(sData) ? sData : sData.students || []
      setStudents(slist)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadAll()
    // 来自 Agent 的跳转（旧版行为恢复）：navigate params {focus: 学号, action: 'plan'}
    // → 自动打开学生抽屉；action=plan → 自动生成学习方案（用户点确认发送）
    const navParamsRaw = sessionStorage.getItem('chemai_navigate_params')
    if (navParamsRaw) {
      sessionStorage.removeItem('chemai_navigate_params')
      try {
        const navParams = JSON.parse(navParamsRaw) as { focus?: string; action?: string }
        const focusId = navParams.focus || sessionStorage.getItem('chemai_focus_student')
        if (focusId) {
          sessionStorage.removeItem('chemai_focus_student')
          window.setTimeout(() => {
            setStudents((prev) => {
              const s = prev.find((x) => studentId(x) === focusId)
              if (s) {
                setDrawerStudent(s)
                loadDetail(s)
                if (navParams.action === 'plan') {
                  window.setTimeout(() => genPlan(s), 400)
                }
              }
              return prev
            })
          }, 600)
        }
      } catch {
        /* ignore */
      }
    }
    // 来自学情面板的跳转（chemai_focus_student）
    const focusId2 = sessionStorage.getItem('chemai_focus_student')
    if (focusId2) {
      sessionStorage.removeItem('chemai_focus_student')
      window.setTimeout(() => {
        setStudents((prev) => {
          const s = prev.find((x) => studentId(x) === focusId2)
          if (s) {
            setDrawerStudent(s)
            loadDetail(s)
          }
          return prev
        })
      }, 600)
    }
  }, [loadAll])

  // #11：抽屉打开即回显该生活跃草稿（跨入口同一扇门）
  useEffect(() => {
    if (!drawerStudent) return
    let alive = true
    api.get<{ success?: boolean; draft?: DraftGateState | null }>(
      `/api/diagnosis/learning-plan/draft/${studentId(drawerStudent)}/active`,
    ).then((d) => {
      if (alive) setActiveDraft(d.draft && d.draft.draft_id ? d.draft : null)
    }).catch(() => {
      if (alive) setActiveDraft(null)
    })
    return () => {
      alive = false
    }
  }, [drawerStudent])

  const loadDetail = useCallback(async (s: Student) => {
    setDetail(null)
    try {
      const d = await api.get<StudentDetail>(`/api/users/student/${studentId(s)}/detail`)
      setDetail(d)
    } catch {
      setDetail({})
    }
  }, [])

  /* ── 统计 ── */
  const stats = useMemo(() => {
    const total = students.length
    const active30 = students.filter((s) => {
      const d = s.last_exercise_at || s.created_at || ''
      if (!d) return false
      return (Date.now() - new Date(d).getTime()) / 86400000 <= 30
    }).length
    const attention = students.filter((s) => {
      const bt = s.barrier_type || {}
      return Object.values(bt).some((v) => (v || 0) > 0.6)
    }).length
    const avgEx = total ? Math.round(students.reduce((sum, s) => sum + (s.exercises_completed || 0), 0) / total) : 0
    return { total, active30, attention, avgEx }
  }, [students])

  /* ── 筛选 + 分页 ── */
  // 排序（纯函数，evals 锁定）：演示学生 202610201（李世睿）置顶，其余按练习数降序。
  // 2026-08-14 用户反馈「李世睿直接没了」：分页 12 人/页时她在第 3 页首屏看不到。
  const sorted = useMemo(() => sortStudentsForDisplay(students), [students])

  const filtered = useMemo(() => {
    const keyword = kw.trim().toLowerCase()
    return sorted.filter((s) => {
      if (keyword && !(s.name || '').toLowerCase().includes(keyword) && !studentId(s).toLowerCase().includes(keyword))
        return false
      if (clsFilter && (s.class_id || '') !== clsFilter) return false
      if (barrierFilter && topBarrier(s).key !== barrierFilter) return false
      return true
    })
  }, [sorted, kw, clsFilter, barrierFilter])

  // ⚠️ 2026-09-14 修：这里原先把 filtered 手动切成当前页再交给 antd，而 antd 的
  // pagination 又对这份「已切好的 12 行」再分一次页 → 永远只有 1 页、总数显示 12，
  // 后面 28 个学生翻不到（2419 班 40 人只看得见 12 个）。
  // 分页交给 antd：dataSource 传完整 filtered，页码由 pagination 控制。

  useEffect(() => {
    setPage(1)
  }, [kw, clsFilter, barrierFilter])

  /* ── 学生表格列（antd Table，2026-08 antd 接入） ── */
  const columns = useMemo<TableColumnsType<Student>>(
    () => [
      {
        title: '学生',
        key: 'name',
        width: 190,
        render: (_, s) => (
          <div className="flex items-center gap-2.5">
            <span className="w-8 h-8 rounded-full bg-primary-soft text-primary text-[13px] font-semibold flex items-center justify-center shrink-0">
              {(s.name || '?').charAt(0)}
            </span>
            <div className="min-w-0">
              <div className="text-[13px] font-medium text-ink truncate">{s.name || ''}</div>
              <div className="text-[11px] text-ink-muted truncate">{studentId(s)}</div>
            </div>
          </div>
        ),
      },
      {
        title: '班级',
        key: 'class',
        width: 110,
        render: (_, s) => (
          <span className="text-xs text-ink-secondary">{s.class_name || s.class_id || '—'}</span>
        ),
      },
      {
        title: '主导障碍',
        key: 'barrier',
        width: 150,
        render: (_, s) => {
          const top = topBarrier(s)
          if (!top.key) return <span className="text-xs text-ink-muted">未诊断</span>
          const color = top.key === 'concept' ? 'blue' : top.key === 'reading' ? 'orange' : 'green'
          return (
            <AntTag color={color} className="m-0">
              {BARRIER_LABELS[top.key]} {top.pct}%
            </AntTag>
          )
        },
      },
      {
        title: '练习次数',
        dataIndex: 'exercises_completed',
        key: 'ex',
        width: 90,
        render: (v: number) => <span className="text-xs text-ink-secondary">{v || 0}</span>,
      },
      {
        title: '正确率',
        key: 'acc',
        width: 90,
        render: (_, s) => {
          const acc = s.accuracy
          if (acc === undefined || acc === null) return <span className="text-xs text-ink-muted">—</span>
          const color = acc >= 0.7 ? 'text-success' : acc >= 0.5 ? 'text-primary' : 'text-error'
          return <span className={`text-xs font-medium ${color}`}>{Math.round(acc * 100)}%</span>
        },
      },
      {
        title: '最后活跃',
        key: 'last',
        width: 120,
        render: (_, s) => (
          <span className="text-xs text-ink-muted">
            {(s.last_exercise_at || s.created_at || '').slice(0, 10) || '—'}
          </span>
        ),
      },
    ],
    [],
  )

  /* ── 添加学生 ── */
  async function submitAddStudent() {
    if (!addName.trim()) {
      toast.warning('请输入姓名')
      return
    }
    if (!addClass) {
      toast.warning('请选择班级')
      return
    }
    try {
      const d = await api.post<{ success?: boolean; message?: string }>('/api/users/student', {
        name: addName.trim(),
        class_id: addClass,
      })
      if (d.success !== false) {
        toast.success('已添加学生')
        setAddOpen(false)
        setAddName('')
        setAddClass('')
        loadAll()
      } else {
        toast.error(d.message || '添加失败')
      }
    } catch (e) {
      toast.error(`添加失败: ${e instanceof Error ? e.message : ''}`)
    }
  }

  async function generateInviteCode() {
    if (!inviteClass) {
      toast.warning('请选择班级')
      return
    }
    try {
      const d = await api.post<{ invite_code?: string; data?: { invite_code?: string } }>('/api/users/student', {
        class_id: inviteClass,
        role: 'student',
        via_invite: true,
      })
      const code = d.invite_code || d.data?.invite_code || localFallbackCode(inviteClass)
      setInviteCode(code)
    } catch {
      setInviteCode(localFallbackCode(inviteClass))
    }
  }

  function localFallbackCode(cls: string): string {
    return (
      cls.replace(/[^a-zA-Z0-9]/g, '').slice(0, 4).toUpperCase() +
      '-' +
      Math.random().toString(36).slice(2, 8).toUpperCase()
    )
  }

  async function copyInviteCode() {
    if (!inviteCode) return
    try {
      await navigator.clipboard.writeText(inviteCode)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      toast.error('复制失败，请手动复制')
    }
  }

  /* ── 转班 ── */
  async function confirmTransfer() {
    if (!transferClass) {
      toast.warning('请选择目标班级')
      return
    }
    if (!drawerStudent) return
    try {
      const d = await api.post<{ success?: boolean; message?: string }>(
        `/api/users/student/${studentId(drawerStudent)}/transfer`,
        { new_class_id: transferClass },
      )
      if (d.success !== false) {
        toast.success('转班成功')
        setTransferOpen(false)
        setDrawerStudent(null)
        loadAll()
      } else {
        toast.error(d.message || '转班失败')
      }
    } catch (e) {
      toast.error(`转班失败: ${e instanceof Error ? e.message : ''}`)
    }
  }

  /* ── 重置密码 ── */
  async function resetPassword() {
    if (!drawerStudent) return
    modal.confirm({
      title: '重置密码',
      content: `确定将 ${drawerStudent.name} 的密码重置为默认密码 123456？`,
      okText: '重置',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: async () => {
        try {
          const d = await api.post<{ message?: string }>(`/api/users/student/${studentId(drawerStudent)}/reset-password`)
          toast.success(d.message || '已重置')
        } catch (e) {
          toast.error(`重置失败: ${e instanceof Error ? e.message : ''}`)
        }
      },
    })
  }

  /* ── 学习计划 ── */
  async function genPlan(forStudent?: Student) {
    const s = forStudent || drawerStudent
    if (!s) return
    setPlanTipIdx(0)
    setPlanModal({ mode: 'generating' })
    try {
      // #11：与聊天入口同一 service——生成待确认草稿（regenerate 作废旧活跃草稿），
      // 发送须经三值确认门；旧 generate 直发端点不再被页面调用
      const d = await api.post<{ success?: boolean; draft?: DraftGateState }>(
        `/api/diagnosis/learning-plan/draft/${studentId(s)}`,
      )
      if (d.draft && d.draft.draft_id) {
        setActiveDraft(d.draft)
        setPlanModal({ mode: 'draft', draft: d.draft })
      } else {
        toast.error('生成失败: 未返回有效草稿')
        setPlanModal(null)
      }
    } catch (e) {
      toast.error(`生成失败: ${e instanceof Error ? e.message : ''}`)
      setPlanModal(null)
    }
  }

  async function sendPlan() {
    if (!drawerStudent || planModal?.mode !== 'view') return
    try {
      const d = await api.post<{ success?: boolean; message?: string; student_name?: string }>(
        `/api/diagnosis/learning-plan/apply/${studentId(drawerStudent)}`,
        planModal.plan,
      )
      if (d.success !== false) {
        toast.success(`已发送给 ${d.student_name || drawerStudent.name}`)
      } else {
        toast.error(d.message || '发送失败')
      }
    } catch (e) {
      toast.error(`发送失败: ${e instanceof Error ? e.message : ''}`)
    }
  }

  async function showPlanHistory() {
    if (!drawerStudent) return
    setPlanHistory([])
    setHistoryModal(true)
    try {
      const d = await api.get<{ success?: boolean; history?: PlanHistoryItem[] }>(
        `/api/diagnosis/learning-plan/${studentId(drawerStudent)}/history`,
      )
      setPlanHistory(d.history || [])
    } catch {
      setPlanHistory([])
    }
  }

  /* ── 迷你趋势（SVG sparkline，轻量替代 Chart.js） ── */
  const sparkline = useMemo(() => {
    const activities = detail?.recent_activity || []
    const reversed = [...activities].reverse()
    let correct = 0
    let total = 0
    const scores: number[] = []
    const labels: string[] = []
    for (const a of reversed) {
      total++
      if (a.is_correct) correct++
      scores.push(total > 0 ? Math.round((correct / total) * 100) : 0)
      labels.push(a.date || '')
    }
    if (!scores.length) {
      return { scores: [Math.round((drawerStudent?.accuracy || 0) * 100)], labels: ['当前'] }
    }
    return { scores, labels }
  }, [detail, drawerStudent])

  function Sparkline({ scores }: { scores: number[] }) {
    const w = 260
    const h = 56
    const max = Math.max(...scores, 60)
    const min = Math.min(...scores)
    const pts = scores
      .map((v, i) => {
        const x = scores.length > 1 ? (i / (scores.length - 1)) * w : w / 2
        const y = h - ((v - min) / Math.max(max - min, 1)) * h
        return `${x.toFixed(1)},${y.toFixed(1)}`
      })
      .join(' ')
    return (
      <svg width="100%" height={h} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className="block">
        <polyline points={pts} fill="none" stroke="#0d7377" strokeWidth="2" strokeLinejoin="round" />{/* @token-allow chart(canvas) */}
        <circle
          cx={scores.length > 1 ? w : w / 2}
          cy={h - ((scores[scores.length - 1] - min) / Math.max(max - min, 1)) * h}
          r="3"
          fill="#b43c28" data-token-allow="chart" // @token-allow chart(canvas)
        />
      </svg>
    )
  }

  /* ── 渲染 ── */
  return (
    <div className="animate-fade-in-up">
      {/* 页头 */}
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div>
          <h1 className="text-[22px] font-semibold text-ink m-0">学生管理</h1>
          <p className="mt-1 text-sm text-ink-secondary">学生档案 · 障碍诊断 · 个性化学习计划</p>
        </div>
        <Button onClick={() => setAddOpen(true)}>
          <UserPlus size={15} />
          添加学生
        </Button>
      </div>

      {/* 统计条 */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4 mb-5">
        <StatCard label="总人数" value={stats.total} />
        <StatCard label="近期活跃（30 天）" value={stats.active30} tone="ok" />
        <StatCard label="需关注" value={stats.attention} tone={stats.attention > 0 ? 'warn' : 'normal'} />
        <StatCard label="人均练习" value={stats.avgEx} />
      </div>

      {/* 工具栏 */}
      <div className="flex items-center gap-3 mb-5 flex-wrap">
        <AntInput
          value={kw}
          onChange={(e) => setKw(e.target.value)}
          placeholder="搜索姓名 / 学号…"
          allowClear
          prefix={<Search size={14} className="text-ink-muted" />}
          className="w-[220px]"
        />
        <AntSelect
          value={clsFilter}
          onChange={setClsFilter}
          placeholder="全部班级"
          allowClear
          className="w-[170px]"
          options={classes.map((c) => ({
            value: c.class_id || c.id || '',
            label: c.name || c.class_name || '',
          }))}
        />
        <AntSelect
          value={barrierFilter}
          onChange={setBarrierFilter}
          placeholder="全部障碍类型"
          allowClear
          className="w-[170px]"
          options={[
            { value: 'concept', label: '概念理解型' },
            { value: 'reading', label: '审题障碍型' },
            { value: 'expression', label: '表述障碍型' },
          ]}
        />
        <span className="ml-auto text-xs text-ink-muted">共 {filtered.length} 名学生</span>
      </div>

      {/* 学生表格（antd Table，2026-08 antd 接入；排序沿用演示学生置顶） */}
      <AntTable<Student>
        rowKey={(s) => studentId(s)}
        loading={loading}
        dataSource={filtered}
        size="middle"
        pagination={{
          current: page,
          pageSize: PAGE_SIZE,
          onChange: (p) => setPage(p),
          showTotal: (t) => `共 ${t} 名学生`,
          showSizeChanger: false,
        }}
        onRow={(s) => ({
          onClick: () => {
            setDrawerStudent(s)
            loadDetail(s)
          },
          className: 'cursor-pointer',
        })}
        locale={{
          emptyText: (
            <EmptyState
              illustration={<Illo src={assets.emptyStudents} />}
              title="暂无匹配学生"
              description="调整筛选条件，或点击右上角添加学生"
              action={
                <Button size="sm" onClick={() => setAddOpen(true)}>
                  <UserPlus size={14} />
                  添加学生
                </Button>
              }
            />
          ),
        }}
        columns={columns}
      />

      {/* ── 学生详情 Drawer（antd，2026-08 接入） ── */}
      <AntDrawer
        open={!!drawerStudent}
        onClose={() => setDrawerStudent(null)}
        size={440}
        styles={{ body: { padding: 0 } }}
      >
        {drawerStudent && (
          <div className="h-full flex flex-col">
            <div className="flex items-center justify-between px-5 py-4 border-b border-border">
              <div className="flex items-center gap-3">
                <span className="w-10 h-10 rounded-full bg-primary-soft text-primary text-base font-semibold flex items-center justify-center">
                  {(drawerStudent.name || '?').charAt(0)}
                </span>
                <div>
                  <div className="text-[15px] font-semibold text-ink">{drawerStudent.name || ''}</div>
                  <div className="text-xs text-ink-muted">
                    {drawerStudent.class_name || drawerStudent.class_id || ''} · {studentId(drawerStudent)}
                  </div>
                </div>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto px-5 py-4">
              {/* 操作按钮 */}
              <div className="grid grid-cols-2 gap-2 mb-5">
                <Button variant="secondary" size="sm" onClick={() => setTransferOpen(true)}>
                  <ArrowLeftRight size={13} />
                  转班
                </Button>
                <Button variant="secondary" size="sm" onClick={resetPassword}>
                  <KeyRound size={13} />
                  重置密码
                </Button>
                {activeDraft && activeDraft.draft_id ? (
                  <Button variant="ai" size="sm" onClick={() => setPlanModal({ mode: 'draft', draft: activeDraft })}>
                    <Sparkles size={13} />
                    继续处理待确认计划（v{activeDraft.version}）
                  </Button>
                ) : null}
                <Button variant="ai" size="sm" onClick={() => genPlan()}>
                  <Sparkles size={13} />
                  生成学习计划
                </Button>
                <Button variant="secondary" size="sm" onClick={showPlanHistory}>
                  <History size={13} />
                  历史计划
                </Button>
              </div>

              {/* 学习统计（antd Statistic） */}
              <div className="mb-5">
                <div className="text-xs font-semibold text-ink mb-2">学习统计</div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-surface-muted/70 rounded-[var(--radius-md)] p-3 text-center">
                    <Statistic
                      value={drawerStudent.exercises_completed || 0}
                      suffix="次"
                      styles={{ content: { fontSize: 18, fontWeight: 600, color: 'var(--color-text)' } }}
                    />
                    <div className="text-[11px] text-ink-muted mt-1">练习次数</div>
                  </div>
                  <div className="bg-surface-muted/70 rounded-[var(--radius-md)] p-3 text-center">
                    <Statistic
                      value={drawerStudent.accuracy ? Math.round(drawerStudent.accuracy * 100) : 0}
                      suffix="%"
                      precision={0}
                      styles={{
                        content: {
                          fontSize: 18,
                          fontWeight: 600,
                          color: drawerStudent.accuracy
                            ? drawerStudent.accuracy >= 0.7
                              ? 'var(--color-success)'
                              : drawerStudent.accuracy >= 0.5
                                ? 'var(--color-primary)'
                                : 'var(--color-error)'
                            : 'var(--color-ink-muted)',
                        },
                      }}
                    />
                    <div className="text-[11px] text-ink-muted mt-1">平均正确率</div>
                  </div>
                  <div className="bg-surface-muted/70 rounded-[var(--radius-md)] p-3 text-center">
                    <Statistic
                      value={
                        drawerStudent.exercises_completed
                          ? drawerStudent.accuracy && drawerStudent.accuracy > 0.6
                            ? '↗'
                            : drawerStudent.accuracy && drawerStudent.accuracy > 0.4
                              ? '→'
                              : '↘'
                          : '--'
                      }
                      styles={{ content: { fontSize: 18, fontWeight: 600, color: 'var(--color-text)' } }}
                    />
                    <div className="text-[11px] text-ink-muted mt-1">近势</div>
                  </div>
                  <div className="bg-surface-muted/70 rounded-[var(--radius-md)] p-3 text-center">
                    <Statistic
                      value={(drawerStudent.last_exercise_at || drawerStudent.created_at || '').slice(0, 10) || '—'}
                      styles={{ content: { fontSize: 15, fontWeight: 600, color: 'var(--color-text)' } }}
                    />
                    <div className="text-[11px] text-ink-muted mt-1">最后活跃</div>
                  </div>
                </div>
              </div>

              {/* 障碍诊断（antd Progress） */}
              <div className="mb-5">
                <div className="text-xs font-semibold text-ink mb-2">障碍诊断</div>
                {(['concept', 'reading', 'expression'] as const).map((k) => {
                  const val = drawerStudent.barrier_type?.[k] || 0
                    const strokeColor = { concept: 'var(--color-primary)', reading: 'var(--color-teal)', expression: 'var(--color-success)' }[k]
                  return (
                    <div key={k} className="mb-1.5">
                      <div className="flex justify-between text-xs mb-0.5">
                        <span className="text-ink-secondary">{BARRIER_LABELS[k]}理解型</span>
                        <span className="text-ink-secondary chem-mono">{Math.round(val * 100)}%</span>
                      </div>
                      <Progress
                        percent={Math.round(val * 100)}
                        strokeColor={strokeColor}
                        trailColor="var(--color-surface-muted)"
                        size="small"
                        format={() => ''}
                      />
                    </div>
                  )
                })}
              </div>

              {/* 成绩趋势 */}
              <div className="mb-5">
                <div className="text-xs font-semibold text-ink mb-2 flex items-center gap-1.5">
                  <TrendingUp size={13} />
                  成绩趋势
                </div>
                <div className="bg-surface-muted/50 rounded-[var(--radius-md)] p-3">
                  <Sparkline scores={sparkline.scores} />
                  <div className="flex justify-between mt-1 text-[10px] text-ink-muted">
                    <span>{sparkline.labels[0] || ''}</span>
                    <span>{sparkline.labels[sparkline.labels.length - 1] || ''}</span>
                  </div>
                </div>
              </div>

              {/* 薄弱知识点 */}
              <div className="mb-5">
                <div className="text-xs font-semibold text-ink mb-2">薄弱知识点</div>
                <div className="flex gap-1.5 flex-wrap">
                  {detail?.weak_knowledge_points?.length ? (
                    detail.weak_knowledge_points.map((k) => (
                      <AntTag key={k} color="default" className="m-0">
                        {k}
                      </AntTag>
                    ))
                  ) : (
                    <span className="text-xs text-ink-muted">暂无数据</span>
                  )}
                </div>
              </div>

              {/* 最近活动 */}
              <div>
                <div className="text-xs font-semibold text-ink mb-2">最近活动</div>
                {detail?.recent_activity?.length ? (
                  <ul className="space-y-2.5">
                    {detail.recent_activity.map((a, i) => (
                      <li key={i} className="flex items-start gap-2.5 text-[13px]">
                        <span className="text-[11px] text-ink-muted chem-mono shrink-0 pt-0.5">{a.date}</span>
                        <span className={a.is_correct ? 'text-success shrink-0' : 'text-error shrink-0'}>
                          {a.is_correct ? '✓' : '✗'}
                        </span>
                        <span className="text-ink-secondary">{a.desc}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <span className="text-xs text-ink-muted">暂无活动</span>
                )}
              </div>
            </div>
          </div>
        )}
      </AntDrawer>

      {/* ── 添加学生 Modal ── */}
      <Modal open={addOpen} onClose={() => setAddOpen(false)} title="添加学生" hideFooter>
        <div className="flex gap-1 mb-4">
          {(
            [
              { key: 'manual', label: '手动输入' },
              { key: 'invite', label: '邀请码' },
            ] as const
          ).map((t) => (
            <button
              key={t.key}
              onClick={() => setAddTab(t.key)}
              className={`px-3.5 py-1.5 rounded-[var(--radius-sm)] text-[13px] font-medium transition-colors cursor-pointer ${
                addTab === t.key ? 'bg-primary text-white' : 'text-ink-secondary hover:bg-surface-muted'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {addTab === 'manual' ? (
          <div className="space-y-4">
            <div>
              <div className="text-[13px] font-medium text-ink-secondary mb-1.5">姓名</div>
              <Input value={addName} onChange={(e) => setAddName(e.target.value)} placeholder="学生姓名" />
            </div>
            <div>
              <div className="text-[13px] font-medium text-ink-secondary mb-1.5">班级</div>
              <Select value={addClass} onChange={(e) => setAddClass(e.target.value)}>
                <option value="">选择班级…</option>
                {classes.map((c) => (
                  <option key={c.class_id || c.id} value={c.class_id || c.id}>
                    {c.name || c.class_name || ''}
                  </option>
                ))}
              </Select>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" onClick={() => setAddOpen(false)}>
                取消
              </Button>
              <Button onClick={submitAddStudent}>确认添加</Button>
            </div>
          </div>
        ) : (
          <div>
            <div>
              <div className="text-[13px] font-medium text-ink-secondary mb-1.5">班级</div>
              <Select value={inviteClass} onChange={(e) => setInviteClass(e.target.value)}>
                <option value="">选择班级…</option>
                {classes.map((c) => (
                  <option key={c.class_id || c.id} value={c.class_id || c.id}>
                    {c.name || c.class_name || ''}
                  </option>
                ))}
              </Select>
            </div>
            <div className="flex justify-end gap-2 pt-4">
              <Button onClick={generateInviteCode}>生成邀请码</Button>
            </div>
            {inviteCode && (
              <div className="mt-4 p-4 bg-success-soft border border-success/15 rounded-[var(--radius-md)] text-center animate-fade-in-up">
                <div className="text-[10px] text-ink-muted tracking-widest mb-2">邀请码</div>
                <div className="chem-mono text-[26px] font-medium text-success tracking-[3px] select-all mb-2">
                  {inviteCode}
                </div>
                <div className="text-[11px] text-ink-muted mb-2.5">有效期 7 天 · 将邀请码分享给学生即可加入班级</div>
                <Button size="sm" variant="secondary" onClick={copyInviteCode}>
                  {copied ? <Check size={13} /> : <Copy size={13} />}
                  {copied ? '已复制' : '复制邀请码'}
                </Button>
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* ── 转班 Modal ── */}
      <Modal open={transferOpen} onClose={() => setTransferOpen(false)} title="转班" hideFooter>
        <p className="text-sm text-ink-secondary m-0 mb-3">
          {drawerStudent?.name}（{studentId(drawerStudent || {})}）
        </p>
        <div>
          <div className="text-[13px] font-medium text-ink-secondary mb-1.5">目标班级</div>
          <Select value={transferClass} onChange={(e) => setTransferClass(e.target.value)}>
            <option value="">选择目标班级…</option>
            {classes
              .filter((c) => (c.class_id || c.id) !== (drawerStudent?.class_id || ''))
              .map((c) => (
                <option key={c.class_id || c.id} value={c.class_id || c.id}>
                  {c.name || c.class_name || ''}
                </option>
              ))}
          </Select>
        </div>
        <div className="flex justify-end gap-2 pt-4">
          <Button variant="secondary" onClick={() => setTransferOpen(false)}>
            取消
          </Button>
          <Button onClick={confirmTransfer}>确认转班</Button>
        </div>
      </Modal>

      {/* ── 历史计划 Modal（先渲染；同 z 层时后渲染的在上层，
            计划详情 Modal 必须在历史计划之后 → 查看计划时详情盖住列表；
            top 顶部对齐：列表较长时不用滚动就能看到全貌） ── */}
      <Modal open={historyModal} onClose={() => setHistoryModal(false)} title="历史学习计划" top hideFooter>
        {planHistory.length === 0 ? (
          <EmptyState title="暂无历史学习计划" description="为学生生成计划后会显示在这里" />
        ) : (
          <div className="space-y-2">
            {planHistory.map((p, i) => (
              <button
                key={i}
                onClick={() => p.plan_data && setPlanModal({ mode: 'view', plan: p.plan_data })}
                className="w-full flex items-center justify-between px-3.5 py-3 bg-surface-muted/60 rounded-[var(--radius-md)] hover:bg-surface-muted transition-colors cursor-pointer text-left"
              >
                <span>
                  <span className="block text-sm font-medium text-ink">{p.plan_title || '学习计划'}</span>
                  <span className="block text-xs text-ink-muted mt-0.5">{p.created_at || ''}</span>
                </span>
                <span className="text-xs text-teal shrink-0">查看 →</span>
              </button>
            ))}
          </div>
        )}
      </Modal>

      {/* ── 学习计划 Modal（后渲染，盖在历史计划之上） ── */}
      <Modal
        open={planModal !== null}
        onClose={() => setPlanModal(null)}
        title="学习计划"
        wide
        hideFooter
      >
        {planModal?.mode === 'generating' ? (
          <div className="text-center py-10">
            <RefreshCw size={36} className="mx-auto text-teal animate-spin mb-4" />
            <p className="text-sm text-ink-secondary">{PLAN_TIPS[planTipIdx % PLAN_TIPS.length]}</p>
            <PlanTipRotator onTick={() => setPlanTipIdx((i) => i + 1)} />
          </div>
        ) : planModal?.mode === 'draft' ? (
          <DraftGatePanel
            studentId={drawerStudent ? studentId(drawerStudent) : ''}
            draft={planModal.draft}
            onDraftChanged={(d) => {
              setActiveDraft(d)
              setPlanModal({ mode: 'draft', draft: d })
            }}
          />
        ) : planModal?.mode === 'view' ? (
          <PlanView
            plan={planModal.plan}
            onSave={() => {
              try {
                if (drawerStudent) {
                  localStorage.setItem(`chemai_plan_${studentId(drawerStudent)}`, JSON.stringify(planModal.plan))
                }
              } catch {
                /* ignore */
              }
              toast.success('已保存')
            }}
            onSend={sendPlan}
          />
        ) : null}
      </Modal>
    </div>
  )
}

/** 生成提示词轮换（每 2.5s 一次） */
function PlanTipRotator({ onTick }: { onTick: () => void }) {
  useEffect(() => {
    const t = window.setInterval(onTick, 2500)
    return () => window.clearInterval(t)
  }, [onTick])
  return null
}

/** 计划视图：可编辑字段 + 操作 */
function PlanView({ plan, onSave, onSend }: { plan: PlanData; onSave: () => void; onSend: () => void }) {
  const [data, setData] = useState<PlanData>({ ...plan })
  const setPath = (path: string[], val: string) => {
    setData((prev) => {
      const next: Record<string, unknown> = { ...prev }
      let cur: Record<string, unknown> = next
      for (let i = 0; i < path.length - 1; i++) {
        const key = path[i]
        const isArrNext = /^\d+$/.test(path[i + 1])
        if (isArrNext) {
          if (!Array.isArray(cur[key])) cur[key] = []
          cur = cur[key] as Record<string, unknown>
        } else {
          if (!cur[key] || typeof cur[key] !== 'object') cur[key] = {}
          cur = cur[key] as Record<string, unknown>
        }
      }
      const lastKey = path[path.length - 1]
      if (/^\d+$/.test(lastKey)) {
        const arr = cur as unknown as string[]
        arr[parseInt(lastKey)] = val
      } else {
        cur[lastKey] = val
      }
      return next as PlanData
    })
  }

  const goals = data.weekly_goals || []
  const tasks = data.daily_tasks || []
  const interventions = data.barrier_interventions || {}
  const tips = data.motivation_tips || []
  const noStructured = !tasks.length && !goals.length

  const Editable = ({
    path,
    value,
    className = '',
  }: {
    path: string[]
    value: string
    className?: string
  }) => (
    <div
      contentEditable
      suppressContentEditableWarning
      onBlur={(e) => setPath(path, e.currentTarget.textContent || '')}
      className={`px-2.5 py-2 rounded-[var(--radius-sm)] text-sm text-ink bg-surface border border-transparent focus:border-teal/50 focus:bg-white outline-none hover:border-border transition-colors ${className}`}
      dangerouslySetInnerHTML={{ __html: value }}
    />
  )

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <ClipboardList size={16} className="text-success" />
          <span className="font-semibold text-[15px] text-ink">{data.plan_title || '个性化学习计划'}</span>
        </div>
        {data.plan_period && <span className="text-xs text-ink-muted">周期: {data.plan_period}</span>}
      </div>
      <p className="text-[11px] text-ink-muted mb-3">点击任意字段直接编辑，失焦生效</p>

      {noStructured && data.raw_text ? (
        <Editable path={['raw_text']} value={data.raw_text} />
      ) : null}

      {goals.length > 0 && (
        <div className="mb-3">
          <div className="text-xs font-semibold text-ink mb-1.5">🎯 周目标</div>
          {goals.map((g, i) => (
            <Editable
              key={i}
              path={['weekly_goals', String(i)]}
              value={typeof g === 'string' ? g : String(g.milestone || g.goal || g.text || '')}
            />
          ))}
        </div>
      )}

      {tasks.length > 0 && (
        <div className="mb-3">
          <div className="text-xs font-semibold text-ink mb-1.5">📅 每日任务</div>
          {tasks.slice(0, 14).map((t, j) => {
            const day = typeof t === 'object' ? t.day || '' : ''
            const task = typeof t === 'object' ? t.task || '' : String(t)
            return (
              <div key={j} className="flex items-start gap-2">
                <span className="text-[11px] text-ink-muted shrink-0 pt-2.5 chem-mono w-[52px]">
                  {day ? `Day ${day}` : '•'}
                </span>
                <Editable path={['daily_tasks', String(j), 'task']} value={task} className="flex-1" />
              </div>
            )
          })}
        </div>
      )}

      {Object.keys(interventions).length > 0 && (
        <div className="mb-3">
          <div className="text-xs font-semibold text-ink mb-1.5">🧠 障碍干预</div>
          {Object.entries(interventions).map(([bt, v]) => (
            <div key={bt} className="flex items-start gap-2">
              <span className="text-[11px] text-warning shrink-0 pt-2.5 w-[52px]">
                {{ concept: '概念理解', reading: '审题仔细', expression: '答题表述' }[bt] || bt}
              </span>
              <Editable path={['barrier_interventions', bt]} value={String(v)} className="flex-1" />
            </div>
          ))}
        </div>
      )}

      {tips.length > 0 && (
        <div className="mb-3">
          <div className="text-xs font-semibold text-ink mb-1.5">💡 激励建议</div>
          {tips.map((tip, k) => (
            <Editable key={k} path={['motivation_tips', String(k)]} value={String(tip)} />
          ))}
        </div>
      )}

      <div className="flex gap-2 pt-3.5 mt-2 border-t border-border">
        <Button size="sm" variant="secondary" onClick={onSave}>
          <CalendarClock size={13} />
          保存修改
        </Button>
        <Button size="sm" variant="ai" onClick={onSend}>
          <Send size={13} />
          发给学生
        </Button>
      </div>
    </div>
  )
}

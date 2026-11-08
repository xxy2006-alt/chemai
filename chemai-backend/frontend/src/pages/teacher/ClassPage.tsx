import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Users, FileText, AlertTriangle, TrendingUp, ChevronRight } from 'lucide-react'
import { Select as AntSelect, Statistic, Table as AntTable, Tag as AntTag, type TableColumnsType } from 'antd'
import { api } from '../../lib/api'
import { Card, EmptyState, SkeletonCard } from '../../components/ui'
import { EChart, CHART_COLORS, CHART_AXIS_TEXT } from '../../components/ui/EChart'
import { Illo, assets } from '../../assets'

interface ClassInfo {
  class_id?: string
  id?: string
  name?: string
  class_name?: string
}

interface PanelData {
  class_overview?: {
    exam_count?: number
    total_students?: number
    recent_exam_avg?: number
    avg_score_trend?: number[]
  }
  overview?: Record<string, unknown>
  knowledge_points?: { knowledge_point?: string; error_rate?: number; class_error_rate?: number }[]
  top_errors?: unknown[]
  barrier_distribution?: { concept?: number; reading?: number; expression?: number }
}

interface BarrierStats {
  distribution?: { concept?: { count?: number }; reading?: { count?: number }; expression?: { count?: number } }
}

interface StudentRow {
  id?: string
  student_id?: string
  name?: string
  student_name?: string
  barrier_type?: Record<string, number>
  weak_knowledge_points?: string[]
}

interface TrendPoint {
  date?: string
  exam_date?: string
  avg_score?: number
  score?: number
}

const BARRIER_LABELS: Record<string, string> = { concept: '概念', reading: '审题', expression: '表述' }

/** 班级学情 · Phase 1 迁移（原 pages/teacher.html） */
export function ClassPage() {
  const navigate = useNavigate()
  const [classes, setClasses] = useState<ClassInfo[]>([])
  const [classId, setClassId] = useState('')
  const [loading, setLoading] = useState(true)
  const [panel, setPanel] = useState<PanelData | null>(null)
  const [barrier, setBarrier] = useState<BarrierStats | null>(null)
  const [students, setStudents] = useState<StudentRow[]>([])
  const [trend, setTrend] = useState<TrendPoint[]>([])

  const loadClasses = useCallback(async () => {
    try {
      const d = await api.get<{ success?: boolean; data?: { classes?: ClassInfo[] }; classes?: ClassInfo[] }>(
        '/api/classes',
      )
      const list = (d.data?.classes || d.classes || []) as ClassInfo[]
      if (list.length) {
        setClasses(list)
        const first = list[0].class_id || list[0].id || ''
        setClassId(first)
        return first
      }
    } catch {
      /* 服务不可用 */
    }
    // 演示班级兜底（后端 panel 支持 __demo__ mock）
    setClasses([{ class_id: '__demo__', name: '演示班级' }])
    setClassId('__demo__')
    return '__demo__'
  }, [])

  const loadDashboard = useCallback(async (cid: string) => {
    if (!cid) return
    setLoading(true)
    setPanel(null)
    setBarrier(null)
    setStudents([])
    setTrend([])
    try {
      const [p, b, s] = await Promise.all([
        api.get<PanelData>(`/api/panel/class/${cid}`),
        api.get<BarrierStats>(`/api/diagnosis/class/${cid}/stats`),
        api.get<{ students?: StudentRow[]; data?: StudentRow[] }>(`/api/classes/${cid}/students`),
      ])
      setPanel(p)
      setBarrier(b)
      setStudents(s.students || s.data || [])
      try {
        const t = await api.get<{ trend?: TrendPoint[] }>(`/api/panel/class/${cid}/trend`)
        const list = t.trend || []
        if (list.length) {
          setTrend(list)
        } else if (p.class_overview?.avg_score_trend?.length) {
          setTrend(
            p.class_overview.avg_score_trend.map((v, i) => ({
              date: `考试${i + 1}`,
              avg_score: v,
            })),
          )
        }
      } catch {
        /* 趋势接口失败不阻塞 */
      }
    } catch {
      /* 数据加载失败：保持空态 */
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadClasses().then((cid) => loadDashboard(cid))
  }, [loadClasses, loadDashboard])

  const overview = panel?.class_overview || {}
  const kpData = panel?.knowledge_points || []
  const dist = useMemo(() => {
    if (barrier?.distribution) return barrier.distribution
    const bd = panel?.barrier_distribution
    if (bd) {
      return {
        concept: { count: bd.concept || 0 },
        reading: { count: bd.reading || 0 },
        expression: { count: bd.expression || 0 },
      }
    }
    return null
  }, [barrier, panel])

  const warnCount =
    (dist?.concept?.count || 0) + (dist?.reading?.count || 0) + (dist?.expression?.count || 0)

  /* 图表 option */
  const kpOption = useMemo(() => {
    if (!kpData.length) return null
    return {
      tooltip: { trigger: 'axis' as const },
      grid: { left: 40, right: 16, top: 16, bottom: 28 },
      xAxis: {
        type: 'category' as const,
        data: kpData.slice(0, 8).map((d) => d.knowledge_point || ''),
        axisLabel: { ...CHART_AXIS_TEXT, interval: 0, rotate: kpData.length > 4 ? 28 : 0 },
        axisLine: { lineStyle: { color: '#e5e7eb' } }, // @token-allow chart(canvas)
      },
      yAxis: {
        type: 'value' as const,
        max: 100,
        axisLabel: { ...CHART_AXIS_TEXT, formatter: '{value}%' },
        splitLine: { lineStyle: { color: '#f0f1f3' } }, // @token-allow chart(canvas)
      },
      series: [
        {
          type: 'bar' as const,
          data: kpData.slice(0, 8).map((d) => Math.round(((d.class_error_rate ?? d.error_rate) || 0) * 100)),
          itemStyle: {
            borderRadius: [4, 4, 0, 0],
            color: (p: { dataIndex: number }) => CHART_COLORS.bar[p.dataIndex % CHART_COLORS.bar.length],
          },
          barWidth: 28,
        },
      ],
    }
  }, [kpData])

  const barrierOption = useMemo(() => {
    const counts = [dist?.concept?.count || 0, dist?.reading?.count || 0, dist?.expression?.count || 0]
    if (counts.every((v) => v === 0)) return null
    return {
      tooltip: { trigger: 'item' as const },
      legend: {
        bottom: 0,
        icon: 'circle',
        itemWidth: 8,
        textStyle: { color: '#5b616e', fontSize: 12 }, // @token-allow chart(canvas)
      },
      series: [
        {
          type: 'pie' as const,
          radius: ['55%', '75%'],
          center: ['50%', '44%'],
          avoidLabelOverlap: true,
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
  }, [dist])

  const trendOption = useMemo(() => {
    if (!trend.length) return null
    return {
      tooltip: {
        trigger: 'axis' as const,
        valueFormatter: (v: number) => `${v} 分`,
      },
      grid: { left: 44, right: 16, top: 20, bottom: 28 },
      xAxis: {
        type: 'category' as const,
        data: trend.map((d) => d.date || d.exam_date || ''),
        axisLabel: CHART_AXIS_TEXT,
        axisLine: { lineStyle: { color: '#e5e7eb' } }, // @token-allow chart(canvas)
      },
      yAxis: {
        type: 'value' as const,
        min: 0,
        max: 100,
        axisLabel: { ...CHART_AXIS_TEXT, formatter: '{value} 分' },
        splitLine: { lineStyle: { color: '#f0f1f3' } }, // @token-allow chart(canvas)
      },
      series: [
        {
          type: 'line' as const,
          name: '平均分',
          data: trend.map((d) => d.avg_score || d.score || 0),
          smooth: 0.3,
          symbol: 'circle',
          symbolSize: 6,
          lineStyle: { color: CHART_COLORS.line, width: 2 },
          itemStyle: { color: CHART_COLORS.teal },
          areaStyle: { color: 'rgba(13, 115, 119, 0.06)' }, // @token-allow chart(canvas)
        },
      ],
    }
  }, [trend])

  /* 需关注学生 top5（按最高障碍占比排序） */
  const attention = useMemo(() => {
    const scored = students
      .map((s) => {
        const bt = s.barrier_type || {}
        const max = Math.max(0, ...Object.values(bt))
        return { s, score: max }
      })
      .sort((a, b) => b.score - a.score)
      .slice(0, 5)
    if (!scored.length || scored[0].score === 0) return []
    return scored.map((x) => x.s)
  }, [students])

  const columns: TableColumnsType<StudentRow> = [
    {
      key: 'name',
      title: '学生',
      render: (_, row) => (
        <span className="flex items-center gap-2.5">
          <span className="w-7 h-7 rounded-full bg-primary-soft text-primary text-xs font-semibold flex items-center justify-center shrink-0">
            {(row.name || row.student_name || '?').charAt(0)}
          </span>
          <span className="font-medium text-ink">{row.name || row.student_name || ''}</span>
        </span>
      ),
    },
    {
      key: 'barrier',
      title: '主要障碍',
      render: (_, row) => {
        const bt = row.barrier_type || {}
        const entries = Object.entries(bt).filter(([, v]) => v > 0)
        if (!entries.length) return <span className="text-ink-muted">—</span>
        const top = entries.sort((a, b) => b[1] - a[1])[0]
        return (
          <AntTag color={top[0] === 'concept' ? 'blue' : top[0] === 'reading' ? 'orange' : 'green'} className="m-0">
            {BARRIER_LABELS[top[0]] || top[0]} {Math.round(top[1] * 100)}%
          </AntTag>
        )
      },
    },
    {
      key: 'weak',
      title: '弱知识点',
      render: (_, row) => (
        <span className="text-[13px] text-ink-secondary">
          {(row.weak_knowledge_points || []).length ? row.weak_knowledge_points!.join('、') : '—'}
        </span>
      ),
    },
    {
      key: 'action',
      title: '',
      width: '40px',
      render: () => <ChevronRight size={14} className="text-ink-muted" />,
    },
  ]

  function focusStudent(row: StudentRow) {
    sessionStorage.setItem('chemai_focus_student', row.id || row.student_id || '')
    navigate('/students')
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <SkeletonCard />
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          {[0, 1, 2, 3].map((i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="animate-fade-in-up">
      {/* 页头 */}
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div>
          <h1 className="text-[22px] font-semibold text-ink m-0">班级学情</h1>
          <p className="mt-1 text-sm text-ink-secondary">班级统计 · 知识掌握 · 障碍分布 · 成绩趋势</p>
        </div>
        <div className="w-[220px]">
          <AntSelect
            value={classId}
            onChange={loadDashboard}
            className="w-full"
            options={classes.map((c) => ({
              value: c.class_id || c.id || '',
              label: c.name || c.class_name || '',
            }))}
          />
        </div>
      </div>

      {/* 统计卡（antd Statistic） */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-5">
        <div className="bg-surface border border-border rounded-[var(--radius-lg)] p-4">
          <Statistic
            title={<span className="text-[13px] text-ink-secondary">考试次数</span>}
            value={overview.exam_count || 0}
            prefix={<FileText size={16} className="text-teal mr-1" />}
          />
        </div>
        <div className="bg-surface border border-border rounded-[var(--radius-lg)] p-4">
          <Statistic
            title={<span className="text-[13px] text-ink-secondary">需关注学生</span>}
            value={warnCount}
            prefix={<AlertTriangle size={16} className={warnCount > 0 ? 'text-warning mr-1' : 'text-ink-muted mr-1'} />}
            styles={{ content: warnCount > 0 ? { color: 'var(--color-warning)' } : undefined }}
          />
        </div>
        <div className="bg-surface border border-border rounded-[var(--radius-lg)] p-4">
          <Statistic
            title={<span className="text-[13px] text-ink-secondary">班级人数</span>}
            value={overview.total_students || students.length || 0}
            prefix={<Users size={16} className="text-success mr-1" />}
          />
        </div>
        <div className="bg-surface border border-border rounded-[var(--radius-lg)] p-4">
          <Statistic
            title={<span className="text-[13px] text-ink-secondary">最近均分</span>}
            value={overview.recent_exam_avg ? overview.recent_exam_avg : '--'}
            suffix={overview.recent_exam_avg ? '分' : undefined}
            prefix={<TrendingUp size={16} className="text-primary mr-1" />}
          />
        </div>
      </div>

      {/* 图表区 */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 mb-5">
        <Card title="知识点错误率" flush>
          {kpOption ? (
            <div className="p-3">
              <EChart option={kpOption} height={280} />
            </div>
          ) : (
            <EmptyState
              illustration={<Illo src={assets.emptyClass} />}
              title="暂无知识点数据"
              description="完成诊断或考试后这里会展示知识点错误率"
            />
          )}
        </Card>
        <Card title="障碍类型分布" flush>
          {barrierOption ? (
            <div className="p-3">
              <EChart option={barrierOption} height={280} />
            </div>
          ) : (
            <EmptyState
              illustration={<Illo src={assets.emptyClass} />}
              title="暂无诊断数据"
              description="学生完成诊断后这里会展示障碍类型分布"
            />
          )}
        </Card>
      </div>

      <Card title="成绩趋势" flush className="mb-5">
        {trendOption ? (
          <div className="p-3">
            <EChart option={trendOption} height={240} />
          </div>
        ) : (
          <EmptyState
            illustration={<Illo src={assets.emptyClass} width={180} />}
            title="暂无趋势数据"
            description="完成多次考试后这里会展示成绩变化"
          />
        )}
      </Card>

      {/* 需关注学生 */}
      {attention.length > 0 && (
        <Card title="需关注学生" className="mb-5">
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-3">
            {attention.map((s, i) => {
              const bt = s.barrier_type || {}
              const maxKey = Object.entries(bt).sort((a, b) => b[1] - a[1])[0]?.[0] || ''
              return (
                <button
                  key={i}
                  onClick={() => focusStudent(s)}
                  className="flex items-center gap-2.5 px-3 py-2.5 border border-border rounded-[var(--radius-md)] hover:border-teal/40 hover:shadow-[var(--shadow-sm)] transition-all cursor-pointer text-left"
                >
                  <span className="w-8 h-8 rounded-full bg-primary-soft text-primary text-sm font-semibold flex items-center justify-center shrink-0">
                    {(s.name || s.student_name || '?').charAt(0)}
                  </span>
                  <span className="min-w-0">
                    <span className="block text-[13px] font-medium text-ink truncate">{s.name || s.student_name || ''}</span>
                    {maxKey && (
                      <AntTag color={maxKey === 'concept' ? 'blue' : maxKey === 'reading' ? 'orange' : 'green'} className="mt-0.5">
                        {BARRIER_LABELS[maxKey] || maxKey} {Math.round((bt[maxKey] || 0) * 100)}%
                      </AntTag>
                    )}
                  </span>
                </button>
              )
            })}
          </div>
        </Card>
      )}

      {/* 学生列表（antd Table） */}
      <Card title="学生列表" flush>
        {students.length ? (
          <AntTable<StudentRow>
            columns={columns}
            dataSource={students}
            rowKey={(row) => row.id || row.student_id || String(row.name || '')}
            size="middle"
            pagination={{ pageSize: 10, showSizeChanger: false, showTotal: (t) => `共 ${t} 名学生` }}
            onRow={(row) => ({
              onClick: () => focusStudent(row),
              className: 'cursor-pointer',
            })}
          />
        ) : (
          <EmptyState
            illustration={<Illo src={assets.emptyStudents} />}
            title="暂无学生数据"
            description="班级中还没有学生，可在学生管理中添加"
          />
        )}
      </Card>
    </div>
  )
}

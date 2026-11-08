/* ParentHomePage — 家长主面板（design/家长端.md）：
 * 三 Tab（概览/学习报告/消息）+ 绑定管理 + AI 助手对话覆盖层（persona=parent）。
 * Wise 视觉：白卡 24px 圆角坐鼠尾草底；报告 hero 48px/900（R-P-T1/L1）；
 * 涨跌徽章 positive-pale 深字（R-P-C2）；AI 气泡保持品牌青（R-P-C3）。 */

import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  User, Link2, Link2Off, LogOut, Users, TrendingUp, TrendingDown, Minus,
  BarChart3, Lightbulb, Search, BookOpenCheck, Send, X,
} from 'lucide-react'
import { api } from '../../../lib/api'
import { getMobileUser, clearMobileSession, type MobileUser } from '../../../lib/mobile-auth'
import { MobileLayout, MobileHeader, MobileTabBar, MobileFullPane, MobileLoading, MobileEmpty } from '../../../components/mobile/MobileLayout'
import { ChatPanel } from '../../../components/mobile/ChatPanel'

interface Child {
  student_id: string
  student_name?: string
  grade?: string
  class_name?: string
  relation?: string
  binding_id?: string
}

interface ChildReport {
  success?: boolean
  report?: {
    exercises_completed?: number
    last_exercise_at?: string
    barrier_type?: Record<string, number>
  }
}

interface Weekly {
  success?: boolean
  weekly?: {
    practice_count?: number
    accuracy_rate?: number
    streak_days?: number
    weak_knowledge_points?: string[]
  }
}

interface Notification {
  notification_id: string
  title: string
  content?: string
  type?: string
  is_read?: boolean
  created_at?: string
}

type TabId = 'home' | 'report' | 'notif'

function greeting() {
  const h = new Date().getHours()
  return h < 6 ? '夜深了' : h < 12 ? '早上好' : h < 14 ? '中午好' : h < 18 ? '下午好' : '晚上好'
}

function fmtTime(s?: string) {
  if (!s) return ''
  const d = new Date(s)
  if (isNaN(d.getTime())) return s.slice(0, 10)
  const now = new Date()
  const pad = (n: number) => (n < 10 ? `0${n}` : `${n}`)
  if (d.toDateString() === now.toDateString()) return `今天 ${pad(d.getHours())}:${pad(d.getMinutes())}`
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const BARRIER_NAMES: Record<string, string> = { concept: '概念理解', reading: '审题仔细', expression: '答题表述' }
const BARRIER_TIPS: Record<string, string> = {
  concept: '建议帮孩子建立知识框架图，用思维导图梳理化学概念之间的联系。',
  reading: '建议每天陪孩子读一道题，让他把题目条件说出来。这能有效改善审题习惯。',
  expression: '鼓励孩子写完整的解题过程，化学符号和方程式要写规范。',
}

export function ParentHomePage() {
  const navigate = useNavigate()
  const [user] = useState<MobileUser | null>(() => getMobileUser() as MobileUser | null)
  const [children, setChildren] = useState<Child[]>([])
  const [active, setActive] = useState<Child | null>(null)
  const [tab, setTab] = useState<TabId>('home')
  const [loaded, setLoaded] = useState(false)
  const [bindOpen, setBindOpen] = useState(false)
  const [manageOpen, setManageOpen] = useState(false)
  const [bindSid, setBindSid] = useState('')
  const [bindCode, setBindCode] = useState('')
  const [chatOpen, setChatOpen] = useState(false)
  const [parentCid] = useState(() => localStorage.getItem('chemai_parent_cid') || `p-${Date.now()}`)

  useEffect(() => {
    document.title = '家长面板'
    localStorage.setItem('chemai_parent_cid', parentCid)
  }, [parentCid])

  const loadChildren = useCallback(() => {
    if (!user) return
    api.get<{ success?: boolean; children?: Child[] }>(
      `/api/parent/children?parent_id=${encodeURIComponent(user.id)}`,
    )
      .then((d) => {
        const list = d.success && d.children ? d.children : []
        setChildren(list)
        setActive(list[0] || null)
        setLoaded(true)
      })
      .catch(() => setLoaded(true))
  }, [user])

  useEffect(() => loadChildren(), [loadChildren])

  function doBind() {
    if (!user || !bindSid.trim() || !bindCode.trim()) return
    api.post<{ success?: boolean; message?: string; detail?: string }>('/api/parent/bind', {
      student_id: bindSid.trim(), bind_code: bindCode.trim(), parent_id: user.id, relation: '家长',
    })
      .then((d) => {
        if (d.success) {
          setBindOpen(false)
          setBindSid('')
          setBindCode('')
          loadChildren()
        } else {
          alert(d.message || d.detail || '绑定失败')
        }
      })
      .catch(() => alert('网络错误，请重试'))
  }

  function doUnbind(bindingId: string, name: string) {
    if (!user || !confirm(`确定解除与 ${name} 的绑定？解除后家长端将不再显示该学生的学习数据。`)) return
    api.del<{ success?: boolean; message?: string }>(
      `/api/parent/bind/${bindingId}?parent_id=${encodeURIComponent(user.id)}`,
    )
      .then((d) => {
        if (d.success) {
          setManageOpen(false)
          loadChildren()
        } else alert(d.message || '解绑失败')
      })
  }

  if (!user) return null

  const tabs = [
    { id: 'home', label: '概览', icon: <BarChart3 size={20} />, active: tab === 'home', onClick: () => setTab('home') },
    { id: 'report', label: '学习报告', icon: <BookOpenCheck size={20} />, active: tab === 'report', onClick: () => setTab('report') },
    { id: 'notif', label: '消息', icon: <Send size={20} />, active: tab === 'notif', onClick: () => setTab('notif') },
  ]

  return (
    <MobileLayout
      theme="parent"
      header={
        <MobileHeader
          title={
            <span>
              <span className="block text-[11px] text-ink-muted font-normal leading-none">{greeting()}</span>
              <span className="text-[16px]">{user.name || '家长'}</span>
            </span>
          }
          left={
            <div className="w-9 h-9 rounded-full bg-primary-soft flex items-center justify-center">
              <User size={17} className="text-primary" />
            </div>
          }
          right={
            <div className="flex items-center gap-1">
              <button
                onClick={() => (children.length > 0 ? setManageOpen(true) : setBindOpen(true))}
                className="p-2 rounded-full hover:bg-surface-muted cursor-pointer text-ink-secondary"
                title={children.length > 0 ? '管理绑定' : '绑定孩子'}
              >
                {children.length > 0 ? <Link2Off size={17} /> : <Link2 size={17} />}
              </button>
              <button
                onClick={() => {
                  clearMobileSession()
                  navigate('/m/parent-login', { replace: true })
                }}
                className="p-2 rounded-full hover:bg-surface-muted cursor-pointer text-ink-secondary"
                title="退出登录"
              >
                <LogOut size={17} />
              </button>
            </div>
          }
        />
      }
      footer={
        children.length > 0 ? (
          <>
            {/* 孩子条 */}
            <div className="flex items-center gap-2.5 px-4 py-2 bg-surface border-t border-border/60">
              <div className="w-8 h-8 rounded-full bg-primary-soft flex items-center justify-center text-[14px] font-black text-primary font-display">
                {(active?.student_name || '?')[0]}
              </div>
              <div>
                <div className="text-[13px] font-semibold text-ink leading-tight">{active?.student_name}</div>
                <div className="text-[11px] text-ink-muted">{active?.grade} {active?.class_name}</div>
              </div>
            </div>
            <MobileTabBar tabs={tabs} />
          </>
        ) : undefined
      }
    >
      {!loaded ? (
        <MobileLoading />
      ) : !active ? (
        /* 未绑定空态（R-S2：给行动） */
        <MobileEmpty
          icon={<Users size={34} />}
          title="还没有绑定孩子"
          hint={<>绑定后可以查看孩子的<br />学习报告和成长动态</>}
          action={
            <button
              onClick={() => setBindOpen(true)}
              className="px-9 py-3.5 rounded-[24px] bg-primary text-on-primary text-[15px] font-bold"
            >
              立即绑定
            </button>
          }
        />
      ) : tab === 'home' ? (
        <HomePane child={active} parentId={user.id} />
      ) : tab === 'report' ? (
        <ReportPane child={active} parentId={user.id} />
      ) : (
        <NotifPane parentId={user.id} />
      )}

      {/* 问问 AI 助手（悬浮按钮，R-P-C3：入口保留定案） */}
      {active && (
        <button
          onClick={() => setChatOpen(true)}
          className="fixed bottom-24 right-[max(16px,calc(50%-200px))] z-30 flex items-center gap-1.5 h-11 px-5 rounded-full bg-teal text-white text-[14px] font-semibold shadow-[var(--shadow-md)] active:scale-95 transition-transform"
        >
          问问 AI 助手
        </button>
      )}

      {/* AI 对话覆盖层 */}
      {chatOpen && (
        <div className="fixed inset-0 z-50 flex justify-center bg-bg">
          <div data-theme="parent" className="w-full max-w-[430px] h-[100dvh] flex flex-col bg-bg">
            <MobileHeader
              title="AI 家长助手"
              left={
                <button onClick={() => setChatOpen(false)} className="p-1.5 -ml-1.5 hover:bg-surface-muted rounded-full cursor-pointer" aria-label="返回">
                  <X size={20} />
                </button>
              }
            />
            <ChatPanel
              persona="parent"
              cid={parentCid}
              studentId={active?.student_id || ''}
              placeholder="输入问题…"
              quickPrompts={['孩子这周学习怎么样?', '需要重点关注什么?', '在家怎么帮孩子?']}
              intro={
                <div className="text-center py-16 px-8">
                  <p className="text-[14px] text-ink-secondary leading-[1.8]">
                    我是 ChemAI 家长助手。
                    <br />
                    可以问我孩子的学习情况、
                    <br />
                    成长空间、以及在家怎么配合。
                  </p>
                </div>
              }
            />
          </div>
        </div>
      )}

      {/* 绑定弹窗 */}
      {bindOpen && (
        <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-6" onClick={(e) => e.target === e.currentTarget && setBindOpen(false)}>
          <div className="w-full max-w-[390px] bg-surface rounded-[24px] p-6 shadow-[var(--shadow-lg)]">
            <h3 className="text-[17px] font-bold text-ink mb-4">绑定孩子</h3>
            <label className="block text-[13px] text-ink-secondary mb-1">学生 ID（学号）</label>
            <input value={bindSid} onChange={(e) => setBindSid(e.target.value)} placeholder="输入孩子的学号，如 202610101" className="w-full h-12 px-4 mb-3 rounded-xl border-[1.5px] border-ink bg-surface text-[15px] text-ink placeholder:text-ink-muted/70 outline-none focus:border-primary" />
            <label className="block text-[13px] text-ink-secondary mb-1">绑定码（由学生在自己客户端获取）</label>
            <input value={bindCode} onChange={(e) => setBindCode(e.target.value)} placeholder="6 位数字" maxLength={6} className="w-full h-12 px-4 rounded-xl border-[1.5px] border-ink bg-surface text-[15px] text-ink placeholder:text-ink-muted/70 outline-none focus:border-primary" />
            <div className="flex gap-2.5 mt-4">
              <button onClick={() => setBindOpen(false)} className="flex-1 h-12 rounded-[24px] bg-surface-muted text-ink-secondary text-[15px] font-semibold">取消</button>
              <button onClick={doBind} className="flex-1 h-12 rounded-[24px] bg-primary text-on-primary text-[15px] font-bold">确认绑定</button>
            </div>
          </div>
        </div>
      )}

      {/* 绑定管理弹窗 */}
      <MobileFullPane open={manageOpen} title="已绑定的孩子" onClose={() => setManageOpen(false)}>
        <div className="space-y-2.5">
          {children.map((c) => (
            <div key={c.binding_id} className="flex items-center justify-between p-4 rounded-[24px] bg-surface">
              <div>
                <div className="font-bold text-[15px] text-ink">{c.student_name}</div>
                <div className="text-[12px] text-ink-muted">{c.grade} {c.class_name} · {c.relation || '家长'}</div>
              </div>
              <button
                onClick={() => doUnbind(c.binding_id || '', c.student_name || '')}
                className="px-3.5 py-1.5 rounded-full border border-error/40 text-error text-[12.5px] bg-surface cursor-pointer"
              >
                解绑
              </button>
            </div>
          ))}
          <button
            onClick={() => {
              setManageOpen(false)
              setBindOpen(true)
            }}
            className="w-full h-12 mt-2 rounded-[24px] bg-surface-muted text-ink-secondary text-[14px] font-semibold"
          >
            + 绑定其他孩子
          </button>
        </div>
      </MobileFullPane>
    </MobileLayout>
  )
}

/* ── 概览 Tab ── */
function HomePane({ child, parentId }: { child: Child; parentId: string }) {
  const [report, setReport] = useState<ChildReport | null>(null)
  const [weekly, setWeekly] = useState<Weekly | null>(null)

  useEffect(() => {
    setReport(null)
    setWeekly(null)
    api.get<ChildReport>(`/api/parent/child/${child.student_id}/report?parent_id=${encodeURIComponent(parentId)}`)
      .then(setReport)
      .catch(() => {})
    api.get<Weekly>(`/api/parent/child/${child.student_id}/weekly?parent_id=${encodeURIComponent(parentId)}`)
      .then(setWeekly)
      .catch(() => {})
  }, [child.student_id, parentId])

  const r = report?.report
  const w = weekly?.weekly
  const accuracy = Math.round((w?.accuracy_rate ?? 0) * 100)
  const streak = w?.streak_days ?? 0
  const barrier = r?.barrier_type || {}
  const dominant = Object.entries(barrier).sort((a, b) => (b[1] || 0) - (a[1] || 0))[0]?.[0] || 'concept'
  const pct = (k: string) => Math.round((barrier[k] ?? 0) * 100)

  return (
    <div className="p-4 space-y-3">
      {/* 学习概览 hero 卡（单页唯一 hero，R-P-L1） */}
      <div className="bg-surface rounded-[24px] p-5 shadow-sm">
        <div className="text-[12px] text-ink-muted mb-2">本周学习</div>
        <div className="flex items-end gap-3">
          <span className="font-display text-[48px] font-black leading-none text-ink kpi-number">{w?.practice_count ?? r?.exercises_completed ?? 0}</span>
          <span className="text-[13px] text-ink-secondary pb-1.5">道练习</span>
        </div>
        <div className="flex gap-2 mt-3">
          <span className="flex items-center gap-1 text-[11.5px] px-2.5 py-1 rounded-full bg-success-soft text-[var(--color-success)] font-semibold">
            <TrendingUp size={12} />正确率约 {accuracy}%
          </span>
          <span className="flex items-center gap-1 text-[11.5px] px-2.5 py-1 rounded-full bg-primary-soft text-ink font-semibold">
            连续打卡 {streak} 天
          </span>
        </div>
      </div>

      {/* 学习特点（障碍分布） */}
      <div className="bg-surface rounded-[24px] p-5 shadow-sm">
        <div className="flex items-center gap-1.5 text-[14px] font-bold text-ink mb-3">
          <Search size={15} className="text-primary" />学习特点
        </div>
        {(['concept', 'reading', 'expression'] as const).map((k) => (
          <div key={k} className="mb-2.5 last:mb-0">
            <div className="flex justify-between text-[12.5px] mb-1">
              <span className="text-ink-secondary">{BARRIER_NAMES[k]}</span>
              <span className="font-semibold text-ink kpi-number">{pct(k)}%</span>
            </div>
            <div className="h-1.5 rounded-full bg-surface-muted overflow-hidden">
              <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${pct(k)}%` }} />
            </div>
          </div>
        ))}
        <p className="text-[12.5px] leading-relaxed text-ink-secondary mt-3">
          <b className="text-ink">{BARRIER_NAMES[dominant]}</b> 是需要重点关注的方面。{BARRIER_TIPS[dominant]}
        </p>
      </div>

      {/* 给家长的建议 */}
      <div className="bg-surface rounded-[24px] p-5 shadow-sm">
        <div className="flex items-center gap-1.5 text-[14px] font-bold text-ink mb-2">
          <Lightbulb size={15} className="text-primary" />给家长的建议
        </div>
        <p className="text-[13px] leading-relaxed text-ink-secondary">
          多问问孩子"今天学到了什么有趣的东西"，而不是"考了多少分"。肯定努力比关注分数更重要。
        </p>
      </div>
    </div>
  )
}

/* ── 学习报告 Tab ── */
function ReportPane({ child, parentId }: { child: Child; parentId: string }) {
  const [report, setReport] = useState<ChildReport | null>(null)
  const [weekly, setWeekly] = useState<Weekly | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      api.get<ChildReport>(`/api/parent/child/${child.student_id}/report?parent_id=${encodeURIComponent(parentId)}`),
      api.get<Weekly>(`/api/parent/child/${child.student_id}/weekly?parent_id=${encodeURIComponent(parentId)}`),
    ])
      .then(([r, w]) => {
        setReport(r)
        setWeekly(w)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [child.student_id, parentId])

  if (loading) return <MobileLoading />
  if (!report?.success) return <MobileEmpty title="暂无报告数据" hint="孩子完成练习后这里会出现学习报告" />

  const r = report.report || {}
  const w = weekly?.weekly || {}
  const accuracy = Math.round((w.accuracy_rate ?? 0) * 100)
  const barrier = r.barrier_type || {}
  const dominant = Object.entries(barrier).sort((a, b) => (b[1] || 0) - (a[1] || 0))[0]?.[0] || 'concept'
  const weakKps = (w.weak_knowledge_points || []).slice(0, 5)

  return (
    <div className="p-4 space-y-3">
      {/* hero：本周正确率 48px/900（R-P-T1） */}
      <div className="bg-surface rounded-[24px] p-5 shadow-sm">
        <div className="text-[12px] text-ink-muted mb-1.5">本周正确率</div>
        <div className="flex items-end gap-2">
          <span className="font-display text-[48px] font-black leading-none text-ink kpi-number">{accuracy}</span>
          <span className="text-[20px] font-black text-ink pb-0.5">%</span>
          <span className={`flex items-center gap-0.5 ml-2 mb-1 text-[11.5px] px-2.5 py-1 rounded-full font-semibold ${accuracy >= 60 ? 'bg-success-soft text-[var(--color-success)]' : 'bg-warning-soft text-warning'}`}>
            {accuracy >= 60 ? <TrendingUp size={12} /> : accuracy > 0 ? <TrendingDown size={12} /> : <Minus size={12} />}
            {accuracy >= 60 ? '稳步提升' : accuracy > 0 ? '需要加油' : '暂无数据'}
          </span>
        </div>
      </div>

      {/* 学习概览 4 KPI */}
      <div className="grid grid-cols-2 gap-2.5">
        {[
          { v: w.practice_count ?? r.exercises_completed ?? 0, l: '本周练习', u: '道' },
          { v: w.streak_days ?? 0, l: '连续打卡', u: '天' },
          { v: r.exercises_completed ?? 0, l: '已完成练习', u: '道' },
          { v: weakKps.length, l: '薄弱知识点', u: '个' },
        ].map((s) => (
          <div key={s.l} className="bg-surface rounded-[24px] py-4 text-center shadow-sm">
            <div className="font-display text-[26px] font-black text-ink leading-none kpi-number">
              {s.v}
              <span className="text-[12px] font-normal text-ink-muted ml-0.5">{s.u}</span>
            </div>
            <div className="text-[11px] text-ink-muted mt-1.5">{s.l}</div>
          </div>
        ))}
      </div>

      {/* 知识点掌握 */}
      <div className="bg-surface rounded-[24px] p-5 shadow-sm">
        <div className="flex items-center gap-1.5 text-[14px] font-bold text-ink mb-2.5">
          <Search size={15} className="text-primary" />需要加强的知识点
        </div>
        {weakKps.length ? (
          <div className="flex flex-wrap gap-1.5">
            {weakKps.map((k) => (
              <span key={k} className="text-[12px] px-3 py-1 rounded-full bg-success-soft text-[var(--color-success)] font-medium">{k}</span>
            ))}
          </div>
        ) : (
          <p className="text-[13px] text-ink-muted">暂无薄弱数据，表现很稳！</p>
        )}
      </div>

      {/* 学习特点 + 家庭配合建议 */}
      <div className="bg-surface rounded-[24px] p-5 shadow-sm">
        <div className="flex items-center gap-1.5 text-[14px] font-bold text-ink mb-3">
          <Lightbulb size={15} className="text-primary" />家庭配合建议
        </div>
        <p className="text-[13px] leading-relaxed text-ink-secondary">
          <b className="text-ink">{BARRIER_NAMES[dominant]}</b>是需要重点关注的方面。{BARRIER_TIPS[dominant]}
          多问问孩子"今天学到了什么有趣的东西"，而不是"考了多少分"。肯定努力比关注分数更重要。
        </p>
      </div>
    </div>
  )
}

/* ── 消息 Tab ── */
function NotifPane({ parentId }: { parentId: string }) {
  const [items, setItems] = useState<Notification[] | null>(null)
  const [openNotif, setOpenNotif] = useState<Notification | null>(null)

  const load = useCallback(() => {
    api.get<{ success?: boolean; notifications?: Notification[] }>(
      `/api/parent/notifications?parent_id=${encodeURIComponent(parentId)}&limit=20`,
    )
      .then((d) => setItems(d.success ? d.notifications || [] : []))
      .catch(() => setItems([]))
  }, [parentId])

  useEffect(() => load(), [load])

  function markRead(n: Notification) {
    api.put(`/api/parent/notifications/${n.notification_id}/read?parent_id=${encodeURIComponent(parentId)}`)
      .then(load)
      .catch(() => {})
  }

  return (
    <div className="p-4">
      {items === null ? (
        <MobileLoading />
      ) : items.length === 0 ? (
        <MobileEmpty title="暂无消息" hint="周报与学习提醒会出现在这里" />
      ) : (
        <div className="space-y-2.5">
          {items.map((n) => {
            const isReport = n.type === 'weekly_report' || n.type === 'learning_plan'
            return (
              <button
                key={n.notification_id}
                onClick={() => {
                  markRead(n)
                  if (isReport) setOpenNotif(n)
                }}
                className={`w-full text-left p-4 rounded-[24px] bg-surface shadow-sm transition-opacity ${n.is_read ? 'opacity-60' : ''}`}
              >
                <div className="flex items-start gap-2.5">
                  <span className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${n.is_read ? 'bg-ink-muted/40' : 'bg-primary'}`} />
                  <div className="flex-1 min-w-0">
                    <div className="text-[14.5px] font-semibold text-ink">{n.title}</div>
                    {n.content && !isReport && (
                      <p className="text-[13px] text-ink-secondary mt-1 leading-relaxed">{n.content.slice(0, 100)}</p>
                    )}
                    {isReport && (
                      <p className="text-[12.5px] text-primary mt-1 font-medium">点击查看完整报告</p>
                    )}
                    <div className="text-[11px] text-ink-muted mt-1">
                      {fmtTime(n.created_at)}
                      {n.is_read ? ' · 已读' : ''}
                    </div>
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      )}

      {/* 通知报告全文 */}
      <MobileFullPane open={!!openNotif} title={openNotif?.title || ''} onClose={() => setOpenNotif(null)}>
        <p className="text-[14px] leading-[1.9] text-ink whitespace-pre-wrap">{openNotif?.content}</p>
      </MobileFullPane>
    </div>
  )
}

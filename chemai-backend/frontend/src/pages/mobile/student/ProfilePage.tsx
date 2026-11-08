/* ProfilePage — 我的（个人报告与设置，design/学生端.md）：
 * 游戏化首期（连续打卡 streak / 积分 / 徽章，数据来自学生 stats 接口）+
 * KPI（900 大数字）+ 学习计划/学习报告/复习中心/设置 全屏面板（P-08 底层逻辑同源）。 */

import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Flame, Star, MessageCircle, PenLine, BookX, User, CalendarCheck, FileText, RotateCcw, Settings, LogOut, Copy, Check, Award } from 'lucide-react'
import { api } from '../../../lib/api'
import { getMobileUser, clearMobileSession, type MobileUser } from '../../../lib/mobile-auth'
import { MobileLayout, MobileHeader, MobileTabBar, MobileFullPane, MobileLoading, MobileEmpty } from '../../../components/mobile/MobileLayout'

interface DiagnosisPlan {
  success?: boolean
  data?: {
    total_answers?: number
    accuracy?: number
    weak_knowledge_points?: string[]
    bind_code?: string
  }
}

interface StudentStats {
  total_answers: number
  accuracy: number
  streak_days: number
  week_practice_count: number
}

interface LearningPlan {
  plan?: {
    plan_title?: string
    plan_period?: string
    weekly_goals?: ({ milestone?: string; goal?: string; text?: string } | string)[]
    daily_tasks?: { day?: string; task?: string; content?: string }[]
    barrier_interventions?: Record<string, string>
    motivation_tips?: ({ tip?: string; text?: string } | string)[]
    raw_text?: string
  }
}

interface StudentReport {
  success?: boolean
  data?: {
    exercises_completed?: number
    avg_score?: number | string
    barrier_type?: Record<string, number>
    recent_exams?: number
    trend?: { exam_name?: string; score?: number }[]
  }
  message?: string
}

const BARRIER_NAMES: Record<string, string> = { concept: '概念理解', reading: '审题仔细', expression: '答题表述' }

export function ProfilePage() {
  const navigate = useNavigate()
  const [user] = useState<MobileUser | null>(() => getMobileUser() as MobileUser | null)
  const [planOpen, setPlanOpen] = useState(false)
  const [reportOpen, setReportOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [planData, setPlanData] = useState<LearningPlan | null>(null)
  const [planLoading, setPlanLoading] = useState(false)
  const [reportData, setReportData] = useState<StudentReport | null>(null)
  const [stats, setStats] = useState<StudentStats | null>(null)

  const tabs = [
    { id: 'chat', label: 'AI助教', icon: <MessageCircle size={22} />, active: false, onClick: () => navigate('/m') },
    { id: 'practice', label: '练习', icon: <PenLine size={22} />, active: false, onClick: () => navigate('/m/practice') },
    { id: 'wrong', label: '错题', icon: <BookX size={22} />, active: false, onClick: () => navigate('/m/wrong') },
    { id: 'me', label: '我的', icon: <User size={22} />, active: true, onClick: () => navigate('/m/me') },
  ]

  const loadPlan = useCallback(() => {
    if (!user) return
    setPlanLoading(true)
    api.get<LearningPlan>(`/api/diagnosis/learning-plan/${encodeURIComponent(user.id)}`)
      .then((d) => {
        if (d.plan) {
          setPlanData(d)
          setPlanLoading(false)
        } else {
          // 无计划 → 生成一份再加载
          return api.post<LearningPlan>('/api/diagnosis/learning-plan/generate', {
            student_id: user.id, class_id: user.class_id,
          }).then(() => api.get<LearningPlan>(`/api/diagnosis/learning-plan/${encodeURIComponent(user.id)}`))
            .then((d2) => {
              setPlanData(d2)
              setPlanLoading(false)
            })
        }
      })
      .catch(() => setPlanLoading(false))
  }, [user])

  useEffect(() => {
    document.title = '我的'
    if (!user) return
    api.get<DiagnosisPlan>(`/api/diagnosis/plan/${encodeURIComponent(user.id)}`).catch(() => {})
    api.get<StudentStats>(`/api/practice/student/${encodeURIComponent(user.id)}/stats`)
      .then((d) => setStats(d))
      .catch(() => setStats(null))
  }, [user])

  function openReport() {
    if (!user) return
    setReportOpen(true)
    api.get<StudentReport>(`/api/report/student/${encodeURIComponent(user.id)}`)
      .then(setReportData)
      .catch(() => setReportData({ success: false }))
  }

  if (!user) return null

  const accuracyPct = stats ? Math.round((stats.accuracy || 0) * 100) : 0
  const badges = [
    { label: accuracyPct >= 80 ? '化学达人' : accuracyPct >= 60 ? '稳步提升' : '初出茅庐', got: stats ? stats.total_answers > 0 : false },
    { label: '连续7天', got: (stats?.streak_days || 0) >= 7 },
    { label: '百题斩', got: (stats?.total_answers || 0) >= 100 },
  ]

  return (
    <MobileLayout
      theme="student"
      header={
        <MobileHeader
          title={user.name || '同学'}
          right={
            <button
              onClick={() => {
                clearMobileSession()
                navigate('/m/login', { replace: true })
              }}
              className="flex items-center gap-1 text-[12px] text-ink-muted hover:text-error cursor-pointer"
            >
              <LogOut size={13} />退出
            </button>
          }
        />
      }
      footer={<MobileTabBar tabs={tabs} />}
    >
      {/* 顶部：头像 + 班级 */}
      <div className="px-4 pt-5 pb-3 flex items-center gap-3">
        <div className="w-12 h-12 rounded-full bg-primary-soft flex items-center justify-center text-[20px] font-black text-primary font-display">
          {(user.name || '学')[0]}
        </div>
        <div>
          <div className="text-[17px] font-bold text-ink font-display">{user.name || '同学'}</div>
          <div className="text-[12px] text-ink-muted">{user.class_name || '班级未设置'} · {user.id}</div>
        </div>
      </div>

      {/* 游戏化卡（首期：连续打卡 + 积分 + 徽章，R-S-C3 900 大数字） */}
      <div className="mx-4 mb-3 p-4 rounded-lg bg-surface border border-border/60 shadow-[var(--shadow-sm)]">
        <div className="grid grid-cols-2 gap-3">
          <div className="flex items-center gap-2.5">
            <Flame size={26} className="text-warning shrink-0" />
            <div>
              <div className="font-display text-[30px] font-black text-warning leading-none kpi-number">
                {stats?.streak_days ?? '—'}
              </div>
              <div className="text-[11px] text-ink-muted mt-1">连续打卡（天）</div>
            </div>
          </div>
          <div className="flex items-center gap-2.5">
            <Star size={26} className="text-primary shrink-0" />
            <div>
              <div className="font-display text-[30px] font-black text-primary leading-none kpi-number">
                {stats?.total_answers ?? '—'}
              </div>
              <div className="text-[11px] text-ink-muted mt-1">累计积分（答题）</div>
            </div>
          </div>
        </div>
        <div className="flex gap-1.5 mt-3.5 pt-3 border-t border-border/50">
          {badges.map((b) => (
            <span
              key={b.label}
              className={`flex items-center gap-1 text-[10.5px] px-2.5 py-1 rounded-full ${
                b.got ? 'bg-primary-soft text-primary' : 'bg-surface-muted text-ink-muted opacity-60'
              }`}
            >
              <Award size={11} />{b.label}
            </span>
          ))}
        </div>
      </div>

      {/* KPI（P-06） */}
      <div className="mx-4 mb-3 grid grid-cols-3 gap-2">
        {[
          { v: stats?.week_practice_count ?? '—', l: '本周练习' },
          { v: stats ? `${accuracyPct}%` : '—', l: '正确率' },
          { v: stats?.total_answers ?? '—', l: '累计答题' },
        ].map((s) => (
          <div key={s.l} className="rounded-lg bg-surface border border-border/60 py-3.5 text-center">
            <div className="font-display text-[22px] font-black text-ink leading-none kpi-number">{s.v}</div>
            <div className="text-[11px] text-ink-muted mt-1.5">{s.l}</div>
          </div>
        ))}
      </div>

      {/* 入口列表 */}
      <div className="mx-4 mb-6 rounded-lg bg-surface border border-border/60 divide-y divide-border/50 overflow-hidden">
        {[
          { icon: <CalendarCheck size={17} className="text-primary" />, label: '学习计划', onClick: () => { setPlanOpen(true); loadPlan() } },
          { icon: <FileText size={17} className="text-primary" />, label: '学习报告', onClick: openReport },
          { icon: <RotateCcw size={17} className="text-primary" />, label: '复习中心', onClick: () => navigate('/m/review') },
          { icon: <Settings size={17} className="text-primary" />, label: '个人设置', onClick: () => setSettingsOpen(true) },
        ].map((e) => (
          <button key={e.label} onClick={e.onClick} className="w-full flex items-center gap-3 px-4 py-3.5 text-[14px] text-ink hover:bg-surface-muted transition-colors text-left cursor-pointer">
            {e.icon}
            <span className="flex-1">{e.label}</span>
            <span className="text-ink-muted">›</span>
          </button>
        ))}
      </div>

      {/* ── 学习计划面板 ── */}
      <MobileFullPane open={planOpen} title="学习计划" onClose={() => setPlanOpen(false)}>
        {planLoading ? (
          <MobileLoading />
        ) : !planData?.plan ? (
          <MobileEmpty title="暂无学习计划详情" hint="请联系老师布置，或稍后再试" />
        ) : (
          <PlanBody plan={planData.plan} />
        )}
      </MobileFullPane>

      {/* ── 学习报告面板 ── */}
      <MobileFullPane open={reportOpen} title={`${user.name || '同学'} 学习报告`} onClose={() => setReportOpen(false)}>
        {!reportData ? (
          <MobileLoading />
        ) : !reportData.success && !reportData.data ? (
          <MobileEmpty title="加载失败" hint={reportData.message || '请稍后再试'} />
        ) : (
          <ReportBody report={reportData.data || {}} />
        )}
      </MobileFullPane>

      {/* ── 设置面板 ── */}
      <MobileFullPane open={settingsOpen} title="个人设置" onClose={() => setSettingsOpen(false)}>
        <SettingsBody user={user} />
      </MobileFullPane>
    </MobileLayout>
  )
}

function PlanBody({ plan }: { plan: NonNullable<LearningPlan['plan']> }) {
  const weeks = plan.weekly_goals || []
  const tasks = plan.daily_tasks || []
  const barriers = plan.barrier_interventions || {}
  const tips = plan.motivation_tips || []
  const asText = (x: unknown) =>
    typeof x === 'string' ? x : ((x as { milestone?: string; goal?: string; text?: string; tip?: string })?.milestone || (x as { goal?: string })?.goal || (x as { text?: string })?.text || (x as { tip?: string })?.tip || '')
  return (
    <div>
      <h3 className="font-display text-[19px] font-black text-ink">{plan.plan_title || '个性化学习计划'}</h3>
      {plan.plan_period && <p className="text-[12px] text-ink-muted mt-1 mb-3">周期：{plan.plan_period}</p>}
      {weeks.length > 0 && (
        <>
          <div className="text-[13.5px] font-bold text-primary mt-4 mb-1.5">周目标</div>
          {weeks.map((g, i) => (
            <p key={i} className="text-[14px] text-ink py-1.5 border-b border-border/40">{asText(g)}</p>
          ))}
        </>
      )}
      {tasks.length > 0 && (
        <>
          <div className="text-[13.5px] font-bold text-primary mt-4 mb-1.5">每日任务</div>
          {tasks.slice(0, 14).map((t, i) => (
            <p key={i} className="text-[14px] text-ink py-1.5 border-b border-border/40">
              <span className="text-ink-muted text-[12px] mr-2">{t.day}</span>
              {t.task || t.content}
            </p>
          ))}
        </>
      )}
      {Object.keys(barriers).length > 0 && (
        <>
          <div className="text-[13.5px] font-bold text-primary mt-4 mb-1.5">障碍干预</div>
          {Object.entries(barriers).map(([b, v]) => (
            <p key={b} className="text-[14px] text-ink py-1.5 border-b border-border/40">
              <b>{BARRIER_NAMES[b] || b}</b>：{v}
            </p>
          ))}
        </>
      )}
      {tips.length > 0 && (
        <>
          <div className="text-[13.5px] font-bold text-primary mt-4 mb-1.5">激励建议</div>
          {tips.map((t, i) => (
            <p key={i} className="text-[14px] text-ink py-1.5 border-b border-border/40">{asText(t)}</p>
          ))}
        </>
      )}
      {!weeks.length && !tasks.length && plan.raw_text && (
        <p className="text-[14px] leading-[1.8] text-ink whitespace-pre-wrap">{plan.raw_text}</p>
      )}
      {!weeks.length && !tasks.length && !plan.raw_text && (
        <MobileEmpty title="暂无学习计划详情" hint="请联系老师布置" />
      )}
    </div>
  )
}

function ReportBody({ report }: { report: NonNullable<StudentReport['data']> }) {
  const barrier = report.barrier_type || {}
  const main = Object.entries(barrier).sort((a, b) => (b[1] || 0) - (a[1] || 0))[0]?.[0]
  return (
    <div>
      <div className="grid grid-cols-2 gap-2.5 mb-4">
        {[
          { v: report.exercises_completed ?? 0, l: '练习完成' },
          { v: report.avg_score != null ? `${report.avg_score}%` : '--', l: '平均正确率' },
          { v: main ? BARRIER_NAMES[main] : '--', l: '主要障碍' },
          { v: report.recent_exams ?? 0, l: '近期考试' },
        ].map((s) => (
          <div key={s.l} className="rounded-lg bg-surface border border-border/60 py-4 text-center">
            <div className="font-display text-[24px] font-black text-ink leading-none kpi-number">{s.v}</div>
            <div className="text-[11px] text-ink-muted mt-1.5">{s.l}</div>
          </div>
        ))}
      </div>
      {(report.trend || []).length > 0 && (
        <>
          <div className="text-[13.5px] font-bold text-primary mb-2">成绩趋势</div>
          <div className="space-y-1.5">
            {(report.trend || []).map((t, i) => (
              <div key={i} className="flex justify-between items-center px-3.5 py-2.5 rounded-lg bg-surface border border-border/50">
                <span className="text-[13.5px] text-ink truncate">{t.exam_name}</span>
                <span className="font-bold text-[13.5px] text-primary kpi-number">{t.score}分</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

function SettingsBody({ user }: { user: MobileUser }) {
  const [bindCode, setBindCode] = useState('加载中…')
  const [copied, setCopied] = useState(false)
  const [oldPw, setOldPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [newPw2, setNewPw2] = useState('')
  const [pwMsg, setPwMsg] = useState('')

  useEffect(() => {
    api.get<DiagnosisPlan>(`/api/diagnosis/plan/${encodeURIComponent(user.id)}`)
      .then((d) => setBindCode(d.data?.bind_code || user.bind_code || '暂无'))
      .catch(() => setBindCode('获取失败'))
  }, [user])

  function copyBindCode() {
    if (!bindCode || bindCode === '暂无' || bindCode === '加载中…') return
    navigator.clipboard.writeText(bindCode).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }).catch(() => {})
  }

  function changePassword() {
    if (!oldPw || !newPw) return setPwMsg('请填写所有密码字段')
    if (newPw !== newPw2) return setPwMsg('两次新密码不一致')
    if (newPw.length < 4) return setPwMsg('新密码至少4位')
    api.post<{ success?: boolean; message?: string; detail?: string }>('/api/auth/change-password', {
      old_password: oldPw, new_password: newPw,
    })
      .then((d) => setPwMsg(d.success ? '密码修改成功' : d.message || d.detail || '修改失败'))
      .catch(() => setPwMsg('网络错误'))
  }

  return (
    <div className="space-y-3.5">
      <div className="rounded-lg bg-surface border border-border/60 p-4">
        <div className="font-bold text-[14.5px] text-ink mb-2.5">个人信息</div>
        <div className="space-y-1.5 text-[13.5px]">
          <div className="flex justify-between"><span className="text-ink-muted">姓名</span><span className="text-ink">{user.name || '—'}</span></div>
          <div className="flex justify-between"><span className="text-ink-muted">学号</span><span className="text-ink">{user.id}</span></div>
          <div className="flex justify-between"><span className="text-ink-muted">班级</span><span className="text-ink">{user.class_name || '—'}</span></div>
        </div>
      </div>

      <div className="rounded-lg bg-surface border border-border/60 p-4">
        <div className="font-bold text-[14.5px] text-ink mb-1.5">家长绑定码</div>
        <p className="text-[12px] text-ink-muted leading-relaxed mb-2.5">将此码发给家长，家长在家长端输入后即可绑定查看你的学习情况</p>
        <div className="flex items-center gap-3">
          <span className="kpi-number text-[26px] font-black tracking-[0.35em] text-primary">{bindCode}</span>
          <button onClick={copyBindCode} className="flex items-center gap-1 px-3 py-1.5 rounded-full border border-border text-[12px] text-ink-secondary hover:bg-surface-muted cursor-pointer">
            {copied ? <Check size={12} className="text-success" /> : <Copy size={12} />}
            {copied ? '已复制' : '复制'}
          </button>
        </div>
      </div>

      <div className="rounded-lg bg-surface border border-border/60 p-4">
        <div className="font-bold text-[14.5px] text-ink mb-2.5">修改密码</div>
        <div className="space-y-2">
          <input type="password" value={oldPw} onChange={(e) => setOldPw(e.target.value)} placeholder="当前密码" className="w-full h-11 px-4 rounded-xl border-[1.5px] border-border bg-surface-muted text-[14px] text-ink placeholder:text-ink-muted outline-none focus:border-primary" />
          <input type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)} placeholder="新密码" className="w-full h-11 px-4 rounded-xl border-[1.5px] border-border bg-surface-muted text-[14px] text-ink placeholder:text-ink-muted outline-none focus:border-primary" />
          <input type="password" value={newPw2} onChange={(e) => setNewPw2(e.target.value)} placeholder="确认新密码" className="w-full h-11 px-4 rounded-xl border-[1.5px] border-border bg-surface-muted text-[14px] text-ink placeholder:text-ink-muted outline-none focus:border-primary" />
        </div>
        <button onClick={changePassword} className="w-full h-11 mt-2.5 rounded-xl bg-primary text-on-primary text-[14px] font-bold cursor-pointer">确认修改</button>
        {pwMsg && <p className={`text-center text-[12.5px] mt-2 ${pwMsg.includes('成功') ? 'text-success' : 'text-error'}`}>{pwMsg}</p>}
      </div>

      <div className="rounded-lg bg-surface border border-border/60 p-4">
        <div className="font-bold text-[14.5px] text-ink mb-1">关于</div>
        <p className="text-[12.5px] text-ink-muted leading-relaxed">智辅化学 (ChemAI) v2.0<br />面向高中化学的 AI 教学辅助平台<br />教师出题 · 学生辅导 · 家长关注</p>
      </div>
    </div>
  )
}

/* PracticePage — 练习做题（design/学生端.md）：任务列表 → 答题流 → 成绩页。
 * 三态覆盖（R-S1/S2）；提交主按钮 = 亮青实底（2026-09-14 定案 A）。 */

import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { PenLine, ChevronLeft, ChevronRight, CheckCircle2, XCircle, MessageCircle, BookX, User } from 'lucide-react'
import { api } from '../../../lib/api'
import { getMobileUser } from '../../../lib/mobile-auth'
import { MobileLayout, MobileHeader, MobileTabBar, MobileLoading, MobileEmpty } from '../../../components/mobile/MobileLayout'
import { ChemMd } from '../../../components/ChemMd'

interface PracticeTask {
  practice_id?: string
  id?: string
  title?: string
  question_count?: number
  difficulty?: string
  deadline?: string
  due_date?: string
  knowledge_points?: string[]
  status?: string
  score?: number
  total?: number
}

interface Question {
  question_id?: string
  id?: string
  content?: string
  question?: string
  options?: string[]
}

const TABS_INIT = [
  { id: 'chat', label: 'AI助教', active: false, path: '/m', icon: <MessageCircle size={22} /> },
  { id: 'practice', label: '练习', active: true, path: '/m/practice', icon: <PenLine size={22} /> },
  { id: 'wrong', label: '错题', active: false, path: '/m/wrong', icon: <BookX size={22} /> },
  { id: 'me', label: '我的', active: false, path: '/m/me', icon: <User size={22} /> },
]

function fmtDate(d?: string) {
  if (!d) return '—'
  const t = new Date(d)
  return `${t.getFullYear()}/${t.getMonth() + 1}/${t.getDate()}`
}

export function PracticePage() {
  const navigate = useNavigate()
  const [user] = useState(() => getMobileUser())
  const [view, setView] = useState<'list' | 'quiz' | 'result'>('list')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tasks, setTasks] = useState<PracticeTask[]>([])
  const [quiz, setQuiz] = useState<Question[]>([])
  const [qIdx, setQIdx] = useState(0)
  const [answers, setAnswers] = useState<Record<number, string>>({})
  const [practiceId, setPracticeId] = useState('')
  const [result, setResult] = useState<{ correct: number; total: number } | null>(null)

  const loadTasks = useCallback(() => {
    if (!user) return
    setLoading(true)
    setError('')
    api.get<{ data?: { tasks?: PracticeTask[] }; tasks?: PracticeTask[] }>(
      `/api/practice/student/${encodeURIComponent(user.id)}/tasks?page_size=50`,
    )
      .then((d) => {
        setTasks(d.data?.tasks || d.tasks || [])
        setLoading(false)
      })
      .catch((e: Error) => {
        setError(e.message)
        setLoading(false)
      })
  }, [user])

  useEffect(() => {
    document.title = '我的练习'
    loadTasks()
  }, [loadTasks])

  function startPractice(pid: string) {
    if (!user) return
    setLoading(true)
    api.get<{ data?: { questions?: Question[] }; questions?: Question[] }>(
      `/api/practice/student/${encodeURIComponent(user.id)}/practice/${encodeURIComponent(pid)}`,
    )
      .then((d) => {
        const qs = d.data?.questions || d.questions || []
        if (!qs.length) {
          setError('暂无题目')
          setLoading(false)
          return
        }
        setQuiz(qs)
        setPracticeId(pid)
        setQIdx(0)
        setAnswers({})
        setView('quiz')
        setLoading(false)
      })
      .catch((e: Error) => {
        setError(e.message)
        setLoading(false)
      })
  }

  function submit() {
    if (!user) return
    setLoading(true)
    const payload = quiz.map((q, i) => ({
      question_id: q.question_id || q.id || '',
      student_answer: answers[i] ?? '',
    }))
    api.post<{ correct_count?: number; correct?: number; total_count?: number }>('/api/practice/submit', {
      practice_id: practiceId, student_id: user.id, answers: payload,
    })
      .then((d) => {
        const correct = d.correct_count ?? d.correct ?? 0
        setResult({ correct, total: quiz.length })
        setView('result')
        setLoading(false)
      })
      .catch((e: Error) => {
        setError(e.message)
        setLoading(false)
      })
  }

  const q = quiz[qIdx]
  const pending = tasks.filter((t) => t.status !== 'completed')
  const done = tasks.filter((t) => t.status === 'completed')

  return (
    <MobileLayout
      theme="student"
      header={<MobileHeader title={view === 'quiz' ? `${qIdx + 1} / ${quiz.length}` : '我的练习'} />}
      footer={
        view === 'quiz' ? (
          /* 做题中隐藏 Tab（专注模式），底栏为导航条 */
          <div className="flex justify-between px-4 py-3 bg-bg border-t border-border/60">
            <button
              onClick={() => setQIdx((v) => Math.max(0, v - 1))}
              disabled={qIdx === 0}
              className="flex items-center gap-1 px-5 py-2.5 rounded-full border border-border bg-surface text-[14px] text-ink-secondary disabled:opacity-30"
            >
              <ChevronLeft size={15} />上一题
            </button>
            {qIdx < quiz.length - 1 ? (
              <button
                onClick={() => setQIdx((v) => Math.min(quiz.length - 1, v + 1))}
                className="flex items-center gap-1 px-7 py-2.5 rounded-full bg-primary text-on-primary text-[14px] font-bold"
              >
                下一题<ChevronRight size={15} />
              </button>
            ) : (
              <button
                onClick={submit}
                className="px-7 py-2.5 rounded-full bg-primary text-on-primary text-[14px] font-bold"
              >
                提交
              </button>
            )}
          </div>
        ) : (
          <MobileTabBar
            tabs={TABS_INIT.map((t) => ({ ...t, onClick: () => navigate(t.path) }))}
          />
        )
      }
    >
      {loading && <MobileLoading />}

      {view === 'list' && (!loading || tasks.length > 0) && (
        <div className="p-4">
          {error ? (
            <MobileEmpty title="加载失败" hint={error} action={
              <button onClick={loadTasks} className="px-5 py-2 rounded-full bg-primary text-on-primary text-[13px] font-bold">重试</button>
            } />
          ) : tasks.length === 0 ? (
            <MobileEmpty
              icon={<PenLine size={30} />}
              title="暂无练习任务"
              hint="老师布置练习后会出现在这里，先去问问 AI 助教今天学了什么吧"
            />
          ) : (
            <>
              <div className="text-[11px] text-ink-muted tracking-[0.15em] mb-2.5">待完成 · {pending.length} 项</div>
              {pending.length === 0 && <p className="text-[13px] text-ink-secondary pb-2">全部完成，太棒了！</p>}
              {pending.map((t) => (
                <button
                  key={t.practice_id || t.id}
                  onClick={() => startPractice(t.practice_id || t.id || '')}
                  className="w-full text-left p-4 mb-2 rounded-lg border border-border/70 bg-surface active:bg-surface-muted transition-colors"
                >
                  <div className="text-[15px] font-bold text-ink mb-1.5">{t.title || '练习'}</div>
                  <div className="flex gap-3 text-[12px] text-ink-secondary mb-1.5">
                    <span>{t.question_count ?? '?'} 题</span>
                    <span>{t.difficulty || '中等'}</span>
                    <span>截止 {fmtDate(t.deadline || t.due_date)}</span>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {(t.knowledge_points || []).map((k) => (
                      <span key={k} className="text-[10.5px] px-2 py-0.5 rounded-full bg-primary-soft text-primary">{k}</span>
                    ))}
                  </div>
                </button>
              ))}
              {done.length > 0 && (
                <>
                  <div className="text-[11px] text-ink-muted tracking-[0.15em] mt-5 mb-2.5">已完成 · {done.length} 项</div>
                  {done.map((t) => (
                    <div key={t.practice_id || t.id} className="p-4 mb-2 rounded-lg border border-border/50 bg-surface/60 opacity-70">
                      <div className="text-[15px] font-bold text-ink">{t.title || '练习'}</div>
                      <div className="text-[12px] text-ink-secondary mt-1">得分：{t.score ?? '?'}/{t.total ?? '?'}</div>
                    </div>
                  ))}
                </>
              )}
            </>
          )}
        </div>
      )}

      {!loading && view === 'quiz' && q && (
        <div className="p-5">
          <div className="text-[15px] leading-[1.9] text-ink mb-6">
            <ChemMd text={q.content || q.question || ''} />
          </div>
          <div className="space-y-2.5">
            {(q.options || []).map((o, i) => {
              const selected = answers[qIdx] === String(i)
              return (
                <button
                  key={i}
                  onClick={() => setAnswers((prev) => ({ ...prev, [qIdx]: String(i) }))}
                  className={`w-full text-left px-4 py-3.5 rounded-lg border-[1.5px] text-[14px] leading-relaxed transition-colors ${
                    selected
                      ? 'border-primary bg-primary-soft text-primary font-medium'
                      : 'border-border bg-surface text-ink'
                  }`}
                >
                  {String(o).replace(/^[A-F]\.\s*/, '')}
                </button>
              )
            })}
          </div>
        </div>
      )}

      {!loading && view === 'result' && result && (
        <div className="text-center pt-16 px-8">
          <div className="flex items-center justify-center gap-2 mb-2">
            <CheckCircle2 size={28} className="text-success" />
            <span className="kpi-number font-display text-[52px] font-black text-success leading-none">
              {result.correct}<span className="text-[22px] text-ink-muted font-normal">/{result.total}</span>
            </span>
          </div>
          <p className="text-[15px] text-ink-secondary mb-8">
            正确率 {result.total > 0 ? Math.round((result.correct / result.total) * 100) : 0}%
          </p>
          {result.correct === result.total ? (
            <p className="text-[13px] text-success mb-2 flex items-center justify-center gap-1"><CheckCircle2 size={14} />全对，继续保持！</p>
          ) : (
            <p className="text-[13px] text-error mb-2 flex items-center justify-center gap-1"><XCircle size={14} />错题已收入错题本</p>
          )}
          <button
            onClick={() => {
              setView('list')
              loadTasks()
            }}
            className="mt-4 px-8 py-3 rounded-full bg-primary text-on-primary text-[14px] font-bold"
          >
            返回练习列表
          </button>
        </div>
      )}
    </MobileLayout>
  )
}

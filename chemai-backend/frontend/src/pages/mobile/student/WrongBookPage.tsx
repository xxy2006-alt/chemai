/* WrongBookPage — 错题本（P-20 手风琴）：错答(红)/正解(绿)对比 + 知识点标签。 */

import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { BookX, ChevronDown, MessageCircle, PenLine, User } from 'lucide-react'
import { api } from '../../../lib/api'
import { getMobileUser } from '../../../lib/mobile-auth'
import { MobileLayout, MobileHeader, MobileTabBar, MobileLoading, MobileEmpty } from '../../../components/mobile/MobileLayout'

interface WrongQuestion {
  question_id?: string
  content?: string
  answer?: string
  your_answer?: string
  knowledge_points?: string[]
  last_error_at?: string
  wrong_count?: number
  analysis?: string
}

export function WrongBookPage() {
  const navigate = useNavigate()
  const [user] = useState(() => getMobileUser())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [items, setItems] = useState<WrongQuestion[]>([])
  const [expanded, setExpanded] = useState<string | null>(null)

  const load = useCallback(() => {
    if (!user) return
    setLoading(true)
    api.get<{ data?: { wrong_questions?: WrongQuestion[] }; wrong_questions?: WrongQuestion[] }>(
      `/api/practice/wrong/list?student_id=${encodeURIComponent(user.id)}&limit=30`,
    )
      .then((d) => {
        setItems(d.data?.wrong_questions || d.wrong_questions || [])
        setLoading(false)
      })
      .catch((e: Error) => {
        setError(e.message)
        setLoading(false)
      })
  }, [user])

  useEffect(() => {
    document.title = '错题本'
    load()
  }, [load])

  const tabs = [
    { id: 'chat', label: 'AI助教', icon: <MessageCircle size={22} />, active: false, onClick: () => navigate('/m') },
    { id: 'practice', label: '练习', icon: <PenLine size={22} />, active: false, onClick: () => navigate('/m/practice') },
    { id: 'wrong', label: '错题', icon: <BookX size={22} />, active: true, onClick: () => navigate('/m/wrong') },
    { id: 'me', label: '我的', icon: <User size={22} />, active: false, onClick: () => navigate('/m/me') },
  ]

  return (
    <MobileLayout
      theme="student"
      header={<MobileHeader title={`错题本 · ${items.length} 道`} />}
      footer={<MobileTabBar tabs={tabs} />}
    >
      {loading && items.length === 0 && <MobileLoading />}
      {!loading && error && (
        <MobileEmpty title="加载失败" hint={error} action={
          <button onClick={load} className="px-5 py-2 rounded-full bg-primary text-on-primary text-[13px] font-bold">重试</button>
        } />
      )}
      {!loading && !error && items.length === 0 && (
        <MobileEmpty
          icon={<BookX size={30} />}
          title="暂无错题记录"
          hint="做错的题会自动收进错题本，去练习页挑战一下吧"
          action={
            <button onClick={() => navigate('/m/practice')} className="px-5 py-2 rounded-full bg-primary text-on-primary text-[13px] font-bold">
              去练习
            </button>
          }
        />
      )}
      <div className="p-3.5">
        {items.map((w) => {
          const kp = (w.knowledge_points || [])[0] || '综合'
          const open = expanded === (w.question_id || w.content)
          return (
            <button
              key={w.question_id || w.content}
              onClick={() => setExpanded(open ? null : w.question_id || w.content || '')}
              className="w-full text-left p-4 mb-2 rounded-lg border border-border/70 bg-surface transition-colors"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="text-[10.5px] px-2 py-0.5 rounded-full bg-primary-soft text-primary">{kp}</span>
                    <span className="text-[11px] text-ink-muted">
                      {w.last_error_at ? new Date(w.last_error_at).toLocaleDateString('zh-CN').replace(/\//g, '/') : ''}
                      {w.wrong_count ? ` · 做错 ${w.wrong_count} 次` : ''}
                    </span>
                  </div>
                  <p className="text-[14px] leading-relaxed text-ink">{w.content}</p>
                  {open && (
                    <div className="mt-3 p-3 rounded-lg bg-error-soft/60 border border-error/20 text-[13px] leading-relaxed">
                      <p className="text-error">你的答案：{w.your_answer || '—'}</p>
                      <p className="text-success mt-0.5">正确答案：{w.answer || '—'}</p>
                      {w.analysis && <p className="text-ink-secondary mt-1.5">{w.analysis}</p>}
                    </div>
                  )}
                </div>
                <ChevronDown
                  size={18}
                  className={`text-ink-muted shrink-0 transition-transform ${open ? 'rotate-180' : ''}`}
                />
              </div>
            </button>
          )
        })}
      </div>
    </MobileLayout>
  )
}

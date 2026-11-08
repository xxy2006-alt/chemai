/* ReviewCenterPage — 复习中心：错题强化清单（只读 + 解析），从"我的"页进入。 */

import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CheckCircle2, ArrowLeft } from 'lucide-react'
import { api } from '../../../lib/api'
import { getMobileUser } from '../../../lib/mobile-auth'
import { MobileLayout, MobileHeader, MobileLoading, MobileEmpty } from '../../../components/mobile/MobileLayout'
import { ChemMd } from '../../../components/ChemMd'

interface WrongQuestion {
  content?: string
  answer?: string
  your_answer?: string
  knowledge_points?: string[]
  wrong_count?: number
  analysis?: string
}

export function ReviewCenterPage() {
  const navigate = useNavigate()
  const [user] = useState(() => getMobileUser())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [items, setItems] = useState<WrongQuestion[]>([])

  const load = useCallback(() => {
    if (!user) return
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
    document.title = '复习中心'
    load()
  }, [load])

  return (
    <MobileLayout
      theme="student"
      header={
        <MobileHeader
          title="复习中心"
          left={
            <button onClick={() => navigate('/m/me')} className="p-1.5 -ml-1.5 hover:bg-surface-muted rounded-[var(--radius-sm)] cursor-pointer" aria-label="返回">
              <ArrowLeft size={20} />
            </button>
          }
        />
      }
    >
      {loading && <MobileLoading />}
      {!loading && error && <MobileEmpty title="加载失败" hint={error} />}
      {!loading && !error && items.length === 0 && (
        <MobileEmpty
          icon={<CheckCircle2 size={30} className="text-success" />}
          title="暂无错题，继续保持！"
          hint="复习中心会汇总你近期的错题与解析"
          action={
            <button onClick={() => navigate('/m/practice')} className="px-5 py-2 rounded-full bg-primary text-on-primary text-[13px] font-bold">
              去练习
            </button>
          }
        />
      )}
      <div className="p-3.5 space-y-2.5">
        {items.map((q, i) => (
          <div key={i} className="p-4 rounded-lg border border-border/70 bg-surface">
            <div className="text-[14px] leading-relaxed text-ink mb-2">
              <ChemMd text={q.content || ''} />
            </div>
            <div className="text-[11.5px] text-ink-muted">
              知识点：{(q.knowledge_points || []).join('、') || '综合'}
              {q.wrong_count ? ` · 做错 ${q.wrong_count} 次` : ''}
            </div>
            <div className="text-[12px] mt-1.5">
              <span className="text-error">你的答案：{q.your_answer || '—'}</span>
              <span className="text-success ml-3">正确答案：{q.answer || '—'}</span>
            </div>
            {q.analysis && (
              <div className="mt-2 text-[12.5px] text-success leading-relaxed">解析：{q.analysis.slice(0, 120)}</div>
            )}
          </div>
        ))}
      </div>
    </MobileLayout>
  )
}

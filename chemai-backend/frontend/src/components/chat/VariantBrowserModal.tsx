/* VariantBrowserModal.tsx — 选真题作蓝本弹窗（变种题入口，旧版 openVariantPaper 行为）
 * 出题工作台主页面与内联面板共用：地区 → 年份 → 试卷 → 题目 → 选为蓝本 */

import { useCallback, useEffect, useState } from 'react'
import { ChevronLeft, Loader2, Pencil } from 'lucide-react'
import { api } from '../../lib/api'
import { Button, Modal, Tag } from '../ui'
import { QuestionMd } from '../QuestionMd'

interface Paper {
  name?: string
  source_key?: string
  year?: string
  question_count?: number
}

interface PaperGroup {
  region?: string
  years?: { year?: string; papers?: Paper[] }[]
}

interface BankQuestion {
  question_id?: string
  id?: string
  exam_id?: string
  question_number?: string
  source?: string
  content?: string
  answer?: string
  knowledge_points?: string[]
  page_image?: string
  region?: string
  year?: string
}

export function VariantBrowserModal({
  open,
  onClose,
  onPick,
}: {
  open: boolean
  onClose: () => void
  onPick: (q: BankQuestion, label: string) => void
}) {
  const [groups, setGroups] = useState<PaperGroup[]>([])
  const [view, setView] = useState<{ step: 'dir' } | { step: 'paper'; title: string; questions: BankQuestion[]; loading: boolean }>({ step: 'dir' })

  const loadDir = useCallback(() => {
    setView({ step: 'dir' })
    api
      .get<{ data?: { groups?: PaperGroup[] } }>('/api/exam-bank/papers')
      .then((d) => setGroups(d.data?.groups || []))
      .catch(() => setGroups([]))
  }, [])

  useEffect(() => {
    if (open) loadDir()
  }, [open, loadDir])

  async function openPaper(p: Paper, region: string) {
    const title = `${region} · ${p.year || ''} · ${p.name || '试卷'}`
    setView({ step: 'paper', title, questions: [], loading: true })
    try {
      const params = `region=${encodeURIComponent(p.source_key || p.name || region)}&year=${encodeURIComponent(p.year || '')}&page_size=200`
      const d = await api.get<{ data?: { questions?: BankQuestion[] } }>(`/api/exam-bank/historical?${params}`)
      setView({ step: 'paper', title, questions: d.data?.questions || [], loading: false })
    } catch {
      setView({ step: 'paper', title, questions: [], loading: false })
    }
  }

  function pick(q: BankQuestion) {
    onPick(q, `${q.source || ''} · #${q.question_number || ''}`)
  }

  return (
    <Modal open={open} onClose={onClose} title="选择真题作蓝本" wide hideFooter>
      {view.step === 'dir' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {groups.map((g) => (
            <div key={g.region} className="border border-border rounded-[var(--radius-md)] p-3">
              <div className="text-[13px] font-semibold text-ink mb-2">{g.region}</div>
              <div className="space-y-1">
                {(g.years || []).map((y) =>
                  (y.papers || []).map((p, pi) => (
                    <button
                      key={`${y.year}-${pi}`}
                      onClick={() => openPaper(p, g.region || '')}
                      className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-[var(--radius-sm)] text-[13px] hover:bg-teal-soft/40 transition-colors cursor-pointer"
                    >
                      <span className="text-ink">{p.name}</span>
                    </button>
                  )),
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Button size="sm" variant="secondary" onClick={loadDir}>
              <ChevronLeft size={14} />
              返回目录
            </Button>
            <span className="text-xs text-ink-muted">
              {view.title} · {view.loading ? '加载中…' : `${view.questions.length} 题`}
            </span>
          </div>
          {view.loading ? (
            <div className="flex items-center gap-2 py-8 justify-center text-ink-secondary">
              <Loader2 size={18} className="animate-spin text-teal" />
              加载题目中…
            </div>
          ) : view.questions.length === 0 ? (
            <div className="text-center py-8 text-sm text-ink-muted">该试卷暂无题目</div>
          ) : (
            <div className="space-y-2 max-h-[55vh] overflow-y-auto pr-1">
              {view.questions.map((q, i) => (
                <button
                  key={q.question_id || q.id || i}
                  onClick={() => pick(q)}
                  className="w-full text-left border border-border rounded-[var(--radius-md)] p-3 hover:border-teal/50 hover:bg-teal-soft/20 transition-colors cursor-pointer"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="w-5 h-5 rounded-full bg-primary-soft text-primary text-[11px] font-semibold flex items-center justify-center shrink-0">
                          {q.question_number || i + 1}
                        </span>
                        {(q.knowledge_points || []).slice(0, 2).map((k) => (
                          <Tag key={k} tone="gray" size="sm">
                            {k}
                          </Tag>
                        ))}
                      </div>
                      <QuestionMd text={q.content || ''} />
                    </div>
                    <span className="shrink-0 text-xs text-teal flex items-center gap-1 mt-1">
                      <Pencil size={12} />
                      作蓝本
                    </span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </Modal>
  )
}

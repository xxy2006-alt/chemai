import { useState } from 'react'
import { Send, Undo2 } from 'lucide-react'
import { api } from '../../lib/api'
import { Button, useToast } from '../ui'
import { LearningPlan } from './tool-renderers'

/** 草稿门状态（与后端 learning_plan_drafts 载荷对齐） */
export interface DraftGateState {
  draft_id: string
  student_id: string
  version: number
  status: string
  content: Record<string, unknown>
  feedback?: string
  teacher_approved?: boolean
}

/** #11 页面侧三值确认门面板：与聊天确认卡同一 REST decision 接缝（issue #11）。
 * 打回 → service 修订出新版，原地替换并重开门（多轮循环不离开页面）。 */
export function DraftGatePanel({
  studentId: sid,
  draft,
  onDraftChanged,
  onDone,
}: {
  studentId: string
  draft: DraftGateState
  onDraftChanged: (d: DraftGateState) => void
  onDone?: (action: 'approve' | 'abandon') => void
}) {
  const toast = useToast()
  const [busy, setBusy] = useState<'' | 'approve' | 'reject' | 'abandon'>('')
  const [rejectOpen, setRejectOpen] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [done, setDone] = useState<'' | 'approved' | 'abandoned'>('')
  const [histOpen, setHistOpen] = useState(false)
  const [history, setHistory] = useState<
    { version: number; content: Record<string, unknown>; feedback: string; created_at: string }[]
  >([])
  const [histLoading, setHistLoading] = useState(false)
  const [histOpenIdx, setHistOpenIdx] = useState<number | null>(null)

  async function decide(action: 'approve' | 'reject' | 'abandon') {
    if (!sid || !draft.draft_id) return
    if (action === 'reject' && !feedback.trim()) return
    setBusy(action)
    try {
      const out = await api.post<{ success: boolean; sent?: unknown; draft?: DraftGateState }>(
        `/api/diagnosis/learning-plan/draft/${sid}/${draft.draft_id}/decision`,
        { action, feedback: action === 'reject' ? feedback.trim() : '' },
      )
      if (action === 'reject' && out.draft) {
        onDraftChanged(out.draft)
        setFeedback('')
        setRejectOpen(false)
        setHistory([])
        toast.success(`已打回，修订为第 ${out.draft.version} 版`)
        return
      }
      if (action === 'approve') {
        setDone('approved')
        toast.success('已确认发送给学生')
      } else {
        setDone('abandoned')
        toast.success('已放弃本次发送（草稿保留）')
      }
      onDone?.(action === 'approve' ? 'approve' : 'abandon')
    } catch (e) {
      toast.error(`操作失败: ${e instanceof Error ? e.message : ''}`)
    } finally {
      setBusy('')
    }
  }

  async function toggleHistory() {
    const next = !histOpen
    setHistOpen(next)
    if (!next || history.length > 0 || !sid || !draft.draft_id) return
    setHistLoading(true)
    try {
      const out = await api.get<{ success: boolean; versions: typeof history }>(
        `/api/diagnosis/learning-plan/draft/${sid}/${draft.draft_id}/versions`,
      )
      setHistory(out.versions || [])
    } catch {
      toast.error('修订历史加载失败')
    } finally {
      setHistLoading(false)
    }
  }

  if (done === 'approved') {
    return <p className="text-sm text-success py-6 text-center m-0">✅ 学习计划已确认发送给学生</p>
  }
  return (
    <div>
      <div className="flex items-center gap-2 mb-2.5">
        <span className="text-[12px] text-warning bg-warning-soft rounded-[var(--radius-sm)] px-2 py-0.5">
          待确认 · 第 {draft.version} 版
        </span>
        {draft.feedback && (
          <span className="text-[12px] text-ink-muted truncate">上轮意见：{draft.feedback}</span>
        )}
      </div>
      <LearningPlan data={{ plan: draft.content }} />
      {done === 'abandoned' ? (
        <p className="mt-2.5 text-[12px] text-ink-muted m-0">
          ⊘ 已放弃本次发送（草稿保留，可稍后继续处理）
        </p>
      ) : (
        <div className="mt-2.5">
          <div className="flex gap-2">
            <Button variant="ai" size="sm" disabled={busy !== ''} onClick={() => decide('approve')}>
              <Send size={13} />
              {busy === 'approve' ? '发送中…' : '确认发送给学生'}
            </Button>
            {!rejectOpen && (
              <Button variant="secondary" size="sm" disabled={busy !== ''} onClick={() => setRejectOpen(true)}>
                <Undo2 size={13} />
                打回修改
              </Button>
            )}
            <Button variant="ghost" size="sm" disabled={busy !== ''} onClick={() => decide('abandon')}>
              放弃
            </Button>
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
              <Button variant="ai" size="sm" disabled={!feedback.trim() || busy !== ''} onClick={() => decide('reject')}>
                {busy === 'reject' ? '提交中…' : '提交'}
              </Button>
            </div>
          )}
        </div>
      )}
      <div className="mt-3">
        <button
          onClick={toggleHistory}
          className="text-[12px] text-ink-secondary hover:text-teal transition-colors cursor-pointer"
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
                    {v.feedback ? `意见：${v.feedback}` : String((v.content as { plan_title?: string })?.plan_title || '初版')}
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
    </div>
  )
}

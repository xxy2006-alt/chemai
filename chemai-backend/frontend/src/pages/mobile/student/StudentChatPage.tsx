/* StudentChatPage — AI 助教对话（门面页，design/学生端.md）：
 * 深色沉浸 + 侧滑历史会话 + 快捷 chips + ChatPanel 流式对话。 */

import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Menu, MessageCirclePlus, MessagesSquare, Trash2, X, MessageCircle, PenLine, BookX, User } from 'lucide-react'
import { api } from '../../../lib/api'
import { getMobileUser, type MobileUser } from '../../../lib/mobile-auth'
import { MobileLayout, MobileTabBar, MobileLoading } from '../../../components/mobile/MobileLayout'
import { ChatPanel } from '../../../components/mobile/ChatPanel'

interface Conversation {
  thread_id: string
  title?: string
  preview?: string
  last_at?: string
}

const CID_KEY = 'chemai_student_cid'

function loadCid(): string {
  let cid = sessionStorage.getItem(CID_KEY) || ''
  if (!cid || !cid.startsWith('m-')) {
    cid = `m-${Date.now()}`
    sessionStorage.setItem(CID_KEY, cid)
  }
  return cid
}

export function StudentChatPage() {
  const navigate = useNavigate()
  const [user] = useState<MobileUser | null>(() => getMobileUser() as MobileUser | null)
  const [cid, setCid] = useState(loadCid)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [conversations, setConversations] = useState<Conversation[] | null>(null)

  /* 历史会话列表（prefix=m- + student_id，与旧接口一致） */
  const loadConversations = useCallback(() => {
    if (!user) return
    api.get<{ conversations?: Conversation[] }>(
      `/api/agent/chat/conversations?prefix=m-&student_id=${encodeURIComponent(user.id)}`,
    )
      .then((d) =>
        setConversations(
          (d.conversations || []).sort((a, b) => ((b.last_at || '') > (a.last_at || '') ? 1 : -1)),
        ),
      )
      .catch(() => setConversations([]))
  }, [user])

  useEffect(() => {
    document.title = 'AI 化学助教'
  }, [])

  function newConversation() {
    api.post<{ thread_id: string }>('/api/agent/chat/new')
      .then((d) => {
        sessionStorage.setItem(CID_KEY, d.thread_id)
        setCid(d.thread_id)
        setDrawerOpen(false)
        loadConversations()
      })
      .catch(() => {})
  }

  function deleteConversation(tid: string) {
    setConversations((prev) => (prev ? prev.filter((c) => c.thread_id !== tid) : prev))
    api.del(`/api/agent/chat/conversations/${tid}`).catch(() => {})
  }

  if (!user) return null

  const tabs = [
    { id: 'chat', label: 'AI助教', icon: <MessageCircle size={22} />, active: true, onClick: () => navigate('/m') },
    { id: 'practice', label: '练习', icon: <PenLine size={22} />, active: false, onClick: () => navigate('/m/practice') },
    { id: 'wrong', label: '错题', icon: <BookX size={22} />, active: false, onClick: () => navigate('/m/wrong') },
    { id: 'me', label: '我的', icon: <User size={22} />, active: false, onClick: () => navigate('/m/me') },
  ]

  return (
    <MobileLayout
      theme="student"
      header={
        <div className="shrink-0 h-14 px-3 flex items-center gap-2 bg-bg border-b border-border/60">
          <button
            onClick={() => {
              loadConversations()
              setDrawerOpen(true)
            }}
            className="p-1.5 -ml-1.5 rounded-[var(--radius-sm)] hover:bg-surface-muted cursor-pointer text-ink"
            aria-label="历史对话"
          >
            <Menu size={21} />
          </button>
          <div className="flex-1 min-w-0">
            <span className="font-display font-bold text-[17px] text-ink">{user.name || '同学'}</span>
          </div>
          <span className="font-mono text-[10px] text-ink-muted tracking-[0.2em] mr-1">AI TUTOR</span>
        </div>
      }
      footer={<MobileTabBar tabs={tabs} />}
    >
      <div className="h-full">
        <ChatPanel
          persona="student"
          cid={cid}
          studentId={user.id}
          placeholder="输入化学问题…"
          quickPrompts={[
            '我想了解钠和水反应的实验',
            '帮我讲解一个化学知识点',
            '帮我检查一个化学方程式配平',
          ]}
          intro={
            <div className="text-center py-16 px-8">
              <div className="mx-auto w-14 h-14 rounded-full bg-primary-soft flex items-center justify-center mb-4">
                <MessageCircle size={26} className="text-primary" />
              </div>
              <h2 className="text-[16px] font-bold text-ink mb-1.5">你好，我是你的 AI 化学助教</h2>
              <p className="text-[13px] text-ink-secondary leading-relaxed">
                有任何化学问题都可以问我
                <br />
                我会一步一步引导你找到答案
              </p>
            </div>
          }
        />
      </div>

      {/* ── 历史会话侧滑抽屉（P-01 会话列表） ── */}
      {drawerOpen && (
        <>
          <div className="fixed inset-0 z-40 bg-black/40" onClick={() => setDrawerOpen(false)} />
          <div className="fixed top-0 left-0 bottom-0 z-50 w-[85%] max-w-[360px] bg-surface shadow-[var(--shadow-lg)] flex flex-col rounded-r-2xl">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border/60">
              <span className="font-semibold text-[15px] text-ink">历史对话</span>
              <div className="flex items-center gap-1">
                <button
                  onClick={newConversation}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-full border border-primary text-primary text-[12px] bg-transparent cursor-pointer"
                >
                  <MessageCirclePlus size={13} />
                  新建
                </button>
                <button
                  onClick={() => setDrawerOpen(false)}
                  className="p-1.5 rounded-full hover:bg-surface-muted cursor-pointer text-ink-muted"
                  aria-label="关闭"
                >
                  <X size={18} />
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-2">
              {conversations === null ? (
                <MobileLoading />
              ) : conversations.length === 0 ? (
                <p className="text-center text-[13px] text-ink-muted py-8">暂无历史对话</p>
              ) : (
                conversations.map((c) => (
                  <div
                    key={c.thread_id}
                    onClick={() => {
                      sessionStorage.setItem(CID_KEY, c.thread_id)
                      setCid(c.thread_id)
                      setDrawerOpen(false)
                    }}
                    className={`group flex items-center gap-2 px-3 py-2.5 rounded-lg mb-0.5 cursor-pointer transition-colors ${
                      c.thread_id === cid ? 'bg-primary-soft' : 'hover:bg-surface-muted'
                    }`}
                  >
                    <MessagesSquare size={14} className="text-ink-muted shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="text-[14px] font-medium text-ink truncate">{c.title || '新对话'}</div>
                      <div className="text-[12px] text-ink-muted truncate">{(c.preview || '').slice(0, 40)}</div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        deleteConversation(c.thread_id)
                      }}
                      className="opacity-0 group-hover:opacity-100 text-ink-muted hover:text-error cursor-pointer"
                      aria-label="删除"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </MobileLayout>
  )
}

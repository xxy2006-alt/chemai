import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { MessageSquarePlus, MessagesSquare, Paperclip, Send as SendIcon, Trash2, X, FileStack, FolderOpen, FolderPlus, FolderUp } from 'lucide-react'
import { Input as AntInput, Modal as AntModal } from 'antd'
import { api, getTeacherId } from '../../lib/api'
import { postStream, streamAgent, type AgentEvent, type ContextEvent } from '../../lib/agent-sse'
import { createStreamState, reduceAgentEvent, seedNewTurn, updateApprovalStatus, type StreamState, type PlanStepStatus, type ApprovalStatus } from '../../lib/agent-stream-reducer'
import type { GateDecision } from '../../components/chat/ApprovalCard'
import type { OrbState } from 'thinking-orbs'
import { formatChemicalText } from '../../lib/chem-format'
import { useLiveTimer } from '../../lib/use-live-timer'
import { Button, useToast } from '../../components/ui'
import { MessageList, type ChatItem } from '../../components/chat/MessageList'
import type { ToolCardData } from '../../components/chat/ToolCard'
import { SuggestionGroup } from '../../components/chat/SuggestionGroup'
import { ContextMeter } from '../../components/chat/ContextMeter'
import { estimateContextFromHistory } from '../../lib/context-meter'

interface Conversation {
  thread_id: string
  title: string
  preview?: string
  last_at?: string
  message_count?: number
}

let uid = 0
const nid = () => `m${Date.now()}_${uid++}`

/** Agent 工作台（原对话工作台）· Phase 1 迁移（原 index.html + js/agent.js） */
export function ChatPage() {
  const navigate = useNavigate()
  const toast = useToast()
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatItem[]>([])
  const [streaming, setStreaming] = useState(false)
  const [phase, setPhase] = useState('')
  // thinking-orbs 动画状态（thinking→breathing / 执行中→working / reply→composing）
  const [orb, setOrb] = useState<OrbState | ''>('')
  const [input, setInput] = useState('')
  // 上下文占用(SSE context 事件更新;历史加载用启发式估算占位)
  const [ctxInfo, setCtxInfo] = useState<ContextEvent | null>(null)
  const [fileAccess, setFileAccess] = useState<'off' | 'workspace' | 'full'>('workspace')
  const [workspacePath, setWorkspacePath] = useState(
    () => localStorage.getItem('chemai_workspace') || '',
  )
  // 工作区选择器（服务器端目录浏览）
  const [wsPickerOpen, setWsPickerOpen] = useState(false)
  const [wsCurrent, setWsCurrent] = useState('')
  const [wsParent, setWsParent] = useState<string | null>(null)
  const [wsDirs, setWsDirs] = useState<string[]>([])
  const [wsNewFolder, setWsNewFolder] = useState('')
  const [wsDefault, setWsDefault] = useState('')
  const [convOpen, setConvOpen] = useState(true)  // 对话列表默认展开，可折叠
  const inputRef = useRef<HTMLTextAreaElement>(null)
  // 旧版 live-timer：流式期间每 100ms 跳动（1 位小数秒），显示在气泡思考状态内
  const elapsed = useLiveTimer(streaming)

  // 消息列表同步引用（发送消息时需读取当前完整列表种入 reducer 状态，避免旧消息丢失）
  const messagesRef = useRef<ChatItem[]>([])
  const applyMessages = useCallback((items: ChatItem[]) => {
    messagesRef.current = items
    setMessages(items)
  }, [])
  const appendMessage = useCallback((item: ChatItem) => {
    messagesRef.current = [...messagesRef.current, item]
    setMessages(messagesRef.current)
  }, [])

  // 流式会话状态（避免闭包过期）：SSE 事件经纯函数归约器（agent-stream-reducer）处理
  const streamRef = useRef<{
    state: StreamState
    history: { role: string; content: string }[]
  }>({ state: createStreamState(), history: [] })

  const streamingRef = useRef(false)
  streamingRef.current = streaming

  /* ── 对话列表 ── */
  const loadConversations = useCallback(async () => {
    try {
      const d = await api.get<{ conversations: Conversation[] }>(
        '/api/agent/chat/conversations?prefix=t-,c',
      )
      const list = d.conversations || []
      setConversations(list)
      if (list.length && !activeId) {
        const best = list[0]
        setActiveId(best.thread_id)
        loadHistory(best.thread_id)
      }
    } catch {
      /* 服务端不可用：静默 */
    }
  }, [activeId])

  const loadHistory = useCallback(async (threadId: string) => {
    try {
      const d = await api.get<{
        messages: ({ type?: string; role?: string; name?: string; status?: string; content?: string; data?: unknown; raw?: string })[]
        run?: { run_id: string; goal: string; steps: { step: number; skill: string; description: string; status: PlanStepStatus }[] } | null
        gate?: { draft_id: string; student_id: string; version: number; action: string; message: string; gate_id?: string } | null
      }>(`/api/agent/chat/history/${threadId}`)
      // 2026-08 记录恢复：历史含完整结构（user/ai/tool），重开对话后
      // 工具卡与结果（图表/文件内容）完整还原，不再只剩文本。
      const items: ChatItem[] = (d.messages || []).flatMap((m) => {
        if (m.type === 'tool') {
          const card: ToolCardData = {
            tool: m.name || '',
            status: m.status === 'error' ? 'error' : 'done',
            data: (m.data as ToolCardData['data']) ?? (m.raw ? { raw: m.raw } : undefined),
          }
          return [{ id: nid(), kind: 'tool', card } as ChatItem]
        }
        // 旧协议 {role, content} 兼容
        const role = m.type ?? (m.role === 'user' || m.role === 'human' ? 'user' : 'ai')
        const text = m.content || ''
        if (role === 'user') return [{ id: nid(), kind: 'user', text } as ChatItem]
        if (!text.trim()) return [] // 空气泡不复现
        return [{ id: nid(), kind: 'ai', text, streaming: false } as ChatItem]
      })
      // 2026-08 DSH 式：工具调用前的 AI 文本在历史里同样折叠为思考行
      for (let i = 0; i < items.length - 1; i++) {
        if (items[i].kind === 'ai' && items[i + 1].kind === 'tool') {
          items[i] = { ...items[i], kind: 'think' } as ChatItem
        }
      }
      // ADR-0013 重同步：刷新/重开后 todolist 与待确认门不丢
      if (d.run && Array.isArray(d.run.steps) && d.run.steps.length > 0) {
        items.push({
          id: nid(),
          kind: 'plan',
          plan: {
            goal: d.run.goal,
            total_steps: d.run.steps.length,
            steps: d.run.steps,
          },
        } as ChatItem)
      }
      if (d.gate && d.gate.draft_id) {
        items.push({
          id: nid(),
          kind: 'approval',
          approval: {
            text: d.gate.message || '学习计划等待确认',
            status: 'pending',
            // ADR-0015：按钮文案由门自己的数据渲染——历史恢复不得默认 send_student
            //（曾把家长门渲染成「发送给学生」）
            action: d.gate.action || '',
            draft_id: d.gate.draft_id,
            version: d.gate.version,
            gate_id: d.gate.gate_id,
          },
        } as ChatItem)
      }
      applyMessages(items)
      setCtxInfo(estimateContextFromHistory(items))
      streamRef.current.history = items.flatMap((it): { role: string; content: string }[] =>
        it.kind === 'user'
          ? [{ role: 'user', content: it.text }]
          : it.kind === 'ai'
            ? [{ role: 'assistant', content: it.text }]
            : [],
      )
      streamRef.current.state = { ...createStreamState(), items }
    } catch {
      /* ignore */
    }
  }, [applyMessages])

  useEffect(() => {
    loadConversations()
    // 上传卡操作事件
    const onSend = (e: Event) => {
      const detail = (e as CustomEvent<string>).detail
      if (detail) sendMessage(detail)
    }
    window.addEventListener('chemai:send', onSend)
    return () => window.removeEventListener('chemai:send', onSend)
  }, [])

  async function selectConversation(id: string) {
    if (streamingRef.current) return
    setActiveId(id)
    setConvOpen(false)
    await loadHistory(id)
  }

  async function newConversation() {
    if (streamingRef.current) return
    try {
      const d = await api.post<{ thread_id: string }>('/api/agent/chat/new?prefix=t-')
      const id = d.thread_id
      setActiveId(id)
      applyMessages([])
      setCtxInfo(null)
      streamRef.current.history = []
      streamRef.current.state = createStreamState()
      setConversations((prev) => [
        { thread_id: id, title: '新对话', last_at: new Date().toISOString() },
        ...prev.filter((c) => c.thread_id !== id),
      ])
    } catch (e) {
      toast.error(`新建对话失败: ${e instanceof Error ? e.message : ''}`)
    }
  }

  async function deleteConversation(id: string) {
    if (streamingRef.current) return
    try {
      await api.del(`/api/agent/chat/conversations/${id}`)
    } catch {
      /* 后端删除失败也本地移除 */
    }
    const rest = conversations.filter((c) => c.thread_id !== id)
    setConversations(rest)
    if (activeId === id) {
      setActiveId(null)
      applyMessages([])
      setCtxInfo(null)
      streamRef.current.history = []
    }
  }

  /* ── 流式对话（事件经纯函数归约器处理，行为由 evals 回归测试锁定） ── */
  const handleEvent = useCallback(
    (evt: AgentEvent) => {
      const s = streamRef.current
      // 上下文占用是独立 UI 状态,不进消息 reducer
      if (evt.type === 'context') {
        setCtxInfo(evt)
        return
      }
      const next = reduceAgentEvent(s.state, evt, {
        newId: nid,
        onNavigate: (path, params) => {
          // 旧版行为：navigate 参数（focus 学号 / action）经 sessionStorage 交给目标页
          // 消费（如学生页自动打开李世睿抽屉并生成学习方案）
          if (params && Object.keys(params).length > 0) {
            sessionStorage.setItem('chemai_navigate_params', JSON.stringify(params))
          }
          navigate(path)
        },
      })
      s.state = next
      applyMessages(next.items)
      setPhase(next.phase)
      setOrb(next.orb)
    },
    [navigate, applyMessages],
  )

  async function runStream(resp: Response) {
    await streamAgent(resp, {
      onEvent: handleEvent,
      onDone: () => {
        setStreaming(false)
        setPhase('')
        setOrb('')
        const s = streamRef.current
        s.state = {
          ...s.state,
          aiId: null,
          // 2026-08：流结束兜底清除空 AI 气泡（白块不复现），
          // 思考行与工具卡保留
          items: s.state.items
            .map((it) =>
              it.kind === 'ai' && it.streaming ? { ...it, streaming: false } : it,
            )
            .filter((it) => !(it.kind === 'ai' && !it.text.trim())),
        }
        applyMessages(s.state.items)
        loadConversations()
      },
      onError: (m) => {
        setStreaming(false)
        setPhase('')
        setOrb('')
        toast.error(m)
      },
      onAbnormalEnd: () => {
        // ADR-0016：流被掐断 ≠ 正常完成——重同步历史（run/门/步状态以 DB 为准）
        setStreaming(false)
        setPhase('')
        setOrb('')
        if (activeId) loadHistory(activeId).catch(() => {})
        toast.info('连接中断，已重新同步会话状态')
      },
    })
  }

  async function sendMessage(text: string) {
    const msg = text.trim()
    if (!msg || streamingRef.current) return

    let convId: string = activeId ?? ''
    if (!convId) {
      try {
        const d = await api.post<{ thread_id: string }>('/api/agent/chat/new?prefix=t-')
        convId = d.thread_id
        setActiveId(convId)
        setConversations((prev) => [
          { thread_id: convId, title: '新对话', last_at: new Date().toISOString() },
          ...prev,
        ])
      } catch {
        toast.error('无法创建对话，请检查服务是否启动')
        return
      }
    }

    const s = streamRef.current
    // ADR-0013 确认门通道：待确认卡存在时，老师打字 = 打回+反馈
    // （进确定性修订循环），不再当作全新消息、更不会假批准旧卡
    const pendingGate = messagesRef.current.find(
      (it) => it.kind === 'approval' && it.approval.status === 'pending',
    )
    if (pendingGate && pendingGate.kind === 'approval') {
      const gateDraft = pendingGate.approval.draft_id
      if (gateDraft) {
        applyMessages(updateApprovalStatus(messagesRef.current, 'rejected'))
        const seeded2 = seedNewTurn(messagesRef.current, msg, nid)
        s.state = seeded2.state
        applyMessages(seeded2.items)
        setInput('')
        setStreaming(true)
        setPhase('按意见修订中…')
        setOrb('working')
        try {
          const resp = await postStream('/api/agent/chat/langgraph/resume', {
            message: msg,
            conversationId: convId,
            resume: true,
            decision: { action: 'reject', feedback: msg, draft_id: gateDraft },
          })
          await runStream(resp)
        } catch (e) {
          toast.error(`操作失败: ${e instanceof Error ? e.message : e}`)
          setStreaming(false)
        }
        return
      }
      // 布尔门（无修订能力）：保持旧行为——新消息流转，门由后端作废
      applyMessages(updateApprovalStatus(messagesRef.current, 'cancelled'))
    }
    // 以当前完整消息列表（含旧对话）种入 reducer 状态，避免首事件到达时覆盖丢失
    const seeded = seedNewTurn(messagesRef.current, msg, nid)
    s.state = seeded.state
    applyMessages(seeded.items)

    setInput('')
    const history = s.history.map((h) => ({ role: h.role, content: h.content }))
    s.history.push({ role: 'user', content: msg })

    setStreaming(true)
    setPhase('分析中…')
    setOrb('breathing')

    try {
      const resp = await postStream('/api/agent/chat/langgraph/stream', {
        message: msg,
        conversationId: convId,
        history,
        file_access: fileAccess,
        workspace: workspacePath,
      })
      await runStream(resp)
    } catch (e) {
      setStreaming(false)
      setPhase('')
      const s2 = streamRef.current
      if (s2.state.aiId) {
        const aid = s2.state.aiId
        applyMessages(
          s2.state.items.map((it) =>
            it.kind === 'ai' && it.id === aid ? { ...it, text: `⚠ 请求失败：${e instanceof Error ? e.message : e}`, streaming: false } : it,
          ),
        )
      }
      s2.state = { ...s2.state, aiId: null }
    }
  }

  /** ADR-0013 确认门三值决定：批准（发送+继续）/ 打回（带反馈，修订后再确认）/ 放弃（跳过继续）。
   * ADR-0015：decision 必带 gate_id（一决定一动作）；流式期间禁止重复提交（409 前端防线）。 */
  async function handleDecision(decision: GateDecision, feedback?: string, draftId?: string, gateId?: string) {
    if (streamingRef.current) {
      toast.info('上一条回复还在处理中，请稍候')
      return
    }
    const statusMap: Record<GateDecision, ApprovalStatus> = {
      approve: 'approved',
      reject: 'rejected',
      abandon: 'abandoned',
    }
    const s = streamRef.current
    s.state = { ...s.state, items: updateApprovalStatus(s.state.items, statusMap[decision]) }
    applyMessages(updateApprovalStatus(messagesRef.current, statusMap[decision]))
    if (!activeId) return
    if (decision === 'reject') {
      // 打回反馈以用户消息形式入列（老师能看到自己说了什么）
      const seeded = seedNewTurn(messagesRef.current, feedback || '', nid)
      s.state = seeded.state
      applyMessages(seeded.items)
    }
    setStreaming(true)
    setPhase(decision === 'approve' ? '已批准，继续执行…' : decision === 'reject' ? '按意见修订中…' : '继续执行…')
    setOrb(decision === 'approve' ? 'working' : decision === 'reject' ? 'working' : 'breathing')
    try {
      const resp = await postStream('/api/agent/chat/langgraph/resume', {
        message: decision === 'approve' ? 'approved' : feedback || '',
        conversationId: activeId,
        resume: true,
        decision: { action: decision, feedback, draft_id: draftId, gate_id: gateId },
      })
      await runStream(resp)
    } catch (e) {
      toast.error(`操作失败: ${e instanceof Error ? e.message : e}`)
      setStreaming(false)
    }
  }

  /* ── 上传 ── */
  async function handleFileUpload(file: File) {
    if (file.size > 10 * 1024 * 1024) {
      toast.warning('文件不能超过 10MB')
      return
    }
    const fd = new FormData()
    fd.append('file', file)
    appendMessage({ id: nid(), kind: 'user', text: `📎 上传文件: ${file.name}` })
    try {
      const d = await api.post<{
        upload_id: string
        file_name: string
        preview_text?: string
        actions: { id: string; label: string }[]
      }>('/api/agent/upload', fd)
      appendMessage({
        id: nid(),
        kind: 'upload',
        file_name: d.file_name || file.name,
        preview: d.preview_text || '',
        upload_id: d.upload_id,
        actions: d.actions || [],
      })
    } catch (e) {
      appendMessage({ id: nid(), kind: 'system', text: `⚠ 上传失败: ${e instanceof Error ? e.message : ''}` })
    }
  }

  /* ── 批量上传答题卡 ── */
  async function handleBatchUpload(files: File[]) {
    if (!files.length) return
    if (files.length > 10) {
      toast.warning('一次最多上传 10 张答题卡')
      return
    }
    for (const f of files) {
      if (f.size > 10 * 1024 * 1024) {
        toast.warning('单张答题卡不能超过 10MB')
        return
      }
    }
    const fd = new FormData()
    fd.append('teacher_id', getTeacherId())
    files.forEach((f) => fd.append('files', f))
    appendMessage({ id: nid(), kind: 'user', text: `已选择 ${files.length} 张答题卡，正在提交识别…` })
    try {
      const d = await api.post<{ success: boolean; batch_id: string; count: number; detail?: string }>(
        '/api/ocr/tasks/batch',
        fd,
      )
      if (!d.success || !d.batch_id) {
        appendMessage({ id: nid(), kind: 'system', text: `⚠ 批量上传失败: ${d.detail || '未知错误'}` })
        return
      }
      await sendMessage(
        `我已上传 ${d.count} 张答题卡，批次号 ${d.batch_id}（teacher_id=${getTeacherId()}）。请识别这批答题卡并批改。`,
      )
    } catch (e) {
      appendMessage({ id: nid(), kind: 'system', text: `⚠ 批量上传失败: ${e instanceof Error ? e.message : ''}` })
    }
  }

  /* ── 输入区 ── */
  const chemPreview = useMemo(() => {
    const raw = input.trim()
    if (!raw) return ''
    const formatted = formatChemicalText(raw)
    return formatted === raw ? '' : formatted
  }, [input])

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  /* ── 工作区选择器（服务器端目录浏览，支持新建文件夹） ── */
  async function loadWsDirs(path: string) {
    try {
      const d = await api.get<{ current: string; parent: string | null; dirs: string[]; default_ws: string }>(
        `/api/workspace/dirs?path=${encodeURIComponent(path)}`,
      )
      setWsCurrent(d.current)
      setWsParent(d.parent)
      setWsDirs(d.dirs)
      setWsDefault(d.default_ws)
    } catch (e) {
      toast.error(`目录读取失败: ${e instanceof Error ? e.message : ''}`)
    }
  }

  function openWsPicker() {
    setWsPickerOpen(true)
    loadWsDirs(workspacePath)
  }

  async function enterWsDir(name: string) {
    const sep = wsCurrent.includes('\\') ? '\\' : '/'
    const joined = wsCurrent
      ? `${wsCurrent}${wsCurrent.endsWith('/') || wsCurrent.endsWith('\\') ? '' : sep}${name}`
      : name
    await loadWsDirs(joined)
  }

  async function wsGoUp() {
    if (wsParent) await loadWsDirs(wsParent)
  }

  async function wsCreateFolder() {
    if (!wsNewFolder.trim()) return
    try {
      await api.post('/api/workspace/mkdir', { path: wsCurrent, name: wsNewFolder.trim() })
      setWsNewFolder('')
      await loadWsDirs(wsCurrent)
    } catch (e) {
      toast.error(`新建失败: ${e instanceof Error ? e.message : ''}`)
    }
  }

  function wsConfirmPick() {
    const picked = wsCurrent || wsDefault
    setWorkspacePath(picked)
    localStorage.setItem('chemai_workspace', picked)
    setWsPickerOpen(false)
  }

  async function wsUseDefault() {
    try {
      const d = await api.get<{ path: string }>('/api/workspace/default')
      setWorkspacePath(d.path)
      localStorage.setItem('chemai_workspace', d.path)
      setWsPickerOpen(false)
    } catch (e) {
      toast.error(`获取默认工作区失败: ${e instanceof Error ? e.message : ''}`)
    }
  }

  return (
    /* AI 工作台（v2.1）：氛围底图上的浅色玻璃舱——磨砂卡 + 品牌青 AI 气泡 + 渐变主按钮 */
      <div className="h-full flex gap-4 min-h-0 animate-fade-in-up">
      {/* 会话列表面板（可折叠） */}
      <div
        className={`${
          convOpen ? 'flex' : 'hidden'
        } flex-col w-[240px] shrink-0 bg-white/70 backdrop-blur-md border border-white/90 rounded-[var(--radius-lg)] shadow-[var(--shadow-sm)] overflow-hidden`}
      >
        <div className="p-3 border-b border-border">
          <Button size="sm" className="w-full justify-center" onClick={newConversation}>
            <MessageSquarePlus size={14} />
            新建对话
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {conversations.length === 0 ? (
            <div className="text-center text-xs text-ink-muted py-8 px-4">暂无对话记录</div>
          ) : (
            conversations.map((c) => (
              <div
                key={c.thread_id}
                onClick={() => selectConversation(c.thread_id)}
                className={`group flex items-center gap-2 px-2.5 py-2 rounded-[var(--radius-md)] cursor-pointer transition-colors ${
                  activeId === c.thread_id ? 'bg-primary-soft' : 'hover:bg-surface-muted'
                }`}
              >
                <MessagesSquare size={14} className="text-ink-muted shrink-0" />
                <span
                  className={`flex-1 text-[13px] truncate ${activeId === c.thread_id ? 'text-primary font-medium' : 'text-ink-secondary'}`}
                >
                  {c.title || '新对话'}
                </span>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    deleteConversation(c.thread_id)
                  }}
                  className="opacity-0 group-hover:opacity-100 text-ink-muted hover:text-error transition-all cursor-pointer"
                  title="删除对话"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* 主聊天区 */}
      <div className="flex-1 min-w-0 bg-white/75 backdrop-blur-md border border-white/90 rounded-[var(--radius-lg)] shadow-[var(--shadow-sm)] flex flex-col overflow-hidden">
        <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
          <button
            className="p-1.5 rounded-[var(--radius-sm)] text-ink-secondary hover:bg-surface-muted cursor-pointer"
            onClick={() => setConvOpen((v) => !v)}
            title="折叠/展开对话列表"
          >
            <MessagesSquare size={16} />
          </button>
          <span className="text-sm font-medium text-ink">CHEMAI · 教研助手</span>
        </div>

        <MessageList items={messages} phase={phase} orb={orb} streaming={streaming} elapsed={elapsed} onApproval={handleDecision} />

        {/* 快捷建议 + 化学式预览 + 输入区 */}
        <div className="border-t border-border px-4 pt-3 pb-4">
          {messages.length === 0 && (
            <div className="mb-3">
              <SuggestionGroup
                disabled={streaming}
                onPick={(prompt) => {
                  // 建议卡是**半句模板**（「请帮我配平化学方程式：」）—— 填进输入框
                  // 让老师补完再手动发；直接发送等于把残句丢给 agent。
                  setInput(prompt)
                  inputRef.current?.focus()
                }}
              />
            </div>
          )}
          {chemPreview && (
            <div className="mb-2 px-3 py-2 rounded-[var(--radius-md)] bg-teal-soft/60 border border-teal/20 chem-mono text-[14px] text-teal">
              {chemPreview}
            </div>
          )}
          {/* 输入框独占一行 */}
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="输入化学教学问题，Enter 发送，Shift+Enter 换行…"
            rows={2}
            className="w-full resize-none border border-border rounded-[var(--radius-md)] px-4 py-3 text-[15px] text-ink placeholder:text-ink-muted outline-none focus:border-primary focus:ring-2 focus:ring-primary/15 transition-colors min-h-[64px]"
            style={{ maxHeight: 180 }}
            disabled={streaming}
          />

          {/* 工具栏（WorkBuddy 式：工作区开关/选择、新对话、上传全部收在输入区下方） */}
          <div className="mt-2.5 flex items-center gap-2 flex-wrap">
            <button
              className="flex items-center gap-1.5 h-8 px-2.5 rounded-[var(--radius-md)] text-xs text-ink-secondary hover:bg-surface-muted transition-colors cursor-pointer shrink-0"
              onClick={newConversation}
              title="新建对话"
            >
              <MessageSquarePlus size={14} />
              新对话
            </button>
            <select
              value={fileAccess}
              onChange={(e) => setFileAccess(e.target.value as 'off' | 'workspace' | 'full')}
              title="文件访问档位：工作区=只在老师工作文件夹内自由读写，区外需你批准（推荐）；完全访问=全路径放行，区外不再弹卡（破坏性操作仍会请你确认）；关闭=禁用全部文件与命令"
              className="h-8 shrink-0 border border-border rounded-[var(--radius-md)] px-2 text-xs text-ink outline-none focus:border-primary bg-surface"
            >
              <option value="workspace">🗂 工作区（默认）</option>
              <option value="full">⚡ 完全访问</option>
              <option value="off">🚫 关闭</option>
            </select>
            <button
              className="flex items-center gap-1.5 h-8 px-2.5 rounded-[var(--radius-md)] text-xs text-ink-secondary hover:bg-surface-muted transition-colors cursor-pointer max-w-[280px] shrink-0"
              onClick={openWsPicker}
              title={`打开目录选择工作区（可新建文件夹）${workspacePath ? ` · 当前：${workspacePath}` : ''}`}
            >
              <FolderOpen size={14} />
              <span className="truncate">
                {workspacePath ? workspacePath.split(/[\\/]/).filter(Boolean).pop() : '默认'}
              </span>
            </button>
            <label
              className="flex items-center justify-center w-8 h-8 rounded-[var(--radius-md)] text-ink-muted hover:bg-surface-muted hover:text-teal transition-colors cursor-pointer shrink-0"
              title="上传文件"
            >
              <Paperclip size={16} />
              <input
                type="file"
                accept="image/*,.pdf,.doc,.docx"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  if (f) handleFileUpload(f)
                  e.target.value = ''
                }}
              />
            </label>
            <label
              className="flex items-center justify-center w-8 h-8 rounded-[var(--radius-md)] text-ink-muted hover:bg-surface-muted hover:text-teal transition-colors cursor-pointer shrink-0"
              title="批量上传答题卡（≤10 张）"
            >
              <FileStack size={16} />
              <input
                type="file"
                accept="image/*"
                multiple
                className="hidden"
                onChange={(e) => {
                  const files = Array.from(e.target.files || [])
                  handleBatchUpload(files)
                  e.target.value = ''
                }}
              />
            </label>

            {/* 右侧:上下文占用环 + 发送(与工具栏对齐) */}
            <div className="ml-auto flex items-center gap-2 shrink-0">
              <ContextMeter info={ctxInfo} />
              {streaming ? (
                <Button variant="secondary" size="md" disabled>
                  <X size={15} />
                  生成中
                </Button>
              ) : (
                <Button size="md" onClick={() => sendMessage(input)} disabled={!input.trim()}>
                  <SendIcon size={15} />
                  发送
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 工作区选择器（服务器端目录浏览 + 新建文件夹） */}
      <AntModal
        open={wsPickerOpen}
        onCancel={() => setWsPickerOpen(false)}
        onOk={wsConfirmPick}
        okText="选择此目录"
        cancelText="取消"
        title="选择工作区文件夹"
        width={520}
      >
        <div className="mb-2 text-xs text-ink-secondary break-all">
          当前：<span className="text-ink font-medium">{wsCurrent || '（磁盘根）'}</span>
        </div>
        <div className="flex items-center gap-2 mb-2">
          <button
            className="flex items-center gap-1 h-7 px-2 rounded-[var(--radius-md)] text-xs text-ink-secondary hover:bg-surface-muted cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
            onClick={wsGoUp}
            disabled={!wsParent}
          >
            <FolderUp size={14} />
            上一级
          </button>
          <button
            className="flex items-center gap-1 h-7 px-2 rounded-[var(--radius-md)] text-xs text-ink-secondary hover:bg-surface-muted cursor-pointer"
            onClick={wsUseDefault}
          >
            使用默认（~/ChemAI-Workspace）
          </button>
        </div>
        <div className="border border-border rounded-[var(--radius-md)] max-h-64 overflow-y-auto mb-3">
          {wsDirs.length === 0 ? (
            <div className="px-3 py-6 text-center text-xs text-ink-muted">此目录下没有子文件夹</div>
          ) : (
            wsDirs.map((d) => (
              <div
                key={d}
                onClick={() => enterWsDir(d)}
                className="flex items-center gap-2 px-3 py-2 text-[13px] text-ink cursor-pointer hover:bg-surface-muted border-b border-border/50 last:border-b-0"
              >
                <FolderPlus size={14} className="text-ink-muted" />
                {d}
              </div>
            ))
          )}
        </div>
        <div className="flex items-center gap-2">
          <AntInput
            value={wsNewFolder}
            onChange={(e) => setWsNewFolder(e.target.value)}
            onPressEnter={wsCreateFolder}
            placeholder="新文件夹名（在此目录下创建）"
            size="small"
          />
          <button
            className="h-7 px-3 rounded-[var(--radius-md)] bg-primary text-white text-xs hover:opacity-90 cursor-pointer shrink-0"
            onClick={wsCreateFolder}
          >
            新建文件夹
          </button>
        </div>
      </AntModal>
      </div>
  )
}

/* agent-sse.ts — js/agent.js SSE 流解析的 TS 移植
 * 协议与后端 agent/channel/langgraph_sse_v2.py 输出对齐（v2 单 Agent） */

import { getToken } from './api'

export type ToolStatus = 'running' | 'done' | 'error' | 'paused'

export interface ToolCallEvent {
  type: 'tool_call'
  name: string
  args?: unknown
}

export interface ToolResultEvent {
  type: 'tool_result'
  name: string
  success?: boolean
  data?: unknown
  /** 确定性审批重放补发的结果载荷（JSON 字符串），普通 tool_result 只有 data */
  result?: unknown
}

export interface ToolErrorEvent {
  type: 'tool_error'
  name: string
  message?: string
}

export interface TextEvent {
  type: 'text'
  content: string
}

export interface PhaseEvent {
  type: 'phase'
  phase: string
  message?: string
  /** 2026-08 发送确认门：动态按钮文案标记（send_student/send_parent） */
  action?: string
  /** ADR-0013 三值门：门挂在草稿实体上，draft_id 缺失 = 布尔门（无修订能力） */
  draft_id?: string
  version?: number
}

export interface StepEvent {
  type: 'step'
  skill?: string
  current?: number
}

export interface ErrorEvent {
  type: 'error'
  message?: string
  recoverable?: boolean
}

export interface RouteEvent {
  type: 'route'
  [k: string]: unknown
}

export interface SubAgentEvents {
  type: 'sub_agent_start' | 'sub_agent_end' | 'subagent_text'
  agent?: string
  content?: string
}

export interface ComponentEvent {
  type: 'component'
  component: string
  params?: Record<string, unknown>
}

export interface NavigateEvent {
  type: 'navigate'
  page: string
  params?: Record<string, unknown>
}

export interface PlanEvent {
  type: 'plan_summary' | 'plan_progress'
  [k: string]: unknown
}

export interface ExamImagesEvent {
  type: 'exam_images'
  urls?: string[]
  q_index?: number
  title?: string
}

/** 上下文占用(后端 context_meter 每次流式回复结束时下发) */
export interface ContextEvent {
  type: 'context'
  /** 已用 token(provider usage 锚定,无 usage 时启发式估算) */
  used_tokens: number
  /** 模型上下文窗口容量 */
  context_window: number
  /** 占用百分比 0-100 */
  percent: number
  breakdown: {
    system_tokens: number
    tools_tokens: number
    message_tokens: number
  }
}

export interface DoneEvent {
  type: 'done'
}

/** ADR-0015 阶段 4 事件契约：确认门开启（等待人工决定）。
 * gate_id 是决定与动作的强绑定键——批准哪张卡，就执行哪个动作。 */
export interface GateOpenEvent {
  type: 'gate_open'
  gate_id: string
  message?: string
  action?: string
  /** 收件人语义：student=发送给学生 / parent=同步给家长 / system=系统级（按次审批等） */
  recipient?: 'student' | 'parent' | 'system'
  draft_id?: string
  version?: number
}

/** ADR-0016 Paused Run：系统挂起（断线/中断/超时），与等待人工是两个状态。
 * 恢复永远是显式人工动作（发下一条消息 / 决定一个门）。 */
export interface RunPausedEvent {
  type: 'run_paused'
  reason?: string
  message?: string
}

export type AgentEvent =
  | ToolCallEvent
  | ToolResultEvent
  | ToolErrorEvent
  | TextEvent
  | PhaseEvent
  | StepEvent
  | ErrorEvent
  | RouteEvent
  | SubAgentEvents
  | ComponentEvent
  | NavigateEvent
  | PlanEvent
  | ExamImagesEvent
  | ContextEvent
  | GateOpenEvent
  | RunPausedEvent
  | DoneEvent

export interface AgentHandlers {
  onEvent: (evt: AgentEvent) => void
  onDone?: () => void
  onError?: (message: string) => void
  /** ADR-0016：流异常终止（无 [DONE]）——触发 /history 重同步，不伪装成正常完成 */
  onAbnormalEnd?: () => void
}

export interface StreamParams {
  message: string
  conversationId: string
  history?: { role: string; content: string }[]
  provider?: string
  persona?: string
  /** 学生端对话：助手以该学生为上下文（家长 persona 也会携带） */
  studentId?: string
  /** 文件访问档位（前端开关）: off=关闭 | workspace=仅工作区 | full=完全访问 */
  file_access?: 'off' | 'workspace' | 'full'
  /** 老师自定义工作区路径（空 = 默认 ~/ChemAI-Workspace） */
  workspace?: string
  /** ADR-0013 确认门三值决定：approve / reject(必带 feedback) / abandon。
   * ADR-0015 强绑定：gate_id 必带（决定与动作一一对应，防串门）。 */
  decision?: {
    action: 'approve' | 'reject' | 'abandon'
    feedback?: string
    draft_id?: string
    gate_id?: string
  }
}

/** 流式读取 SSE 响应，逐事件回调 */
export async function streamAgent(
  resp: Response,
  handlers: AgentHandlers,
): Promise<void> {
  const reader = resp.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let sawDone = false

  while (true) {
    const r = await reader.read()
    if (r.done) break
    buffer += decoder.decode(r.value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const payload = line.slice(6)
      if (payload === '[DONE]') {
        sawDone = true
        handlers.onDone?.()
        return
      }
      // Legacy think markers
      if (payload === '<think>' || payload === '</think>') continue
      let evt: AgentEvent
      try {
        evt = JSON.parse(payload)
      } catch {
        console.error('SSE event parse error:', payload)
        continue
      }
      if (evt.type === 'done') {
        sawDone = true
        handlers.onDone?.()
        return
      }
      handlers.onEvent(evt)
    }
  }
  if (sawDone) {
    handlers.onDone?.()
  } else {
    // 无收尾标记 = 流被掐断（服务重启/网络中断）——如实上报，由调用方重同步
    handlers.onAbnormalEnd?.()
  }
}

/** 发起一次流式对话请求（POST + SSE），返回 fetch 的 Response 以便调用方继续 streamAgent。
 * persona 默认 teacher（文件档位/工作区为教师端参数）；student/parent 端不携带文件参数。 */
export async function postStream(
  path: '/api/agent/chat/langgraph/stream' | '/api/agent/chat/langgraph/resume',
  params: StreamParams & { resume?: boolean },
): Promise<Response> {
  const persona = params.persona || 'teacher'
  const body: Record<string, unknown> = {
    persona,
    provider: params.provider || 'deepseek',
    conversation_id: params.conversationId,
    version: 'v2',
  }
  if (params.studentId) body.student_id = params.studentId
  if (persona === 'teacher') {
    body.file_access = params.file_access || 'workspace'
    body.workspace = params.workspace || ''
  }
  if (params.decision) {
    // ADR-0013：确认门决定走结构化协议；打回反馈随 decision.feedback 传输
    body.message = params.message || ''
    body.decision = params.decision
  } else if (params.resume) {
    body.message = params.message // approved / cancelled（旧协议兼容）
  } else {
    body.message = params.message
    if (params.history) body.history = params.history
  }
  const resp = await fetch(path, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getToken()}`,
    },
    body: JSON.stringify(body),
  })
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`
    try {
      const d = await resp.json()
      if (d?.detail) detail = typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail)
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  return resp
}

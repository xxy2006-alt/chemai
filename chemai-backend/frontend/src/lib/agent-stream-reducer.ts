/* agent-stream-reducer.ts — SSE 事件 → 消息状态的纯函数归约器
 * 从 ChatPage 抽出，便于回归测试（evals）：
 *  - 问题①回归：tool_result.result 为 JSON 字符串（v2 协议）必须解析为数据
 *  - 问题②回归：component 事件追加内联面板（不跳页）
 *  - 问题③回归：phase 状态进入气泡（由 MessageList 渲染）
 */

import type { AgentEvent, GateOpenEvent, RunPausedEvent } from './agent-sse'
import type { ChatItem } from '../components/chat/MessageList'
import type { OrbState } from 'thinking-orbs'

export interface StreamState {
  items: ChatItem[]
  aiId: string | null
  toolPending: Map<string, string>
  phase: string
  /** thinking-orbs 动画状态（2026-08）：thinking→breathing / 执行中→working / reply→composing */
  orb: OrbState | ''
  seq: number
}

export interface StreamCtx {
  newId: () => string
  onNavigate?: (path: string, params?: Record<string, unknown>) => void
}

const PHASE_LABELS: Record<string, string> = {
  thinking: '分析中…',
  executing: '执行中…',
  reply: '回复中…',
  planning: '生成计划中…',
}

/** ADR-0013 确认门：等待确认/修订中是 Plan Run 的合法驻留状态。
 * unknown：协议里的未知状态——渲染为灰色，绝不乐观地显示完成（issue #18 阶段 4）。 */
export type PlanStepStatus =
  | 'pending'
  | 'running'
  | 'awaiting_confirmation'
  | 'revising'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'unknown'

/** 确认门决定状态（审批卡的最终态） */
export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'abandoned' | 'cancelled'

const STEP_LABELS: Record<string, string> = {
  search_exam_bank: '搜索真题',
  generate_questions: 'AI 出题',
  diagnose_barrier: '障碍诊断',
  chemistry_tutor: '智能辅导',
  simulate_experiment: '模拟实验',
  weekly_report: '生成周报',
  import_exam_paper: '导入试卷',
  assign_adaptive_practice: '布置练习',
  balance_equation: '配平审核',
  web_search: '联网搜索',
}

export function createStreamState(): StreamState {
  return { items: [], aiId: null, toolPending: new Map(), phase: '', orb: '', seq: 0 }
}

/** 发送新消息时的种子状态：以当前完整消息列表（含旧对话）为基底，
 * 追加用户消息与空的 AI 消息。回归点：旧消息不得在首个 SSE 事件到达时丢失。 */
export function seedNewTurn(
  currentItems: ChatItem[],
  userText: string,
  newId: () => string,
): { state: StreamState; items: ChatItem[] } {
  const userItem: ChatItem = { id: newId(), kind: 'user', text: userText }
  const aiId = newId()
  const aiItem: ChatItem = { id: aiId, kind: 'ai', text: '', streaming: true }
  const items = [...currentItems, userItem, aiItem]
  return { state: { ...createStreamState(), items, aiId, orb: 'breathing' }, items }
}

/** 审批卡决定落位（ADR-0013：approve/reject/abandon 三值；cancelled 为旧协议兼容态）。
 * ChatPage 决定时必须同时同步 streamRef.state.items 与消息列表，
 * 否则后续 SSE 流的 onDone 会用旧 state.items 覆盖（历史回归点）。 */
export function updateApprovalStatus(
  items: ChatItem[],
  status: ApprovalStatus,
): ChatItem[] {
  return items.map((it) =>
    it.kind === 'approval' && it.approval.status === 'pending'
      ? { ...it, approval: { ...it.approval, status } }
      : it,
  )
}

/** 解析工具结果：v2 适配器把 result 作为 JSON 字符串发送；旧协议用 data 对象 */
export function parseToolResult(evt: {
  result?: unknown
  data?: unknown
}): unknown {
  if (evt.data !== undefined) return evt.data
  if (typeof evt.result === 'string') {
    try {
      return JSON.parse(evt.result)
    } catch {
      return { raw: evt.result }
    }
  }
  return evt.result
}

export function reduceAgentEvent(state: StreamState, evt: AgentEvent, ctx: StreamCtx): StreamState {
  const next: StreamState = {
    ...state,
    seq: state.seq + 1,
    toolPending: new Map(state.toolPending),
    items: [...state.items],
  }
  const id = ctx.newId

  switch (evt.type) {
    case 'phase': {
      next.phase = evt.phase === 'awaiting_approval' ? '等待确认…' : PHASE_LABELS[evt.phase] || evt.phase
      // thinking-orbs 状态映射：thinking→breathing / executing→working / reply→composing；
      // 等待审批时停动画（审批卡本身是交互 UI）
      if (evt.phase === 'thinking') next.orb = 'breathing'
      else if (evt.phase === 'executing' || evt.phase === 'planning') next.orb = 'working'
      else if (evt.phase === 'reply') next.orb = 'composing'
      else if (evt.phase === 'awaiting_approval') next.orb = ''
      if (evt.phase === 'awaiting_approval') {
        // ADR-0015 阶段 4：旧 phase 门事件已退役（gate_open 取代）。
        // 同 PR 切换后这里只兜底 v1 适配器的遗留流——不出确认按钮。
        next.phase = '等待确认…'
      }
      break
    }
    case 'gate_open': {
      /* ADR-0015 阶段 4：确认门事件（类型化）。按 gate_id 去重/替换——
       * 换绑时 action/recipient 一并更新，家长门不可能渲染成「发送给学生」
       * （旧实现只换 draft_id 不换 action，正是收件人错位的 UI 面）。 */
      const gate = evt as GateOpenEvent
      const existing = next.items.find(
        (it) =>
          it.kind === 'approval' &&
          it.approval.status === 'pending' &&
          it.approval.gate_id === gate.gate_id,
      )
      if (existing) {
        next.items = next.items.map((it) =>
          it.kind === 'approval' && it.id === existing.id
            ? {
                ...it,
                approval: {
                  ...it.approval,
                  text: gate.message || it.approval.text,
                  action: gate.action || it.approval.action,
                  recipient: gate.recipient || it.approval.recipient,
                  draft_id: gate.draft_id,
                  version: gate.version,
                },
              }
            : it,
        )
        break
      }
      // 不同 gate_id 的门 → 各自一张卡（双门并存，互不覆盖）
      const stale = next.items.find(
        (it) => it.kind === 'approval' && it.approval.status === 'pending',
      )
      if (stale && !gate.gate_id) break // 无 gate_id 的兜底事件不堆卡
      next.items.push({
        id: id(),
        kind: 'approval',
        approval: {
          text: gate.message || '请确认操作',
          status: 'pending',
          action: gate.action || '',
          recipient: gate.recipient,
          draft_id: gate.draft_id,
          version: gate.version,
          gate_id: gate.gate_id,
        },
      })
      break
    }
    case 'run_paused': {
      /* ADR-0016：系统挂起 ≠ 等待人工——明确「已暂停」状态，不出按钮 */
      const paused = evt as RunPausedEvent
      next.phase = '已暂停'
      next.orb = ''
      next.items.push({
        id: id(),
        kind: 'system',
        text: `⏸ ${paused.message || '运行已暂停；重新发送消息即可继续'}`,
      })
      break
    }
    case 'step': {
      next.phase = `第 ${evt.current || '?'} 步：${STEP_LABELS[evt.skill || ''] || evt.skill || ''}`
      next.orb = 'working'
      break
    }
    case 'tool_call': {
      if (String(evt.name).startsWith('route_to_')) break
      // 工具执行阶段后端 v2 不发 phase（只发 thinking/reply/awaiting_approval），
      // 状态行会一直停在「分析中…」。这里直接用工具名推进状态：
      // 「执行中：搜索真题」——工具执行通常是最长的一段，必须有可见状态。
      // 联网搜索/真题搜索用专门的 searching 动画（thinking-orbs 扫描子午线）+「搜索中…」
      if (evt.name === 'web_search' || evt.name === 'search_exam_bank') {
        next.phase = '搜索中…'
        next.orb = 'searching'
      } else {
        next.phase = `执行中：${STEP_LABELS[evt.name] || evt.name}`
        next.orb = 'working'
      }
      // DSH 式（2026-08）：工具调用前的 AI 文本是思考过程 → 折叠为 Think 行；
      // 空占位气泡（无文本直开工具）直接移除，白块不复现。
      // ⚠ 折叠/移除都必须清空 aiId：否则后续 text 事件会尝试追加到已变成
      // think 的旧气泡（kind 不匹配）→ 文本静默丢失（2026-08 修复：
      // 多步骤任务最终总结回复消失——思考→工具→再输出文本的整段被吞）
      const last = next.items[next.items.length - 1]
      if (last && last.kind === 'ai') {
        if (last.text.trim()) {
          next.items[next.items.length - 1] = { ...last, kind: 'think', streaming: false }
          if (next.aiId === last.id) next.aiId = null
        } else {
          next.items.pop()
          if (next.aiId === last.id) next.aiId = null
        }
      }
      const itemId = id()
      next.toolPending.set(evt.name, itemId)
      next.items.push({ id: itemId, kind: 'tool', card: { tool: evt.name, status: 'running' } })
      break
    }
    case 'tool_result': {
      const itemId = next.toolPending.get(evt.name)
      if (itemId) {
        next.toolPending.delete(evt.name)
        const parsedData = parseToolResult(evt)
        // gate_open_blocked = 被已打开的确认门拦下 → 暂停等待确认，不是失败
        const paused = evt.success === false
          && parsedData != null
          && typeof parsedData === 'object'
          && (parsedData as Record<string, unknown>).gate_open_blocked === true
        next.items = next.items.map((it) =>
          it.kind === 'tool' && it.id === itemId
            ? {
                ...it,
                card: {
                  tool: evt.name,
                  status: paused ? 'paused' : evt.success === false ? 'error' : 'done',
                  data: parsedData,
                },
              }
            : it,
        )
      } else if (String(evt.name) !== 'request_approval') {
        // 2026-08 确定性审批重放：request_approval 获批后自动重跑被拦截的
        // 工具，其合成 tool_result 无挂起项 → 补一张结果卡（批准后不断链）
        next.items.push({
          id: id(),
          kind: 'tool',
          card: {
            tool: evt.name,
            status: evt.success === false ? 'error' : 'done',
            data: parseToolResult(evt),
          },
        })
      }
      break
    }
    case 'tool_error': {
      const itemId = next.toolPending.get(evt.name)
      if (itemId) {
        next.toolPending.delete(evt.name)
        next.items = next.items.map((it) =>
          it.kind === 'tool' && it.id === itemId
            ? { ...it, card: { tool: evt.name, status: 'error' as const, error: evt.message } }
            : it,
        )
      }
      break
    }
    case 'exam_images': {
      /* 题目附图事件（search_exam_bank 返回的 page_image 附图）：
       * 紧跟 tool_result 之后到达，挂到最近的搜索工具卡片上；
       * 正文已内联的图由 SearchResults 的 filterExamImages 去重。 */
      for (let i = next.items.length - 1; i >= 0; i--) {
        const it = next.items[i]
        if (it.kind === 'tool' && it.card.tool === 'search_exam_bank' && it.card.status === 'done') {
          const cur = it.card.data && typeof it.card.data === 'object' ? it.card.data : {}
          const list = Array.isArray((cur as { images?: unknown[] }).images)
            ? (cur as { images: unknown[] }).images
            : []
          next.items[i] = {
            ...it,
            card: {
              ...it.card,
              data: {
                ...cur,
                images: [
                  ...list,
                  { q_index: evt.q_index, title: evt.title, urls: evt.urls },
                ],
              },
            },
          }
          break
        }
      }
      break
    }
    case 'text': {
      if (!next.aiId) {
        const aid = id()
        next.aiId = aid
        next.items.push({ id: aid, kind: 'ai', text: '', streaming: true })
      }
      const aid = next.aiId
      next.items = next.items.map((it) =>
        it.kind === 'ai' && it.id === aid ? { ...it, text: it.text + evt.content } : it,
      )
      break
    }
    case 'component': {
      /* 内联面板：不跳页（与旧版一致），面板由 InlinePanel 组件渲染。
         S2 去重：同一 component 再次到达时替换原面板（LLM 可能对同一诊断/
         计划多次调用工具，避免面板重复堆叠），新 id 触发重渲染。 */
      const existingIdx = next.items.findIndex(
        (it) => it.kind === 'panel' && it.component === evt.component,
      )
      if (existingIdx >= 0) {
        next.items = next.items.map((it, i) =>
          i === existingIdx
            ? { ...it, id: id(), params: evt.params || {} }
            : it,
        )
      } else {
        next.items.push({ id: id(), kind: 'panel', component: evt.component, params: evt.params || {} })
      }
      break
    }
    case 'plan_summary': {
      /* 任务计划卡（Spec 06）：plan_task 的步骤计划，plan_progress 逐步更新状态。
       * ADR-0013：同 goal 的 plan_summary 原地替换原卡（同一 run 重规划不再堆叠新卡），
       * 不同 goal（新 run）才追加。 */
      const goal = String(evt.goal || '')
      const existingIdx = next.items.findIndex(
        (it) => it.kind === 'plan' && it.plan.goal === goal,
      )
      const planItem: ChatItem = {
        id: existingIdx >= 0 ? next.items[existingIdx].id : id(),
        kind: 'plan',
        plan: {
          goal,
          total_steps: Number(evt.total_steps || 0),
          steps: (Array.isArray(evt.steps) ? evt.steps : []).map((s: unknown) => {
            const st = (s || {}) as Record<string, unknown>
            return {
              step: Number(st.step || 0),
              skill: String(st.skill || ''),
              description: String(st.description || ''),
              status: 'pending' as PlanStepStatus,
            }
          }),
        },
      }
      if (existingIdx >= 0) {
        next.items = next.items.map((it, i) => (i === existingIdx ? planItem : it))
      } else {
        next.items.push(planItem)
      }
      break
    }
    case 'plan_progress': {
      const current = Number(evt.current_step || 0)
      // ADR-0013：步状态机扩展——门循环（等待确认/修订中）与放弃（取消）是合法驻留态
      const allowed: PlanStepStatus[] = [
        'running', 'awaiting_confirmation', 'revising', 'completed', 'failed', 'cancelled',
      ]
      const status = (allowed as string[]).includes(String(evt.status))
        ? (evt.status as PlanStepStatus)
        : 'unknown' // 未知状态渲染灰色，绝不乐观打勾（issue #18 阶段 4）
      next.items = next.items.map((it) =>
        it.kind === 'plan'
          ? {
              ...it,
              plan: {
                ...it.plan,
                steps: it.plan.steps.map((s) => (s.step === current ? { ...s, status } : s)),
              },
            }
          : it,
      )
      break
    }
    case 'navigate': {
      /* 旧版行为（agent.js）：navigate 事件携带 params（如 {focus: 学号, action: 'plan'}），
       * 目标页消费后自动执行（学生页 → 打开学生抽屉 + 自动生成学习方案）。 */
      const path = evt.page === 'exam-workbench' ? '/exam' : `/${evt.page}`
      ctx.onNavigate?.(path, evt.params || {})
      break
    }
    case 'error': {
      next.items.push({ id: id(), kind: 'system', text: `⚠ ${evt.message || '未知错误'}` })
      break
    }
    default:
      break
  }
  return next
}

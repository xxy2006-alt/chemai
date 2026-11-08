/* gate-loop.test.ts — ADR-0013 确认门三值决定的前端状态回归
 * 覆盖：门卡携带 draft_id（三值钮可用）/ 修订后同门新版本原地替换 /
 * plan 步状态机扩展（等待确认、修订中、已放弃）*/
import { describe, expect, it } from 'vitest'
import { createStreamState, reduceAgentEvent, updateApprovalStatus } from '../src/lib/agent-stream-reducer'
import type { StreamState } from '../src/lib/agent-stream-reducer'
import type { GateOpenEvent } from '../src/lib/agent-sse'

let n = 0
const newId = () => `id${n++}`
const ctx = { newId }

const gateOpen = (overrides: Record<string, unknown> = {}): GateOpenEvent => ({
  type: 'gate_open' as const,
  gate_id: 'g-draft-d1',
  message: '学习计划尚未经老师确认，请先确认再发送',
  action: 'send_student',
  recipient: 'student',
  draft_id: 'd1',
  version: 1,
  ...overrides,
})

const planSummary = () => ({
  type: 'plan_summary' as const,
  goal: '给张三做学习计划并发送',
  total_steps: 3,
  steps: [
    { step: 1, skill: 'generate_learning_plan', description: '生成计划' },
    { step: 2, skill: 'send_learning_plan', description: '发送计划' },
    { step: 3, skill: 'weekly_report', description: '发周报' },
  ],
})

const planProgress = (step: number, status: string) => ({
  type: 'plan_progress' as const,
  current_step: step,
  status,
})

describe('ADR-0013 三值确认门', () => {
  it('门卡携带 draft_id 与版本（三值钮的可用依据）', () => {
    let s: StreamState = createStreamState()
    s = reduceAgentEvent(s, gateOpen({ draft_id: 'd1', version: 1 }), ctx)
    const card = s.items.find((it) => it.kind === 'approval')
    expect(card && card.kind === 'approval').toBe(true)
    if (card?.kind === 'approval') {
      expect(card.approval.draft_id).toBe('d1')
      expect(card.approval.version).toBe(1)
      expect(card.approval.action).toBe('send_student')
    }
  })

  it('修订后再确认：同门新版本原地替换 pending 卡，不堆叠', () => {
    let s: StreamState = createStreamState()
    s = reduceAgentEvent(s, gateOpen({ draft_id: 'd1', version: 1 }), ctx)
    s = reduceAgentEvent(s, gateOpen({ draft_id: 'd1', version: 2, message: '修订版（第 2 版）已生成' }), ctx)
    const cards = s.items.filter((it) => it.kind === 'approval')
    expect(cards).toHaveLength(1)
    const c = cards[0]
    if (c.kind === 'approval') {
      expect(c.approval.version).toBe(2)
      expect(c.approval.text).toContain('第 2 版')
    }
  })

  it('plan 步状态机：等待确认 → 修订中 → 再等待 → 完成', () => {
    let s: StreamState = createStreamState()
    s = reduceAgentEvent(s, planSummary(), ctx)
    s = reduceAgentEvent(s, planProgress(1, 'completed'), ctx)
    s = reduceAgentEvent(s, planProgress(2, 'awaiting_confirmation'), ctx)
    let plan = s.items.find((it) => it.kind === 'plan')
    expect(plan?.kind === 'plan' && plan.plan.steps[1].status).toBe('awaiting_confirmation')
    s = reduceAgentEvent(s, planProgress(2, 'revising'), ctx)
    plan = s.items.find((it) => it.kind === 'plan')
    expect(plan?.kind === 'plan' && plan.plan.steps[1].status).toBe('revising')
    s = reduceAgentEvent(s, planProgress(2, 'awaiting_confirmation'), ctx)
    s = reduceAgentEvent(s, planProgress(2, 'completed'), ctx)
    plan = s.items.find((it) => it.kind === 'plan')
    expect(plan?.kind === 'plan' && plan.plan.steps[1].status).toBe('completed')
  })

  it('放弃：步标 cancelled，不影响其他步骤状态', () => {
    let s: StreamState = createStreamState()
    s = reduceAgentEvent(s, planSummary(), ctx)
    s = reduceAgentEvent(s, planProgress(1, 'completed'), ctx)
    s = reduceAgentEvent(s, planProgress(2, 'cancelled'), ctx)
    const plan = s.items.find((it) => it.kind === 'plan')
    if (plan?.kind === 'plan') {
      expect(plan.plan.steps[1].status).toBe('cancelled')
      expect(plan.plan.steps[2].status).toBe('pending')
    }
  })

  it('决定落位：updateApprovalStatus 支持 approve/reject/abandoned', () => {
    let s: StreamState = createStreamState()
    s = reduceAgentEvent(s, gateOpen({ draft_id: 'd1' }), ctx)
    expect(
      updateApprovalStatus(s.items, 'rejected').find((it) => it.kind === 'approval')?.kind === 'approval'
        ? updateApprovalStatus(s.items, 'rejected').map((it) => (it.kind === 'approval' ? it.approval.status : ''))[0]
        : '',
    ).toBe('rejected')
    expect(
      updateApprovalStatus(s.items, 'abandoned').map((it) => (it.kind === 'approval' ? it.approval.status : ''))[0],
    ).toBe('abandoned')
    // pending 卡不得被无关状态污染
    expect(
      updateApprovalStatus(s.items, 'approved').map((it) => (it.kind === 'approval' ? it.approval.status : ''))[0],
    ).toBe('approved')
  })
})

describe('ADR-0013 plan 卡 run 替换', () => {
  it('同 goal 的 plan_summary 原地替换，不堆叠新卡', () => {
    let s: StreamState = createStreamState()
    s = reduceAgentEvent(s, planSummary(), ctx)
    s = reduceAgentEvent(s, planSummary(), ctx)
    expect(s.items.filter((it) => it.kind === 'plan')).toHaveLength(1)
  })

  it('不同 goal（新 run）追加新卡', () => {
    let s: StreamState = createStreamState()
    s = reduceAgentEvent(s, planSummary(), ctx)
    s = reduceAgentEvent(s, { ...planSummary(), goal: '另一个任务' }, ctx)
    expect(s.items.filter((it) => it.kind === 'plan')).toHaveLength(2)
  })
})

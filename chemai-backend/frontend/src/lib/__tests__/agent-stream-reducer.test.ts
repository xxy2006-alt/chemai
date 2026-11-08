/* 阶段 4 — reducer 投影回归（issue #18；ADR-0015 事件契约类型化）。
 * 门卡按 gate_id 去重/替换：换绑时 action/recipient 一并更新——
 * 家长门不可能再渲染成「发送给学生」（收件人错位的 UI 面就此消灭）。 */
import { describe, expect, it } from 'vitest'
import {
  createStreamState,
  reduceAgentEvent,
  type StreamCtx,
} from '../agent-stream-reducer'

const ctx: StreamCtx = { newId: (() => {
  let n = 0
  return () => `id-${++n}`
})() }

describe('gate_open（阶段 4 类型化门事件）', () => {
  it('创建带 gate_id/action/recipient 的确认卡', () => {
    const state = reduceAgentEvent(createStreamState(), { type: 'gate_open', gate_id: 'g-draft-d1', action: 'send_student', recipient: 'student', draft_id: 'd1', version: 1, message: '计划等待确认' }, ctx)
    const cards2 = state.items.filter((it) => it.kind === 'approval')
    expect(cards2).toHaveLength(1)
    const card = cards2[0] as Extract<typeof cards2[number], { kind: 'approval' }>
    expect(card.approval).toMatchObject({
      status: 'pending',
      action: 'send_student',
      recipient: 'student',
      draft_id: 'd1',
      gate_id: 'g-draft-d1',
    })
  })

  it('同 gate_id 新版本 → 原地替换且 action 更新（打回修订后再开门）', () => {
    let state = createStreamState()
    state = reduceAgentEvent(state, { type: 'gate_open', gate_id: 'g-draft-d1', action: 'send_student', recipient: 'student', draft_id: 'd1', version: 1, message: 'v1' }, ctx)
    state = reduceAgentEvent(state, { type: 'gate_open', gate_id: 'g-draft-d1', action: 'send_student', recipient: 'student', draft_id: 'd1', version: 2, message: '修订版 v2' }, ctx)
    const cards = state.items.filter((it) => it.kind === 'approval')
    expect(cards).toHaveLength(1)
    const card = cards[0] as Extract<typeof cards[number], { kind: 'approval' }>
    expect(card.approval.version).toBe(2)
    expect(card.approval.text).toBe('修订版 v2')
  })

  it('不同 gate_id 的门 → 各自一张卡，后门不覆盖前门（门覆盖回归）', () => {
    let state = createStreamState()
    state = reduceAgentEvent(state, { type: 'gate_open', gate_id: 'g-draft-d1', action: 'send_student', recipient: 'student', draft_id: 'd1', version: 1, message: '学生计划' }, ctx)
    state = reduceAgentEvent(state, { type: 'gate_open', gate_id: 'g-draft-d2', action: 'send_parent', recipient: 'parent', draft_id: 'd2', version: 1, message: '家长报告' }, ctx)
    const cards = state.items.filter((it) => it.kind === 'approval')
    expect(cards).toHaveLength(2)
    const actions = cards.map((c) => (c as Extract<typeof c, { kind: 'approval' }>).approval.action)
    expect(actions).toContain('send_student')
    expect(actions).toContain('send_parent')
  })
})

describe('run_paused（Paused Run 与等待人工分离）', () => {
  it('系统暂停 → 状态行 + 系统提示，不出确认卡', () => {
    let state = createStreamState()
    state = reduceAgentEvent(state, { type: 'run_paused', reason: 'interrupted', message: '上一回合被中断' }, ctx)
    expect(state.phase).toBe('已暂停')
    expect(state.orb).toBe('')
    const hasApproval = state.items.some((it) => it.kind === 'approval')
    expect(hasApproval).toBe(false)
    const hasSystem = state.items.some((it) => it.kind === 'system')
    expect(hasSystem).toBe(true)
  })
})

describe('plan_progress 未知状态', () => {
  it('未知 status 渲染 unknown，绝不默认 completed', () => {
    let state = createStreamState()
    state = reduceAgentEvent(state, {
      type: 'plan_summary',
      goal: 'g',
      total_steps: 1,
      steps: [{ step: 1, skill: 'send_learning_plan', description: '发送', status: 'pending' }],
    } as never, ctx)
    state = reduceAgentEvent(state, { type: 'plan_progress', current_step: 1, status: 'superseded' } as never, ctx)
    const plan = state.items.find((it) => it.kind === 'plan') as Extract<typeof state.items[number], { kind: 'plan' }>
    expect(plan.plan.steps[0].status).toBe('unknown')
  })
})

describe('phase:awaiting_approval（旧协议兜底）', () => {
  it('不再创建确认卡', () => {
    let state = createStreamState()
    state = reduceAgentEvent(state, { type: 'phase', phase: 'awaiting_approval', message: '请确认' }, ctx)
    expect(state.items.some((it) => it.kind === 'approval')).toBe(false)
  })
})

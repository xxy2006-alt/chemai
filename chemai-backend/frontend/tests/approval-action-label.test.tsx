/* approval-action-label.test.tsx — 发送确认门动态按钮文案（2026-08） */
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ApprovalCard } from '../src/components/chat/ApprovalCard'
import { reduceAgentEvent, createStreamState } from '../src/lib/agent-stream-reducer'

const ctx = { newId: () => `id-${Math.random()}`, onNavigate: vi.fn() }

describe('审批卡动态按钮文案', () => {
  it('send_student → 按钮显示「发送给学生」', () => {
    render(
      <ApprovalCard
        approval={{ text: '即将把内容发送给学生 李世睿', status: 'pending', action: 'send_student' }}
        onResolve={() => {}}
      />,
    )
    expect(screen.getByRole('button', { name: '发送给学生' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '批准' })).toBeNull()
  })

  it('send_parent → 按钮显示「同步给家长」', () => {
    render(
      <ApprovalCard
        approval={{ text: '即将把学习报告同步给家长', status: 'pending', action: 'send_parent' }}
        onResolve={() => {}}
      />,
    )
    expect(screen.getByRole('button', { name: '同步给家长' })).toBeInTheDocument()
  })

  it('无 action → 默认「批准」；布尔门只有批准/放弃，无打回（ADR-0013）', () => {
    render(
      <ApprovalCard approval={{ text: '请确认操作', status: 'pending' }} onResolve={() => {}} />,
    )
    expect(screen.getByRole('button', { name: '批准' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '放弃' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '打回修改' })).toBeNull()
  })

  it('草稿门（带 draft_id）→ 批准/打回修改/放弃三钮（ADR-0013）', () => {
    render(
      <ApprovalCard
        approval={{ text: '计划等待确认', status: 'pending', action: 'send_student', draft_id: 'd1', version: 1 }}
        onResolve={() => {}}
      />,
    )
    expect(screen.getByRole('button', { name: '发送给学生' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '打回修改' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '放弃' })).toBeInTheDocument()
  })

  it('已打回 / 已放弃终态文案', () => {
    const { rerender } = render(
      <ApprovalCard approval={{ text: 'x', status: 'rejected', draft_id: 'd1' }} onResolve={() => {}} />,
    )
    expect(screen.getByText('已打回，按意见修订中')).toBeInTheDocument()
    rerender(
      <ApprovalCard approval={{ text: 'x', status: 'abandoned', draft_id: 'd1' }} onResolve={() => {}} />,
    )
    expect(screen.getByText('已放弃')).toBeInTheDocument()
  })
})

describe('reducer 审批卡 action 透传', () => {
  it('gate_open 事件的 action/recipient 存入审批条目', () => {
    let s = createStreamState()
    s = reduceAgentEvent(
      s,
      { type: 'gate_open', gate_id: 'g-draft-d1', message: '即将发送', action: 'send_student', recipient: 'student', draft_id: 'd1' } as never,
      ctx,
    )
    const card = s.items.find((it) => it.kind === 'approval')
    expect(card).toBeDefined()
    if (card?.kind === 'approval') {
      expect(card.approval.action).toBe('send_student')
      expect(card.approval.recipient).toBe('student')
    }
  })
})

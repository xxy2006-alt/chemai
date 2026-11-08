import { useState } from 'react'
import { ShieldAlert, ShieldCheck, ShieldX, Undo2, Ban } from 'lucide-react'
import { Button } from '../ui'
import type { ApprovalStatus } from '../../lib/agent-stream-reducer'

export interface ApprovalData {
  text: string
  status: ApprovalStatus
  /** 2026-08 发送确认门：动态批准按钮文案标记（send_student/send_parent） */
  action?: string
  /** ADR-0015 阶段 4：收件人语义（student/parent/system）——与 action 一起渲染按钮，
   * 按钮文案永远来自本门自己的数据（收件人不可能串门） */
  recipient?: 'student' | 'parent' | 'system'
  /** ADR-0013 三值门：门挂在草稿实体上。draft_id 缺失 = 布尔门，打回不可用 */
  draft_id?: string
  version?: number
  /** ADR-0015 强绑定键：决定只作用于这个门（一决定一动作） */
  gate_id?: string
}

export type GateDecision = 'approve' | 'reject' | 'abandon'

/** 审批确认卡：Agent 请求执行破坏性操作前需要教师确认。
 * ADR-0013 三值门：批准（发送并继续）/ 打回（带反馈，修订后再确认）/ 放弃（跳过继续）。 */
export function ApprovalCard({
  approval,
  onResolve,
  disabled,
}: {
  approval: ApprovalData
  onResolve: (decision: GateDecision, feedback?: string) => void
  /** 流式进行中禁用按钮（会话锁 409 的前端防线，ADR-0016 §5） */
  disabled?: boolean
}) {
  const [feedback, setFeedback] = useState('')
  const [rejecting, setRejecting] = useState(false)
  const canReject = Boolean(approval.draft_id)
  const approveLabel =
    approval.action === 'send_student' || approval.recipient === 'student'
      ? '发送给学生'
      : approval.action === 'send_parent' || approval.recipient === 'parent'
        ? '同步给家长'
        : '批准'

  if (approval.status === 'approved') {
    return (
      <div className="self-start flex items-center gap-2 bg-success-soft text-success rounded-[var(--radius-md)] px-3.5 py-2.5 text-[13px]">
        <ShieldCheck size={16} />
        已批准执行
      </div>
    )
  }
  if (approval.status === 'rejected') {
    return (
      <div className="self-start flex items-center gap-2 bg-amber-50 text-amber-700 rounded-[var(--radius-md)] px-3.5 py-2.5 text-[13px] border border-amber-200">
        <Undo2 size={16} />
        已打回，按意见修订中
      </div>
    )
  }
  if (approval.status === 'abandoned' || approval.status === 'cancelled') {
    return (
      <div className="self-start flex items-center gap-2 bg-surface-muted text-ink-secondary rounded-[var(--radius-md)] px-3.5 py-2.5 text-[13px]">
        <ShieldX size={16} />
        已放弃
      </div>
    )
  }
  return (
    <div className="shrink-0 self-start bg-warning-soft border border-warning/25 rounded-[var(--radius-md)] px-4 py-3 max-w-[92%] animate-fade-in-up">
      <div className="flex items-center gap-2 text-warning text-[13px] font-medium">
        <ShieldAlert size={16} />
        需要确认{approval.version ? ` · 第 ${approval.version} 版` : ''}
      </div>
      <p className="mt-1.5 text-[13px] text-ink-secondary m-0">{approval.text}</p>
      {rejecting && (
        <div className="mt-2.5">
          <textarea
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="写明要修改的地方，如：第二周改成盐类水解专题"
            rows={2}
            className="w-full text-[13px] px-2.5 py-2 rounded-[var(--radius-sm)] border border-border bg-surface focus:outline-none focus:border-teal resize-y"
            autoFocus
          />
        </div>
      )}
      <div className="flex gap-2 mt-3">
        <Button
          size="sm"
          variant="primary"
          disabled={disabled}
          onClick={() => onResolve('approve')}
        >
          {approveLabel}
        </Button>
        {canReject && !rejecting && (
          <Button size="sm" variant="secondary" disabled={disabled} onClick={() => setRejecting(true)}>
            打回修改
          </Button>
        )}
        {rejecting && (
          <Button
            size="sm"
            variant="secondary"
            disabled={!feedback.trim() || disabled}
            onClick={() => onResolve('reject', feedback.trim())}
          >
            提交修改意见
          </Button>
        )}
        <Button size="sm" variant="ghost" disabled={disabled} onClick={() => onResolve('abandon')}>
          <Ban size={13} className="mr-1" />
          放弃
        </Button>
      </div>
      {!canReject && (
        <p className="mt-2 text-[11px] text-ink-muted m-0">该操作不支持修改，只能批准或放弃</p>
      )}
    </div>
  )
}

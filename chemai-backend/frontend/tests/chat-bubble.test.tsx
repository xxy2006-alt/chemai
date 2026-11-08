/* chat-bubble.test.tsx — AI 气泡回归测试（evals）
 * 问题③回归：思考/分析状态必须显示在 AI 气泡内（原位置），
 * 且输出文本后气泡展示内容。 */
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AiBubble } from '../src/components/chat/MessageList'

describe('问题③回归：思考状态在气泡内（原位置）', () => {
  it('流式中、尚未输出文本 → 气泡内显示阶段状态与 live-timer 计时器', () => {
    render(<AiBubble text="" streaming phase="执行中…" elapsed={5} />)
    expect(screen.getByText(/执行中/)).toBeInTheDocument()
    // 旧版 live-timer：1 位小数秒 + ticking 跳动类
    const timer = screen.getByText('5.0s')
    expect(timer).toBeInTheDocument()
    expect(timer.className).toContain('live-timer ticking')
  })

  it('tool 步骤状态同样进入气泡', () => {
    render(<AiBubble text="" streaming phase="第 2 步：搜索真题" />)
    expect(screen.getByText(/第 2 步：搜索真题/)).toBeInTheDocument()
  })

  it('输出文本后气泡渲染内容，且执行状态行仍显示（DSH 式，2026-08）', () => {
    render(<AiBubble text="水是 \\ce{H2O}" streaming phase="回复中…" />)
    // 文本经 renderChemMD 渲染为 HTML
    expect(document.querySelector('.chem-md')).not.toBeNull()
    // 执行中状态行持续可见（不再随文本到达消失）
    expect(screen.getByText(/回复中/)).toBeInTheDocument()
  })

  it('等待确认 → 气泡内显示等待状态', () => {
    render(<AiBubble text="" streaming phase="等待确认…" />)
    expect(screen.getByText(/等待确认/)).toBeInTheDocument()
  })

  it('流式结束无文本 → 不显示思考状态', () => {
    render(<AiBubble text="" streaming={false} phase="" />)
    expect(screen.queryByText(/分析中|执行中|回复中/)).toBeNull()
  })
})

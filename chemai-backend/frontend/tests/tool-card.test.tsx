/* tool-card.test.tsx — 工具卡片回归测试（evals）
 * 问题①回归：tool_result 数据到达后卡片自动展开显示结果（旧版即时可见），
 * 执行中不展开。 */
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ToolCard } from '../src/components/chat/ToolCard'

describe('工具调用卡片', () => {
  it('执行中：不展开、无结果内容', () => {
    render(<ToolCard card={{ tool: 'show_exam_workbench', status: 'running' }} />)
    expect(screen.getByText('打开出题工作台')).toBeInTheDocument()
    expect(screen.getByText('执行中')).toBeInTheDocument()
    expect(document.querySelector('.border-t')).toBeNull()
  })

  it('完成后：自动展开并渲染结果内容（问题①回归）', () => {
    render(
      <ToolCard
        card={{
          tool: 'show_exam_workbench',
          status: 'done',
          data: { message: '已打开出题工作台，预选知识点：氧化还原反应' },
        }}
      />
    )
    expect(screen.getByText('打开出题工作台')).toBeInTheDocument()
    expect(screen.getByText('完成')).toBeInTheDocument()
    // 结果区自动可见
    expect(screen.getByText(/已打开出题工作台/)).toBeInTheDocument()
  })

  it('失败：显示错误状态', () => {
    render(<ToolCard card={{ tool: 'web_search', status: 'error', error: '网络不可用' }} />)
    expect(screen.getByText('失败')).toBeInTheDocument()
    expect(screen.getByText('网络不可用')).toBeInTheDocument()
  })

  it('未知工具名回退显示原名称', () => {
    render(<ToolCard card={{ tool: 'some_future_tool', status: 'running' }} />)
    expect(screen.getByText('some_future_tool')).toBeInTheDocument()
  })
})

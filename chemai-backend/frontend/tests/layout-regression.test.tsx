/* layout-regression.test.tsx — 消息项布局塌陷回归（2026-08 用户反复报告：
 * 对话超过视口高度后所有消息/卡片/面板被 flex 压成一条横线）。
 * jsdom 无法量高度，这里结构性地钉住：所有消息项根节点必须带 shrink-0。 */
import { describe, expect, it, beforeAll } from 'vitest'
import { render } from '@testing-library/react'
import { MessageList } from '../src/components/chat/MessageList'
import { ToolCard } from '../src/components/chat/ToolCard'
import { ApprovalCard } from '../src/components/chat/ApprovalCard'
import { InlinePanel } from '../src/components/chat/InlinePanels'
import { ToastProvider } from '../src/components/ui'

beforeAll(() => {
  // jsdom 无 scrollIntoView（MessageList 自动滚动用）
  Element.prototype.scrollIntoView = () => {}
})

function firstEl(container: HTMLElement): HTMLElement | null {
  return container.firstElementChild as HTMLElement | null
}

describe('消息项布局（shrink-0 防塌陷）', () => {
  it('MessageList 各类消息项根节点均带 shrink-0', () => {
    const { container } = render(
      <MessageList
        items={[
          { id: 'u1', kind: 'user', text: '你好' },
          { id: 'a1', kind: 'ai', text: '回复' },
          { id: 't1', kind: 'think', text: '思考中' },
          { id: 'c1', kind: 'tool', card: { tool: 'read', status: 'done', data: { content: 'x' } } },
          { id: 'ap1', kind: 'approval', approval: { text: '确认', status: 'pending' } },
          { id: 'p1', kind: 'plan', plan: { goal: '任务', total_steps: 1, steps: [{ step: 1, skill: 'x', description: 'd', status: 'pending' }] } },
          { id: 's1', kind: 'system', text: '提示' },
        ]}
        onApproval={() => {}}
      />,
    )
    // 消息容器是第一个元素；其直接子元素为各类消息项根节点
    const list = container.firstElementChild as HTMLElement
    expect(list).toBeTruthy()
    const items = [...list.children].filter(
      (el) => el.tagName === 'DIV' && (el as HTMLElement).className !== '', // 跳过滚动锚点
    )
    expect(items.length).toBeGreaterThanOrEqual(5)
    for (const el of items) {
      expect(el.className, `消息项缺 shrink-0: ${el.className}`).toContain('shrink-0')
    }
  })

  it('ToolCard / ApprovalCard / InlinePanel 根节点带 shrink-0', () => {
    const t = render(<ToolCard card={{ tool: 'read', status: 'done', data: { content: 'x' } }} />)
    expect(firstEl(t.container)?.className).toContain('shrink-0')
    const a = render(<ApprovalCard approval={{ text: '确认', status: 'pending' }} onResolve={() => {}} />)
    expect(firstEl(a.container)?.className).toContain('shrink-0')
    const p = render(
      <ToastProvider>
        <InlinePanel panelId="p1" component="student-list" params={{}} />
      </ToastProvider>,
    )
    expect(p.container.querySelector('[data-panel]')?.className).toContain('shrink-0')
  })
})

describe('计划卡执行状态行（DSH 式，2026-08）', () => {
  it('执行中的步骤显示「正在执行第 N 步」状态行与 live 计时', () => {
    const { container } = render(
      <MessageList
        items={[
          {
            id: 'p1',
            kind: 'plan',
            plan: {
              goal: '出5道化学题并保存到题库',
              total_steps: 2,
              steps: [
                { step: 1, skill: 'generate_questions', description: '生成5道化学题', status: 'running' },
                { step: 2, skill: 'save_to_bank', description: '保存到题库', status: 'pending' },
              ],
            },
          },
        ]}
        phase="生成计划中…"
        elapsed={12.3}
        onApproval={() => {}}
      />,
    )
    const text = container.textContent || ''
    expect(text).toContain('正在执行第 1 步：生成5道化学题')
    expect(text).toContain('12.3s')
    const timer = container.querySelector('.live-timer')
    expect(timer).toBeTruthy()
    expect(timer?.className).toContain('ticking')
  })

  it('无执行中步骤时不渲染状态行', () => {
    const { container } = render(
      <MessageList
        items={[
          {
            id: 'p2',
            kind: 'plan',
            plan: {
              goal: '任务',
              total_steps: 1,
              steps: [{ step: 1, skill: 'x', description: 'd', status: 'completed' }],
            },
          },
        ]}
        onApproval={() => {}}
      />,
    )
    expect(container.textContent || '').not.toContain('正在执行')
  })
})

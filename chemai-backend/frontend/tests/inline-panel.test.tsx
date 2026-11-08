/* inline-panel.test.tsx — 内联面板回归测试（evals）
 * 变种题功能：内联出题面板必须包含「选蓝本」入口（旧版功能恢复）
 * 题型选择：Agent 只预填单选时，面板仍必须展示全部 6 种题型 chips（用户反馈） */
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { InlinePanel } from '../src/components/chat/InlinePanels'
import { ToastProvider } from '../src/components/ui'

describe('内联出题面板（变种题功能恢复）', () => {
  it('渲染出题工作台面板：含 选蓝本 / 生成题目 / 保存目标 控件', async () => {
    // mock api（面板挂载时会拉知识点与题库）
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve({ ok: true, json: () => Promise.resolve({ knowledge_points: [], data: { exam_sets: [] } }) }),
      ),
    )
    render(
      <ToastProvider>
        <InlinePanel panelId="p1" component="exam-workbench" params={{ knowledge_points: ['氧化还原反应'] }} />
      </ToastProvider>,
    )
    expect(screen.getByText('出题工作台')).toBeInTheDocument()
    expect(screen.getByText('选蓝本')).toBeInTheDocument()
    expect(screen.getByText('生成题目')).toBeInTheDocument()
    // 知识点异步加载：Agent 预填但接口缺失的知识点应补为已选
    expect(await screen.findByText('氧化还原反应')).toBeInTheDocument()
    vi.unstubAllGlobals()
  })

  it('data-panel 属性存在（消息列表滚动定位用）', () => {
    const { container } = render(
      <ToastProvider>
        <InlinePanel panelId="p9" component="student-list" params={{}} />
      </ToastProvider>,
    )
    expect(container.querySelector('[data-panel="p9"]')).not.toBeNull()
  })
})

describe('诊断内联面板视图判定（2026-08「0% 掌握度」修复）', () => {
  it('单人诊断（student_name + barrier_distribution）→ 学生视图，无班级统计占位', () => {
    render(
      <ToastProvider>
        <InlinePanel
          panelId="p2"
          component="diagnosis"
          params={{
            data: {
              student_name: '张浩宇',
              barrier_distribution: { concept: 0.15, reading: 0.25, expression: 0.6 },
            },
          }}
        />
      </ToastProvider>,
    )
    expect(screen.getByText(/学生诊断 · 张浩宇/)).toBeInTheDocument()
    expect(screen.getByText('60%')).toBeInTheDocument()
    // 学生视图不渲染班级统计（掌握度/诊断学生）
    expect(screen.queryByText('掌握度')).toBeNull()
    expect(screen.queryByText('诊断学生')).toBeNull()
  })

  it('班级诊断（无 student_name + class_barrier_distribution）→ 班级视图', () => {
    render(
      <ToastProvider>
        <InlinePanel
          panelId="p3"
          component="diagnosis"
          params={{
            data: {
              class_id: 'c1',
              class_barrier_distribution: { concept: 0.3, reading: 0.2, expression: 0.5 },
            },
          }}
        />
      </ToastProvider>,
    )
    expect(screen.getByText('班级障碍诊断')).toBeInTheDocument()
    expect(screen.getByText('掌握度')).toBeInTheDocument()
    expect(screen.getByText('诊断学生')).toBeInTheDocument()
  })
})

describe('内联出题面板（题型选择回归：Agent 只预填单选时仍有全部题型）', () => {
  function renderPanel(params: Record<string, unknown>) {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve({ ok: true, json: () => Promise.resolve({ knowledge_points: [], data: { exam_sets: [] } }) }),
      ),
    )
    const utils = render(
      <ToastProvider>
        <InlinePanel panelId="pt" component="exam-workbench" params={params} />
      </ToastProvider>,
    )
    return utils
  }

  it('无 params.types → 展示全部 6 种题型 chips（单选/多选/填空/计算/实验/推断）', () => {
    renderPanel({ knowledge_points: ['氧化还原反应'] })
    for (const label of ['单选', '多选', '填空', '计算', '实验', '推断']) {
      expect(screen.getByText(label)).toBeInTheDocument()
    }
    vi.unstubAllGlobals()
  })

  it('Agent 预填 single_choice:5 → 单选选中且数量 5，其余题型仍展示', () => {
    renderPanel({ knowledge_points: ['有机化学'], types: [{ val: 'single_choice', active: true, qty: 5 }] })
    // antd CheckableTag 渲染 span.ant-tag-checkable（2026-08 第二轮 antd 化）
    const single = screen.getByText('单选').closest('.ant-tag-checkable')
    expect(single).not.toBeNull()
    const qtyInput = single!.querySelector('.ant-input-number-input') as HTMLInputElement | null
    expect(qtyInput).not.toBeNull()
    expect(qtyInput!.value).toBe('5')
    expect(single!.className).toContain('bg-primary-soft')
    for (const label of ['多选', '填空', '计算', '实验', '推断']) {
      expect(screen.getByText(label)).toBeInTheDocument()
    }
    vi.unstubAllGlobals()
  })

  it('Agent 预填无 active 字段（generate_questions 路径）→ 按默认值展示，不崩溃', () => {
    renderPanel({ types: [{ val: 'single_choice', qty: 3 }] })
    const single = screen.getByText('单选').closest('.ant-tag-checkable')
    expect(single).not.toBeNull()
    const qtyInput = single!.querySelector('.ant-input-number-input') as HTMLInputElement | null
    expect(qtyInput).not.toBeNull()
    expect(qtyInput!.value).toBe('3')
    expect(screen.getByText('多选')).toBeInTheDocument()
    vi.unstubAllGlobals()
  })
})

describe('内联诊断面板（旧版「针对障碍出题练习」按钮恢复）', () => {
  it('有诊断数据时显示按钮，点击发送消息给 Agent（chemai:send）', () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve({ ok: true, json: () => Promise.resolve({ knowledge_points: [], data: { exam_sets: [] } }) }),
      ),
    )
    const sent: string[] = []
    const listener = (e: Event) => sent.push((e as CustomEvent<string>).detail)
    window.addEventListener('chemai:send', listener)
    render(
      <ToastProvider>
        <InlinePanel
          panelId="pd"
          component="diagnosis"
          params={{
            data: {
              class_barrier_distribution: { concept: 5, reading: 2, expression: 1 },
              students: [{ student_name: '李世睿' }],
            },
          }}
        />
      </ToastProvider>,
    )
    const btn = screen.getByText('针对障碍出题练习')
    expect(btn).toBeInTheDocument()
    btn.click()
    expect(sent).toContain('针对学习障碍出题练习')
    window.removeEventListener('chemai:send', listener)
    vi.unstubAllGlobals()
  })

  it('无诊断数据时不显示按钮', () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve({ ok: true, json: () => Promise.resolve({ knowledge_points: [], data: { exam_sets: [] } }) }),
      ),
    )
    render(
      <ToastProvider>
        <InlinePanel panelId="pd2" component="diagnosis" params={{}} />
      </ToastProvider>,
    )
    expect(screen.queryByText('针对障碍出题练习')).toBeNull()
    vi.unstubAllGlobals()
  })
})

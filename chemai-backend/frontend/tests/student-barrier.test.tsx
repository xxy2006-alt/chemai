/* student-barrier.test.tsx — 学生诊断结果图形化渲染（evals）
 * 回归用户反馈：「以前是能够显示正常渲染的图和表格，现在最多就一个表格了」——
 * diagnose_barrier 学生场景必须渲染障碍条 + 成绩趋势图 + 薄弱知识点表格 + 出题按钮，
 * 不得落到原始 JSON。 */

import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { StudentBarrierResult, ToolResultView } from '../src/components/chat/tool-renderers'

const STUDENT_DATA = {
  student_id: '202610201',
  student_name: '李世睿',
  barrier_distribution: { concept: 0.808, reading: 0.154, expression: 0.038 },
  dominant_barrier: 'concept',
  exercises_completed: 140,
  total_answers: 123,
  correct_answers: 88,
  accuracy: 0.72,
  weak_knowledge_points: [
    { name: '化学平衡', errors: 3 },
    { name: '物质的量', errors: 3 },
    { name: '元素周期律', errors: 3 },
  ],
  score_trend: [
    { date: '02-15', cumulative_rate: 0.57 },
    { date: '03-20', cumulative_rate: 0.6 },
    { date: '08-10', cumulative_rate: 0.71 },
  ],
}

describe('StudentBarrierResult：诊断结果图形化渲染（图 + 表格 + 按钮）', () => {
  it('渲染障碍条 + 趋势图 + 薄弱点表格 + 出题按钮', () => {
    const { container } = render(<StudentBarrierResult data={STUDENT_DATA} />)
    const text = container.textContent || ''
    // 图：障碍百分比条
    expect(text).toContain('概念理解')
    expect(text).toContain('81%')
    expect(text).toContain('主导障碍')
    // 图：成绩趋势（柱形）
    expect(text).toContain('成绩趋势')
    expect(container.querySelectorAll('.bg-teal\\/70').length).toBeGreaterThanOrEqual(3)
    // 表格：薄弱知识点
    expect(text).toContain('薄弱知识点')
    expect(text).toContain('化学平衡')
    expect(text).toContain('3 次')
    // 统计
    expect(text).toContain('140')
    expect(text).toContain('72%')
    // 按钮
    expect(screen.getByText('针对障碍出题练习')).toBeInTheDocument()
  })

  it('点击出题按钮 → 发送「针对李世睿的学习障碍出题练习」', () => {
    const sent: string[] = []
    const listener = (e: Event) => sent.push((e as CustomEvent<string>).detail)
    window.addEventListener('chemai:send', listener)
    render(<StudentBarrierResult data={STUDENT_DATA} />)
    screen.getByText('针对障碍出题练习').click()
    expect(sent).toContain('针对李世睿的学习障碍出题练习')
    window.removeEventListener('chemai:send', listener)
  })

  it('ToolResultView 按学生场景分发（不落 JSON fallback）', () => {
    const { container } = render(<ToolResultView tool="diagnose_barrier" data={STUDENT_DATA} />)
    expect(container.textContent).toContain('成绩趋势')
    expect(container.textContent).toContain('针对障碍出题练习')
    expect(container.textContent).not.toContain('barrier_distribution')
  })

  it('无数据时不渲染图/表格（空数据安全）', () => {
    const { container } = render(<StudentBarrierResult data={{ student_name: 'x' }} />)
    expect(container.textContent).not.toContain('成绩趋势')
    expect(screen.getByText('针对障碍出题练习')).toBeInTheDocument()
  })

  it('班级场景仍走 BarrierOverview（回归：不被学生渲染器误伤）', () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve({ ok: true, json: () => Promise.resolve({ knowledge_points: [], data: { exam_sets: [] } }) }),
      ),
    )
    const { container } = render(
      <ToolResultView
        tool="diagnose_barrier"
        data={{
          class_id: 'class_2025_1',
          total_students: 34,
          barrier_distribution: { concept: 5, reading: 2, expression: 1 },
          students: [{ student_id: '202610101', student_name: '张浩宇', dominant: 'concept' }],
        }}
      />,
    )
    expect(container.textContent).toContain('张浩宇')
    expect(container.textContent).toContain('掌握度')
    vi.unstubAllGlobals()
  })
})

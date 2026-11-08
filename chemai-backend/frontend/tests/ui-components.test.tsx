import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Button, Tag, Badge, StatCard, Skeleton, EmptyState, Tabs } from '../src/components/ui'

describe('UI 组件库（方向 A 现代学术蓝）', () => {
  it('Button 渲染变体与 loading', () => {
    const { rerender } = render(<Button variant="primary">发送</Button>)
    // v2.1 验收后的主按钮是渐变底（btn-gradient），不再是 --primary 纯色块
    expect(screen.getByRole('button', { name: '发送' })).toHaveClass('btn-gradient')
    rerender(
      <Button variant="ai" loading>
        处理中
      </Button>,
    )
    const btn = screen.getByRole('button')
    expect(btn).toBeDisabled()
    expect(btn).toHaveClass('bg-teal')
  })

  it('Tag 浅底深字语义色', () => {
    render(<Tag tone="green">通过</Tag>)
    expect(screen.getByText('通过')).toHaveClass('bg-success-soft', 'text-success')
  })

  it('Badge 状态点 + 标签', () => {
    render(<Badge status="pass" label="四维全过" />)
    expect(screen.getByText('四维全过')).toHaveClass('text-success')
  })

  it('StatCard 展示数值与状态色', () => {
    render(<StatCard label="班级平均分" value={82} suffix="分" tone="ok" />)
    expect(screen.getByText('82')).toBeInTheDocument()
    expect(screen.getByText('班级平均分')).toBeInTheDocument()
    expect(screen.getByText('82')).toHaveClass('text-success')
  })

  it('Skeleton 骨架屏', () => {
    render(<Skeleton className="h-10" />)
    expect(document.querySelector('.animate-pulse')).toBeInTheDocument()
  })

  it('EmptyState 空状态（v2：烧杯图标占位，不暴露开发文案）', () => {
    render(<EmptyState title="暂无学生" description="还没有学生加入班级" />)
    expect(screen.getByText('暂无学生')).toBeInTheDocument()
    // v2 R-S2/P-11：占位统一为烧杯图标（svg），绝不出现「插画待补」类开发文案
    expect(document.querySelector('svg.lucide-flask-conical')).not.toBeNull()
    expect(document.body.textContent).not.toContain('插画待补')
  })

  it('Tabs 切换激活项', () => {
    const items = [
      { key: 'a', label: 'AI 出题' },
      { key: 'b', label: '手动选题' },
    ]
    const { rerender } = render(<Tabs items={items} active="a" onChange={() => {}} />)
    expect(screen.getByText('AI 出题')).toHaveClass('text-primary')
    rerender(<Tabs items={items} active="b" onChange={() => {}} />)
    expect(screen.getByText('手动选题')).toHaveClass('text-primary')
  })
})

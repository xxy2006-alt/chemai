/* think-row.test.tsx — DSH 式思考行（2026-08） */
import { describe, expect, it } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ThinkRow } from '../src/components/chat/MessageList'

describe('思考行（DSH 式）', () => {
  it('折叠态：显示「思考」标题 + 首行摘要，不含全文', () => {
    render(<ThinkRow text={'我来诊断张浩宇的学习障碍。\n先查他的诊断数据。'} />)
    expect(screen.getByText('思考')).toBeInTheDocument()
    expect(screen.getByText('我来诊断张浩宇的学习障碍。')).toBeInTheDocument()
    expect(screen.queryByText('先查他的诊断数据。')).toBeNull()
  })

  it('点击展开显示全文', () => {
    render(<ThinkRow text={'第一行。\n第二行细节。'} />)
    fireEvent.click(screen.getByText('思考'))
    expect(screen.getByText(/第二行细节/)).toBeInTheDocument()
  })

  it('流式态：摘要跟随最新一行', () => {
    render(<ThinkRow text={'第一步。\n正在分析'} streaming />)
    expect(screen.getByText('正在分析')).toBeInTheDocument()
  })
})

/* ocr-page.test.tsx — 答题卡页 antd 化回归（evals）
 * 锁定 2026-08 antd 接入：
 * ① 上传区为 antd Upload.Dragger（拖拽/点击）
 * ② OcrResultTable：题号动态列 + 可编辑单元格 + 置信度配色 + 入库操作
 */

import { describe, expect, it, vi, afterEach } from 'vitest'
import { render, waitFor, screen } from '@testing-library/react'
import { AntdProvider } from '../src/components/antd/AntdProvider'
import { ToastProvider } from '../src/components/ui'
import { OcrPage, OcrResultTable, type OcrResult } from '../src/pages/teacher/OcrPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('答题卡识别页（antd 接入回归）', () => {
  it('上传区为 antd Upload.Dragger', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ classes: [{ class_id: 'c1', name: '2419班' }] }),
        }),
      ),
    )
    render(
      <AntdProvider>
        <ToastProvider>
          <OcrPage />
        </ToastProvider>
      </AntdProvider>,
    )
    await waitFor(() => {
      expect(document.querySelector('.ant-upload-drag')).not.toBeNull()
    })
    expect(document.body.textContent).toContain('拖拽答题卡图片到此处')
  })
})

describe('OcrResultTable（可编辑结果表）', () => {
  const results: OcrResult[] = [
    {
      student_id: '202610201',
      student_name: '李世睿',
      answers: {
        '1': { answer: 'B', confidence: 0.92 },
        '2': { answer: 'C', confidence: 0.55 },
      },
    },
    {
      student_id: '202610101',
      student_name: '张浩宇',
      answers: {
        '1': { answer: 'A', confidence: 0.6 },
      },
    },
  ]

  it('渲染题号动态列 + 可编辑单元格 + 置信度 + 入库按钮', () => {
    render(<OcrResultTable results={results} edited={{}} onEdit={() => {}} onConfirm={() => {}} />)
    const table = document.querySelector('.ant-table')
    expect(table).not.toBeNull()
    const text = table!.textContent || ''
    expect(text).toContain('李世睿')
    expect(text).toContain('张浩宇')
    // 题号列
    expect(text).toContain('1')
    expect(text).toContain('2')
    // 置信度
    expect(text).toContain('92%')
    expect(text).toContain('55%')
    // 可编辑输入框（每题一个）
    expect(table!.querySelectorAll('input').length).toBe(3)
    // 入库按钮
    expect(screen.getAllByText('入库').length).toBe(2)
  })

  it('已编辑单元格显示编辑态（teal 边框 + 铅笔图标），值优先于识别结果', () => {
    render(
      <OcrResultTable
        results={results}
        edited={{ '202610201|2': 'D' }}
        onEdit={() => {}}
        onConfirm={() => {}}
      />,
    )
    const inputs = [...document.querySelectorAll('.ant-table input')] as HTMLInputElement[]
    const editedInput = inputs.find((i) => i.value === 'D')
    expect(editedInput).toBeDefined()
    expect(editedInput!.className).toContain('border-teal')
    // 铅笔图标出现
    expect(document.querySelector('.ant-table .lucide-pencil')).not.toBeNull()
  })

  it('编辑回调携带 cellKey 与值', () => {
    const calls: [string, string][] = []
    render(
      <OcrResultTable
        results={results}
        edited={{}}
        onEdit={(k, v) => calls.push([k, v])}
        onConfirm={() => {}}
      />,
    )
    const inputs = [...document.querySelectorAll('.ant-table input')] as HTMLInputElement[]
    const input = inputs[0]
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')!.set!
    setter.call(input, 'A')
    input.dispatchEvent(new Event('input', { bubbles: true }))
    expect(calls.length).toBeGreaterThan(0)
    expect(calls[0][0]).toBe('202610201|1')
    expect(calls[0][1]).toBe('A')
  })

  it('入库按钮触发 onConfirm(studentId)', () => {
    const confirmed: string[] = []
    render(
      <OcrResultTable results={results} edited={{}} onEdit={() => {}} onConfirm={(id) => confirmed.push(id)} />,
    )
    const btns = screen.getAllByText('入库')
    btns[0].click()
    expect(confirmed).toEqual(['202610201'])
  })
})

/* tool-renderers.test.tsx — 文件/命令工具渲染器（2026-08 read 卡死修复配套）
 * FileReadResult：approval_needed 显示「等待批准」而非「（空文件）」误导。 */
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { FileReadResult } from '../src/components/chat/tool-renderers'

describe('FileReadResult', () => {
  it('approval_needed：显示等待批准文案与目标路径', () => {
    render(
      <FileReadResult
        data={{
          approval_needed: true,
          message: '工作区外访问需要批准: C:\\Users\\Administrator\\Desktop\\x.md',
          target: 'C:\\Users\\Administrator\\Desktop\\x.md',
        }}
      />
    )
    expect(screen.getByText(/等待批准/)).toBeInTheDocument()
    expect(screen.getAllByText(/x\.md/).length).toBeGreaterThanOrEqual(2)
    expect(screen.queryByText('（空文件）')).toBeNull()
  })

  it('正常内容：显示路径行数与内容', () => {
    render(
      <FileReadResult
        data={{ content: '# 标题\n正文', path: 'notes/readme.md', total_lines: 2 }}
      />
    )
    expect(screen.getByText(/readme\.md · 2 行/)).toBeInTheDocument()
    expect(screen.getByText(/正文/)).toBeInTheDocument()
  })

  it('error：显示错误框', () => {
    render(<FileReadResult data={{ error: '文件不存在: x.md' }} />)
    expect(screen.getByText(/文件不存在/)).toBeInTheDocument()
  })
})

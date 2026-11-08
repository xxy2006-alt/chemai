/* students-page.test.tsx — 学生管理页 antd 化回归（evals）
 * 锁定 2026-08 关键不变量：
 * ① antd Table 渲染，演示学生李世睿（202610201）置顶第一行（用户演示路径）
 * ② 详情抽屉为 antd Drawer（Statistic/Progress）
 * ③ 障碍筛选/班级筛选 antd Select 存在
 */

import { describe, expect, it, vi, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AntdProvider } from '../src/components/antd/AntdProvider'
import { ToastProvider } from '../src/components/ui'
import { StudentsPage } from '../src/pages/teacher/StudentsPage'

function mockApi(students: Record<string, unknown>[]) {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      const u = String(url)
      if (u.includes('/api/classes')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              classes: [
                { class_id: 'class_2025_1', name: '2419班' },
                { class_id: 'class_2025_2', name: '2420班' },
              ],
            }),
        })
      }
      if (u.includes('/api/users/students')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ students }) })
      }
      if (u.includes('/api/users/student/')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              weak_knowledge_points: ['化学平衡'],
              recent_activity: [{ date: '08-10', desc: '✓ 化学平衡练习', is_correct: true }],
            }),
        })
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) })
    }),
  )
}

const DEMO_STUDENTS = [
  { student_id: '202610201', name: '李世睿', class_id: 'class_2025_1', class_name: '2419班', exercises_completed: 50, accuracy: 0.72, barrier_type: { concept: 0.8, reading: 0.15, expression: 0.05 }, last_exercise_at: '2026-08-14T10:42:54' },
  { student_id: '202610101', name: '张浩宇', class_id: 'class_2025_1', class_name: '2419班', exercises_completed: 99, accuracy: 0.6, barrier_type: { concept: 0.3, reading: 0.3, expression: 0.4 }, last_exercise_at: '2026-08-11T06:17:10' },
  { student_id: '202610134', name: '方天宇', class_id: 'class_2025_2', class_name: '2420班', exercises_completed: 20, accuracy: 0.5, barrier_type: { reading: 0.7 }, last_exercise_at: '2026-08-10T00:00:00' },
]

afterEach(() => {
  vi.unstubAllGlobals()
  sessionStorage.clear()
})

describe('学生管理页（antd Table + 演示学生置顶）', () => {
  it('渲染 antd Table，李世睿置顶第一行（演示学生固定优先）', async () => {
    mockApi(DEMO_STUDENTS)
    render(
      <AntdProvider>
        <ToastProvider>
          <MemoryRouter>
            <StudentsPage />
          </MemoryRouter>
        </ToastProvider>
      </AntdProvider>,
    )
    await waitFor(() => {
      expect(document.querySelector('.ant-table')).not.toBeNull()
    })
    const rows = [...document.querySelectorAll('.ant-table-tbody .ant-table-row')]
    expect(rows.length).toBeGreaterThanOrEqual(3)
    expect(rows[0].textContent).toContain('李世睿')
    expect(rows[0].textContent).toContain('202610201')
    // 其余按练习数降序：张浩宇(99) 在 方天宇(20) 前
    expect(rows[1].textContent).toContain('张浩宇')
    expect(rows[2].textContent).toContain('方天宇')
  })

  it('障碍/班级筛选为 antd Select，搜索为 antd Input', async () => {
    mockApi(DEMO_STUDENTS)
    render(
      <AntdProvider>
        <ToastProvider>
          <MemoryRouter>
            <StudentsPage />
          </MemoryRouter>
        </ToastProvider>
      </AntdProvider>,
    )
    await waitFor(() => {
      expect(document.querySelector('.ant-table')).not.toBeNull()
    })
    expect(document.querySelectorAll('.ant-select').length).toBeGreaterThanOrEqual(2)
    expect(document.querySelector('.ant-input')).not.toBeNull()
  })

  it('点击行打开 antd Drawer（Statistic/Progress）', async () => {
    mockApi(DEMO_STUDENTS)
    render(
      <AntdProvider>
        <ToastProvider>
          <MemoryRouter>
            <StudentsPage />
          </MemoryRouter>
        </ToastProvider>
      </AntdProvider>,
    )
    await waitFor(() => {
      expect(document.querySelector('.ant-table')).not.toBeNull()
    })
    const rows = [...document.querySelectorAll('.ant-table-tbody .ant-table-row')] as HTMLElement[]
    rows[0].click()
    await waitFor(() => {
      expect(document.querySelector('.ant-drawer')).not.toBeNull()
    })
    expect(document.querySelector('.ant-statistic')).not.toBeNull()
    expect(document.querySelector('.ant-progress')).not.toBeNull()
    expect(screen.getByText('障碍诊断')).toBeInTheDocument()
  })
})

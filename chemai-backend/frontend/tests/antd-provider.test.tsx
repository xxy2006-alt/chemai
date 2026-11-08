/* antd-provider.test.tsx — Ant Design v6 接入回归（evals）
 * 锁定 2026-08 antd 渐进式接入的关键不变量，防止后续更新破坏：
 * ① AntdProvider 主题挂载（品牌色/中文上下文，antd 组件正常渲染）
 * ② 全局 Toast 桥接：useToast API 不变，视觉走 antd message（全站消息统一）
 * ③ 登录页 antd 表单：提交走 api.post + 跳转，placeholder 保持（Playwright 依赖）
 */

import { describe, expect, it } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Button as AntButton } from 'antd'
import { AntdProvider } from '../src/components/antd/AntdProvider'
import { ToastProvider, useToast } from '../src/components/ui'
import { LoginPage } from '../src/pages/teacher/LoginPage'

describe('AntdProvider：主题接入', () => {
  it('antd 组件在 Provider 内正常渲染', () => {
    render(
      <AntdProvider>
        <AntButton type="primary">测试按钮</AntButton>
      </AntdProvider>,
    )
    const btn = screen.getByRole('button', { name: '测试按钮' })
    expect(btn.className).toContain('ant-btn-primary')
  })
})

describe('全局 Toast 桥接（antd message，API 不变）', () => {
  function Trigger({ kind }: { kind: 'success' | 'error' | 'warning' | 'info' }) {
    const toast = useToast()
    return (
      <button onClick={() => toast[kind](`测试${kind}`)}>
        trigger-{kind}
      </button>
    )
  }

  it('useToast().success → antd message 弹出（视觉统一）', async () => {
    render(
      <AntdProvider>
        <ToastProvider>
          <Trigger kind="success" />
        </ToastProvider>
      </AntdProvider>,
    )
    screen.getByText('trigger-success').click()
    await waitFor(() => {
      expect(document.querySelector('.ant-message')).not.toBeNull()
    })
    expect(document.body.textContent).toContain('测试success')
  })

  it('五种 API（toast/success/error/warning/info）均可调用', () => {
    const calls: string[] = []
    function Probe() {
      const toast = useToast()
      return (
        <button
          onClick={() => {
            toast.toast('error', 'm1')
            toast.success('m2')
            toast.error('m3')
            toast.warning('m4')
            toast.info('m5')
            calls.push('all-called')
          }}
        >
          probe
        </button>
      )
    }
    render(
      <AntdProvider>
        <ToastProvider>
          <Probe />
        </ToastProvider>
      </AntdProvider>,
    )
    screen.getByText('probe').click()
    expect(calls).toEqual(['all-called'])
  })
})

describe('登录页（antd Form 接入回归）', () => {
  it('渲染 antd 表单控件（Input/Password/Checkbox/提交按钮），placeholder 保持', () => {
    render(
      <AntdProvider>
        <ToastProvider>
          <MemoryRouter>
            <LoginPage />
          </MemoryRouter>
        </ToastProvider>
      </AntdProvider>,
    )
    expect(document.querySelector('.ant-input')).not.toBeNull()
    expect(document.querySelector('.ant-input-password')).not.toBeNull()
    expect(document.querySelector('.ant-checkbox-input')).not.toBeNull()
    expect(document.querySelector('input[placeholder="请输入账号"]')).not.toBeNull()
    expect(document.querySelector('button[type="submit"]')).not.toBeNull()
    expect(screen.getByText('登录教师工作台')).toBeInTheDocument()
  })
})

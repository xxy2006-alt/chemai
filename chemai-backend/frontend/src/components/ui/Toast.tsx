import { createContext, useContext, useMemo, type ReactNode } from 'react'
import { App } from 'antd'

export type ToastKind = 'success' | 'info' | 'warning' | 'error'

interface ToastContextValue {
  toast: (kind: ToastKind, message: string) => void
  success: (message: string) => void
  error: (message: string) => void
  info: (message: string) => void
  warning: (message: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

/** 全局消息提示（2026-08 antd 接入）：API 不变（success/error/warning/info），
 * 视觉升级为 antd message（App.useApp 上下文，须在 AntdProvider 内） */
function ToastBridge({ children }: { children: ReactNode }) {
  const { message } = App.useApp()
  const value = useMemo<ToastContextValue>(
    () => ({
      toast: (kind, m) => message.open({ type: kind, content: m }),
      success: (m) => message.success(m),
      error: (m) => message.error(m),
      info: (m) => message.info(m),
      warning: (m) => message.warning(m),
    }),
    [message],
  )
  return <ToastContext.Provider value={value}>{children}</ToastContext.Provider>
}

export function ToastProvider({ children }: { children: ReactNode }) {
  return <ToastBridge>{children}</ToastBridge>
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast 必须在 ToastProvider 内使用')
  return ctx
}

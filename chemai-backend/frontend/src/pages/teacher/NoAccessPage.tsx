import { useNavigate } from 'react-router-dom'
import { Button } from 'antd'
import { LogOut, ShieldAlert } from 'lucide-react'
import { clearAuth, getCaps } from '../../lib/api'

/**
 * 登录了、但没有教师端权限（阶段 5.3）。
 *
 * 学生 / 家长走 `m/` 移动端，后端给他们的 `menus` 是空数组。这里**不能**直接弹回
 * 登录页 —— 用户刚登录成功又被弹回去，会以为登录失败、反复重登。要明确告诉他
 * 「你是谁、为什么进不来、该去哪」。
 */
export function NoAccessPage() {
  const navigate = useNavigate()
  const caps = getCaps()

  function handleLogout() {
    clearAuth()
    navigate('/login', { replace: true })
  }

  return (
    <div className="h-full flex items-center justify-center bg-surface-muted p-6">
      <div className="max-w-md w-full bg-surface rounded-[var(--radius-lg)] border border-border p-8 text-center">
        <div className="w-12 h-12 mx-auto rounded-full bg-warning-soft flex items-center justify-center mb-4">
          <ShieldAlert size={22} className="text-warning" />
        </div>
        <h1 className="text-lg font-semibold text-ink mb-2">当前账号没有教师端权限</h1>
        <p className="text-sm text-ink-secondary leading-relaxed">
          你登录的身份是
          <span className="mx-1 font-medium text-ink">{caps?.role_label || caps?.role || '未知角色'}</span>
          ，教师工作台不对该角色开放。
        </p>
        <p className="text-sm text-ink-muted mt-3 leading-relaxed">
          学生请使用学生端，家长请使用家长端（移动端页面）。
        </p>
        <Button className="mt-6" onClick={handleLogout} icon={<LogOut size={14} />}>
          退出登录
        </Button>
      </div>
    </div>
  )
}

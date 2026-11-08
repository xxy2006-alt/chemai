/* StudentLoginPage — 学生登录（design/学生端.md：品牌蓝仅在此页出现，R-S-C6） */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../../lib/api'
import { setMobileSession } from '../../../lib/mobile-auth'
import { MobileLayout } from '../../../components/mobile/MobileLayout'

interface LoginResp {
  success?: boolean
  message?: string
  token: string
  refresh_token?: string
  user: { id: string; username?: string; name?: string; role?: string; school?: string; class_name?: string; class_id?: string }
}

export function StudentLoginPage() {
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    document.title = '智辅化学 · 学生登录'
  }, [])

  async function handleLogin() {
    if (!username.trim() || !password.trim()) {
      setMsg({ text: '请输入学号和密码', ok: false })
      return
    }
    setLoading(true)
    setMsg(null)
    try {
      const d = await api.post<LoginResp>(
        '/api/auth/login',
        { username: username.trim(), password: password.trim() },
        { public: true },
      )
      setMobileSession(d.token, {
        id: d.user.id,
        username: d.user.username,
        name: d.user.name,
        role: d.user.role,
        school: d.user.school,
        class_name: d.user.class_name,
        class_id: d.user.class_id,
      })
      navigate('/m', { replace: true })
    } catch (e) {
      setMsg({ text: e instanceof Error ? e.message : '网络错误，请重试', ok: false })
      setLoading(false)
    }
  }

  return (
    <MobileLayout theme="student">
      <div className="min-h-[100dvh] flex flex-col justify-center px-8 pb-16">
        {/* 品牌时刻：唯一允许品牌蓝的页面（R-S-C6） */}
        <div className="text-center mb-10">
          <div
            className="mx-auto w-16 h-16 rounded-[20px] flex items-center justify-center text-[28px] font-bold mb-4"
            style={{ background: 'linear-gradient(135deg, var(--color-primary), var(--color-accent-deep))' }}
          >
            <span className="font-mono text-white">H₂O</span>
          </div>
          <h1 className="font-display text-[26px] font-black text-ink">智辅化学</h1>
          <p className="text-[13px] text-ink-muted mt-1.5">学生登录 · 你的 AI 化学助教</p>
        </div>

        <div className="space-y-3.5">
          <div>
            <label className="block text-[12px] text-ink-secondary mb-1.5">学号</label>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="输入学号"
              autoComplete="username"
              className="w-full h-12 px-4 rounded-full border-[1.5px] border-border bg-surface-muted text-[15px] text-ink placeholder:text-ink-muted outline-none focus:border-primary transition-colors"
            />
          </div>
          <div>
            <label className="block text-[12px] text-ink-secondary mb-1.5">密码</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
              placeholder="输入密码"
              autoComplete="current-password"
              className="w-full h-12 px-4 rounded-full border-[1.5px] border-border bg-surface-muted text-[15px] text-ink placeholder:text-ink-muted outline-none focus:border-primary transition-colors"
            />
          </div>

          <button
            onClick={handleLogin}
            disabled={loading}
            className="w-full h-12 mt-2 rounded-full bg-primary text-on-primary text-[15px] font-bold active:scale-[0.98] transition-transform disabled:opacity-50"
          >
            {loading ? '登录中…' : '登录'}
          </button>

          {msg && (
            <p className={`text-center text-[13px] min-h-[20px] ${msg.ok ? 'text-success' : 'text-error'}`}>
              {msg.text}
            </p>
          )}
        </div>

        <p className="text-center text-[11px] text-ink-muted mt-10">
          智辅化学 ChemAI · 教师出题 · 学生辅导 · 家长关注
        </p>
      </div>
    </MobileLayout>
  )
}

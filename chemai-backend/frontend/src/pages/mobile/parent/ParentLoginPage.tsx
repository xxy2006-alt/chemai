/* ParentLoginPage — 家长登录（design/家长端.md：鼠尾草画布 + 亮绿 CTA 胶囊 + 强描边输入）。 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Phone, LockKeyhole, GraduationCap } from 'lucide-react'
import { api } from '../../../lib/api'
import { setMobileSession } from '../../../lib/mobile-auth'
import { MobileLayout } from '../../../components/mobile/MobileLayout'

interface ParentLoginResp {
  success?: boolean
  message?: string
  detail?: string
  parent_id?: string
  name?: string
  token?: string
}

export function ParentLoginPage() {
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    document.title = '智辅化学 · 家长登录'
  }, [])

  async function handleLogin() {
    if (!username.trim() || !password.trim()) {
      setMsg({ text: '请填写用户名和密码', ok: false })
      return
    }
    setLoading(true)
    setMsg(null)
    try {
      const d = await api.post<ParentLoginResp>('/api/parent/login', {
        username: username.trim(),
        password: password.trim(),
      }, { public: true })
      if (d.success && d.token) {
        setMobileSession(d.token, {
          id: d.parent_id || '',
          username: username.trim(),
          name: d.name || '家长',
          role: 'parent',
        })
        navigate('/m/parent', { replace: true })
      } else {
        setMsg({ text: d.message || d.detail || '用户名或密码错误', ok: false })
        setLoading(false)
      }
    } catch (e) {
      setMsg({ text: e instanceof Error ? e.message : '网络错误，请检查后端是否启动', ok: false })
      setLoading(false)
    }
  }

  return (
    <MobileLayout theme="parent">
      <div className="min-h-[100dvh] flex flex-col justify-center px-8 pb-16">
        {/* 品牌 hero（Wise 签名时刻：sage 画布 + 900 大字） */}
        <div className="text-center mb-10">
          <div className="mx-auto w-16 h-16 rounded-[24px] bg-primary-soft flex items-center justify-center mb-4">
            <GraduationCap size={30} className="text-primary" />
          </div>
          <h1 className="font-display text-[28px] font-black text-ink leading-tight">智辅化学</h1>
          <p className="text-[13px] text-ink-secondary mt-1.5">关注孩子的每一步成长</p>
        </div>

        <div className="bg-surface rounded-[24px] p-6 shadow-sm">
          <h2 className="font-bold text-[17px] text-ink mb-4">家长登录</h2>
          <div className="space-y-3.5">
            <div>
              <label className="block text-[12px] text-ink-secondary mb-1.5">手机号 或 用户名</label>
              <div className="flex items-center h-13 rounded-xl border-[1.5px] border-ink bg-surface px-4 focus-within:border-primary transition-colors">
                <Phone size={17} className="text-ink-muted shrink-0" />
                <input
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="输入手机号或用户名"
                  autoComplete="username"
                  className="flex-1 min-w-0 h-13 py-3.5 pl-3 bg-transparent text-[15px] text-ink placeholder:text-ink-muted/70 outline-none"
                />
              </div>
            </div>
            <div>
              <label className="block text-[12px] text-ink-secondary mb-1.5">密码</label>
              <div className="flex items-center h-13 rounded-xl border-[1.5px] border-ink bg-surface px-4 focus-within:border-primary transition-colors">
                <LockKeyhole size={17} className="text-ink-muted shrink-0" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
                  placeholder="输入密码"
                  autoComplete="current-password"
                  className="flex-1 min-w-0 h-13 py-3.5 pl-3 bg-transparent text-[15px] text-ink placeholder:text-ink-muted/70 outline-none"
                />
              </div>
            </div>
            <button
              onClick={handleLogin}
              disabled={loading}
              className="w-full h-13 mt-1 rounded-[24px] bg-primary text-on-primary text-[16px] font-bold active:scale-[0.98] transition-transform disabled:opacity-60"
            >
              {loading ? '登录中…' : '进入'}
            </button>
            {msg && (
              <p className={`text-center text-[13px] min-h-[20px] ${msg.ok ? 'text-success' : 'text-error'}`}>{msg.text}</p>
            )}
          </div>
        </div>

        <p className="text-center text-[12px] text-ink-muted mt-6 leading-relaxed">
          还没有账号？请联系老师开通家长账号
          <br />
          注册后需绑定孩子的学号和绑定码
        </p>
      </div>
    </MobileLayout>
  )
}

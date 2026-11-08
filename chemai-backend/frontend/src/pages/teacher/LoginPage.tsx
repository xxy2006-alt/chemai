import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Checkbox, Form, Input } from 'antd'
import { UserRound, LockKeyhole } from 'lucide-react'
import { getToken, login } from '../../lib/api'
import { useToast } from '../../components/ui'
import { assets } from '../../assets'

/* 登录背景（切换背景图改这一行）：
 * assets.loginBg       —— 原版插画：化学实验室（浅蓝，默认）
 * assets.loginBgAlt1   —— 墨蓝分子网络（深色）
 * assets.loginBgAlt2   —— 浅色六边形分子（浅蓝） */
const LOGIN_BG = assets.loginBg

/* 合并说明：原来这里还有一个 LoginResponse 接口与 `api.post<LoginResponse>` 的
 * 自抄登录逻辑 —— main 已改成走 lib/api 的共享 login()（它一并存能力清单），
 * 那个接口没有引用点，未保留。 */
interface LoginForm {
  username: string
  password: string
  remember?: boolean
}

/** 登录页 · 方向 A：左侧品牌区（元素符号装饰）+ 右侧表单（antd Form，2026-08 antd 接入） */
export function LoginPage() {
  const navigate = useNavigate()
  const toast = useToast()
  const [form] = Form.useForm<LoginForm>()
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (getToken()) navigate('/chat', { replace: true })
    // 读取记住的账号
    try {
      const saved = JSON.parse(localStorage.getItem('chemai_remember') || 'null')
      if (saved?.username) form.setFieldsValue({ username: saved.username })
    } catch {
      /* 忽略损坏的本地存储 */
    }
  }, [navigate, form])

  async function handleFinish(values: LoginForm) {
    const remember = values.remember !== false
    setLoading(true)
    try {
      // 走 lib/api 的共享 login()：它一并存 token / teacher_id / **能力清单**。
      // 这里以前自己抄了一份登录逻辑，结果阶段 5 的能力清单存不进去 —— 同一件事两个入口。
      const data = await login(values.username, values.password)
      if (remember) {
        localStorage.setItem('chemai_remember', JSON.stringify({ username: values.username }))
      } else {
        localStorage.removeItem('chemai_remember')
      }
      toast.success(`欢迎回来，${data.user.name || data.user.username}`)
      navigate('/chat', { replace: true })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '登录失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="min-h-full flex bg-cover bg-center"
      style={{ backgroundImage: `url(${LOGIN_BG})` }}
    >
      {/* 左侧品牌区（直接叠加在登录背景图上，深色字） */}
      <div className="hidden lg:flex w-[46%] flex-col justify-between p-12 relative overflow-hidden">
        <div className="relative z-10 flex items-center gap-3">
          <img
            src={assets.logoMark}
            alt="智辅化学"
            className="w-11 h-11 rounded-[var(--radius-md)] object-cover border border-border"
          />
          <div>
            <div className="text-primary text-lg font-semibold leading-tight">智辅化学</div>
            <div className="text-ink-secondary text-xs tracking-widest mt-0.5">CHEMAI · 教师工作台</div>
          </div>
        </div>
        <div className="relative z-10 flex items-center gap-4 font-mono text-lg select-none">
          {['H', 'O', 'C', 'Fe', 'Cu', 'Ag'].map((el) => (
            <span key={el} className="w-10 h-10 rounded-[var(--radius-md)] bg-primary-soft text-primary font-semibold flex items-center justify-center">
              {el}
            </span>
          ))}
        </div>
        {/* 背景装饰：化学式 */}
        <div className="absolute -right-8 -bottom-10 text-primary/[0.05] font-mono text-[120px] leading-none select-none">
          H₂SO₄
        </div>
      </div>

      {/* 右侧表单 */}
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-[400px] bg-surface/95 backdrop-blur rounded-[var(--radius-lg)] shadow-lg border border-border p-8 animate-fade-in-up">
          <div className="lg:hidden flex items-center gap-2.5 mb-8 justify-center">
            <img
              src={assets.logoMark}
              alt="智辅化学"
              className="w-9 h-9 rounded-[var(--radius-md)] object-cover border border-border"
            />
            <span className="text-lg font-semibold text-ink">智辅化学</span>
          </div>
          <h1 className="text-[22px] font-semibold text-ink m-0">登录教师工作台</h1>
          <p className="mt-1.5 text-sm text-ink-secondary">欢迎回来，请输入账号信息</p>
          <Form
            form={form}
            layout="vertical"
            requiredMark={false}
            initialValues={{ remember: true }}
            onFinish={handleFinish}
            className="mt-6"
          >
            <Form.Item
              name="username"
              label={<span className="text-[13px] text-ink-secondary">账号</span>}
              rules={[{ required: true, message: '请输入账号' }]}
            >
              <Input
                size="large"
                placeholder="请输入账号"
                autoComplete="username"
                prefix={<UserRound size={15} className="text-ink-muted" />}
              />
            </Form.Item>
            <Form.Item
              name="password"
              label={<span className="text-[13px] text-ink-secondary">密码</span>}
              rules={[{ required: true, message: '请输入密码' }]}
            >
              <Input.Password
                size="large"
                placeholder="请输入密码"
                autoComplete="current-password"
                prefix={<LockKeyhole size={15} className="text-ink-muted" />}
              />
            </Form.Item>
            <div className="flex justify-between items-center mb-2">
              <Form.Item name="remember" valuePropName="checked" noStyle>
                <Checkbox>记住账号</Checkbox>
              </Form.Item>
            </div>
            <Button type="primary" htmlType="submit" loading={loading} block size="large" className="btn-gradient-antd">
              登 录
            </Button>
          </Form>
        </div>
      </div>
    </div>
  )
}

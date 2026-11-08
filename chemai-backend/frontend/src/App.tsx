import { lazy, Suspense, type ReactNode } from 'react'
import { HashRouter, Navigate, Outlet, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { LogOut, Loader2 } from 'lucide-react'
import { clearAuth, getToken, hasMenu } from './lib/api'
import { useCapabilities } from './lib/use-capabilities'
import { ToastProvider } from './components/ui'
import { AntdProvider } from './components/antd/AntdProvider'
import { assets } from './assets'
import { ChatPage } from './pages/teacher/ChatPage'
import { LoginPage } from './pages/teacher/LoginPage'
import { NoAccessPage } from './pages/teacher/NoAccessPage'

/* 路由级代码分割：图表/大页面按需加载（echarts/katex 不进首屏包） */
const ClassPage = lazy(() => import('./pages/teacher/ClassPage').then((m) => ({ default: m.ClassPage })))
const StudentsPage = lazy(() => import('./pages/teacher/StudentsPage').then((m) => ({ default: m.StudentsPage })))
const ExamPage = lazy(() => import('./pages/teacher/ExamPage').then((m) => ({ default: m.ExamPage })))
const DiagnosisPage = lazy(() => import('./pages/teacher/DiagnosisPage').then((m) => ({ default: m.DiagnosisPage })))
const OcrPage = lazy(() => import('./pages/teacher/OcrPage').then((m) => ({ default: m.OcrPage })))
const OcrSheetsPage = lazy(() => import('./pages/teacher/OcrSheetsPage').then((m) => ({ default: m.OcrSheetsPage })))
const IntegrationPage = lazy(() =>
  import('./pages/teacher/IntegrationPage').then((m) => ({ default: m.IntegrationPage })),
)

/* ── 移动端（学生/家长）· ADR-0001 并入同一 SPA，主题按端作用域（design/分册） ── */
const StudentLoginPage = lazy(() => import('./pages/mobile/student/StudentLoginPage').then((m) => ({ default: m.StudentLoginPage })))
const StudentChatPage = lazy(() => import('./pages/mobile/student/StudentChatPage').then((m) => ({ default: m.StudentChatPage })))
const PracticePage = lazy(() => import('./pages/mobile/student/PracticePage').then((m) => ({ default: m.PracticePage })))
const WrongBookPage = lazy(() => import('./pages/mobile/student/WrongBookPage').then((m) => ({ default: m.WrongBookPage })))
const ReviewCenterPage = lazy(() => import('./pages/mobile/student/ReviewCenterPage').then((m) => ({ default: m.ReviewCenterPage })))
const ProfilePage = lazy(() => import('./pages/mobile/student/ProfilePage').then((m) => ({ default: m.ProfilePage })))
const ParentLoginPage = lazy(() => import('./pages/mobile/parent/ParentLoginPage').then((m) => ({ default: m.ParentLoginPage })))
const ParentHomePage = lazy(() => import('./pages/mobile/parent/ParentHomePage').then((m) => ({ default: m.ParentHomePage })))

/* 菜单注册表：菜单 key（后端下发）→ 展示信息。
   权限单一真源在后端（`app/middleware/auth.py` 的 MENUS），
   展示细节单一真源在这里 —— 元素符号、中文名、路径都是前端的事。
   导航顺序沿用后端下发的顺序（见 navItemsFor）。
   （合并说明：design-upgrade 的硬编码 NAV_ITEMS 已被本注册表取代、无引用点，未保留。） */
export const MENU_REGISTRY: Record<string, { path: string; label: string; symbol: string }> = {
  chat: { path: '/chat', label: 'Agent 工作台', symbol: 'H' },
  class: { path: '/class', label: '班级学情', symbol: 'O' },
  students: { path: '/students', label: '学生管理', symbol: 'C' },
  exam: { path: '/exam', label: '出题工作台', symbol: 'Fe' },
  diagnosis: { path: '/diagnosis', label: '诊断分析', symbol: 'Cu' },
  ocr: { path: '/ocr-sheets', label: '判卷中心', symbol: 'Ag' },
  integration: { path: '/integration', label: 'LMS 集成', symbol: 'Zn' },
}

/** 路由 → 它归哪个菜单管。守卫按这个判断「这个角色能不能进这一页」。 */
export const ROUTE_MENU: Record<string, string> = {
  '/chat': 'chat',
  '/class': 'class',
  '/students': 'students',
  '/exam': 'exam',
  '/diagnosis': 'diagnosis',
  '/ocr': 'ocr', // 答题卡识别页没有独立导航入口，与判卷中心同一个菜单 key
  '/ocr-sheets': 'ocr',
  '/integration': 'integration',
}

/**
 * 后端下发的菜单 key 列表 → 渲染用的导航项。
 *
 * 顺序沿用后端下发的顺序（菜单排序是权限侧的决定）。
 * 认不出的 key **跳过但告警** —— 前后端版本不一致时不崩，但也不能悄悄少一个菜单：
 * 静默丢弃会表现成「后端加了菜单、前端就是不显示」，很难查。
 */
export function navItemsFor(menuKeys: string[]) {
  return menuKeys
    .map((key) => {
      const meta = MENU_REGISTRY[key]
      if (!meta) {
        console.warn(
          `[menu] 后端下发了前端不认识的菜单 key "${key}" —— 需要在 App.tsx 的 MENU_REGISTRY 补上对应页面`,
        )
        return null
      }
      return { key, ...meta }
    })
    .filter((item): item is NavItem => item !== null)
}

export type NavItem = { key: string; path: string; label: string; symbol: string }

function Shell({ items }: { items: NavItem[] }) {
  const navigate = useNavigate()
  const location = useLocation()
  const active = items.find((n) => location.pathname.startsWith(n.path))
  // Agent 工作台独占视口高度（消息区内部滚动、输入框钉底），其余页面整页滚动
  const isAgentWorkbench = location.pathname.startsWith('/chat')

  function handleLogout() {
    clearAuth()
    navigate('/login', { replace: true })
  }

  return (
    <div
      className="h-full flex bg-cover bg-center"
      style={{ backgroundImage: `url(${assets.mainBg})` }}
    >
      {/* 侧边栏（品牌底图 navBg + 玻璃质感，v2 细节保留） */}
      <aside
        className="w-[var(--sidebar-width)] shrink-0 bg-cover bg-center border-r border-border flex flex-col"
        style={{ backgroundImage: `url(${assets.navBg})` }}
      >
        <div className="px-5 pt-5 pb-4 flex items-center gap-2.5">
          <img
            src={assets.logoMark}
            alt="智辅化学"
            className="w-9 h-9 rounded-[var(--radius-md)] object-cover shrink-0 border border-border"
          />
          <div>
            <div className="text-[15px] font-semibold text-ink leading-tight">智辅化学</div>
            <div className="text-[10px] text-ink-muted tracking-widest mt-0.5">CHEMAI · 教师端</div>
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto px-2.5 py-2 space-y-0.5">
          {items.map((item) => {
            const isActive = location.pathname.startsWith(item.path)
            return (
              <button
                key={item.path}
                onClick={() => navigate(item.path)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-[var(--radius-md)] text-sm transition-colors cursor-pointer text-left ${
                  isActive
                    ? 'bg-primary-soft text-primary font-medium'
                    : 'text-ink-secondary hover:bg-white/60 hover:text-ink'
                }`}
              >
                <span
                  className={`w-7 h-7 rounded-[var(--radius-sm)] flex items-center justify-center font-mono text-[13px] font-semibold shrink-0 transition-colors ${
                    isActive ? 'btn-gradient text-white' : 'bg-white/80 text-ink'
                  }`}
                >
                  {item.symbol}
                </span>
                {item.label}
              </button>
            )
          })}
        </nav>

        <div className="px-4 py-3 border-t border-border">
          <div className="flex items-center justify-between">
            <span className="text-xs text-ink-muted">{active?.label ?? '教师工作台'}</span>
            <button
              onClick={handleLogout}
              className="flex items-center gap-1 text-xs text-ink-secondary hover:text-error transition-colors cursor-pointer"
              title="退出登录"
            >
              <LogOut size={14} />
              退出
            </button>
          </div>
        </div>
      </aside>

      {/* 主区域 */}
      <main className={`flex-1 min-w-0 ${isAgentWorkbench ? 'overflow-hidden' : 'overflow-y-auto'}`}>
        {isAgentWorkbench ? (
          <Outlet />
        ) : (
          <div className="max-w-[var(--container-max)] mx-auto p-6 lg:p-8">
            <Outlet />
          </div>
        )}
      </main>
    </div>
  )
}

/**
 * 需登录的布局路由。
 *
 * 三种状态要分开处理，别合并：
 *   - 没有 token          → 弹回登录页
 *   - 在拉能力清单        → 转圈（别先渲染再闪走）
 *   - 有身份但没有菜单    → 「无教师端权限」页（学生/家长），**不能**弹回登录页
 */
function ProtectedLayout() {
  const { caps, loading } = useCapabilities()
  if (!getToken()) return <Navigate to="/login" replace />
  if (loading) return <PageFallback />
  if (!caps || caps.menus.length === 0) return <NoAccessPage />
  return <Shell items={navItemsFor(caps.menus)} />
}

/**
 * 路由守卫：该角色没有这一页对应的菜单 → 送到它能进的第一页。
 *
 * ⚠️ 这是 **UX 一致性**，不是安全边界 —— 真正的边界在后端端点（阶段 4 已落地）。
 * 守卫写错只会让人看到点不动的页面，不会漏数据。
 */
function RequireMenu({ menuKey, children }: { menuKey: string; children: ReactNode }) {
  const { caps } = useCapabilities()
  if (!hasMenu(menuKey)) {
    const fallback = navItemsFor(caps?.menus ?? [])[0]?.path
    return fallback ? <Navigate to={fallback} replace /> : <NoAccessPage />
  }
  return <>{children}</>
}

/** 移动端会话守卫（学生/家长各自登录页；用户画像在 sessionStorage，e2e 兼容旧约定） */
function RequireMobile({ login }: { login: string }) {
  if (!getToken() || !sessionStorage.getItem('chemai_user')) return <Navigate to={login} replace />
  return <Outlet />
}

function PageFallback() {
  return (
    <div className="flex items-center justify-center py-24">
      <Loader2 size={22} className="animate-spin text-teal" />
    </div>
  )
}

/** 兜底跳转：落到该角色能进的第一个菜单。 */
function HomeRedirect() {
  const { caps } = useCapabilities()
  const first = navItemsFor(caps?.menus ?? [])[0]?.path
  return first ? <Navigate to={first} replace /> : <NoAccessPage />
}

export function App() {
  return (
    <AntdProvider>
      <ToastProvider>
        <HashRouter>
          <Suspense fallback={<PageFallback />}>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route element={<ProtectedLayout />}>
                <Route path="/chat" element={<RequireMenu menuKey="chat"><ChatPage /></RequireMenu>} />
                <Route path="/class" element={<RequireMenu menuKey="class"><ClassPage /></RequireMenu>} />
                <Route path="/students" element={<RequireMenu menuKey="students"><StudentsPage /></RequireMenu>} />
                <Route path="/exam" element={<RequireMenu menuKey="exam"><ExamPage /></RequireMenu>} />
                <Route path="/diagnosis" element={<RequireMenu menuKey="diagnosis"><DiagnosisPage /></RequireMenu>} />
                <Route path="/ocr" element={<RequireMenu menuKey="ocr"><OcrPage /></RequireMenu>} />
                <Route path="/ocr-sheets" element={<RequireMenu menuKey="ocr"><OcrSheetsPage /></RequireMenu>} />
                <Route path="/integration" element={<RequireMenu menuKey="integration"><IntegrationPage /></RequireMenu>} />
                <Route path="*" element={<HomeRedirect />} />
              </Route>

              {/* ── 移动端 · 学生（深色单彩，design/学生端.md） ── */}
              <Route path="/m/login" element={<StudentLoginPage />} />
              <Route element={<RequireMobile login="/m/login" />}>
                <Route path="/m" element={<StudentChatPage />} />
                <Route path="/m/practice" element={<PracticePage />} />
                <Route path="/m/wrong" element={<WrongBookPage />} />
                <Route path="/m/review" element={<ReviewCenterPage />} />
                <Route path="/m/me" element={<ProfilePage />} />
              </Route>

              {/* ── 移动端 · 家长（鼠尾草浅色，design/家长端.md） ── */}
              <Route path="/m/parent-login" element={<ParentLoginPage />} />
              <Route element={<RequireMobile login="/m/parent-login" />}>
                <Route path="/m/parent" element={<ParentHomePage />} />
              </Route>

              <Route path="*" element={<Navigate to="/chat" replace />} />
            </Routes>
          </Suspense>
        </HashRouter>
      </ToastProvider>
    </AntdProvider>
  )
}

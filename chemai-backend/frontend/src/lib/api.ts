/* ChemAI 教师端 · 类型化 API 客户端
   URL 与后端 FastAPI 完全一致，鉴权沿用旧前端约定：
   localStorage['token'] + Authorization: Bearer <token> */

const TOKEN_KEY = 'token'
const TEACHER_ID_KEY = 'teacher_id'
const CAPS_KEY = 'chemai_caps'

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function getTeacherId(): string {
  return localStorage.getItem(TEACHER_ID_KEY) || ''
}

export function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(TEACHER_ID_KEY)
  localStorage.removeItem(CAPS_KEY)
}

export class ApiError extends Error {
  status: number
  detail: string
  constructor(status: number, detail: string) {
    super(detail)
    this.status = status
    this.detail = detail
  }
}

export interface RequestOptions {
  method?: string
  body?: unknown
  headers?: Record<string, string>
  /** 不自动附带 Authorization（公开接口） */
  public?: boolean
  /** 原始文本响应（SSE 等） */
  raw?: boolean
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { ...opts.headers }
  if (opts.body !== undefined && !(opts.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }
  if (!opts.public && !headers['Authorization']) {
    const token = getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
  }
  const init: RequestInit = { method: opts.method || 'GET', headers }
  if (opts.body !== undefined) {
    init.body = opts.body instanceof FormData ? opts.body : JSON.stringify(opts.body)
  }
  const resp = await fetch(path, init)
  if (!resp.ok) {
    // token 失效：清除本地凭证并回登录页（服务重启/token 过期后，
    // 页面会停在 chat 等页且全部数据接口 401，历史上有"数据看似
    // 全消失"的回归——根因即此处此前不处理 401）
    if (resp.status === 401 && !opts.public) {
      clearAuth()
      if (!window.location.hash.includes('/login')) {
        window.location.hash = '#/login'
      }
    }
    let detail = `请求失败 (${resp.status})`
    try {
      const data = await resp.json()
      if (data?.detail) detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    } catch {
      /* 非 JSON 错误体，忽略 */
    }
    throw new ApiError(resp.status, detail)
  }
  if (opts.raw) return (await resp.text()) as unknown as T
  if (resp.status === 204) return undefined as T
  return (await resp.json()) as T
}

export const api = {
  get: <T>(path: string, opts?: RequestOptions) => request<T>(path, { ...opts, method: 'GET' }),
  post: <T>(path: string, body?: unknown, opts?: RequestOptions) =>
    request<T>(path, { ...opts, method: 'POST', body }),
  put: <T>(path: string, body?: unknown, opts?: RequestOptions) =>
    request<T>(path, { ...opts, method: 'PUT', body }),
  del: <T>(path: string, opts?: RequestOptions) => request<T>(path, { ...opts, method: 'DELETE' }),
}

/* ── 认证 ─────────────────────────────────────────────── */

export interface LoginUser {
  id: string
  username: string
  name: string
  role: string
  /** 中文显示名（阶段 5.1 起后端下发） */
  role_label?: string
  /** 能力清单，形如 "question:create"（阶段 5.1 起后端下发） */
  permissions?: string[]
  /** 能看到的教师端菜单 key，顺序由后端定（阶段 5.1 起后端下发） */
  menus?: string[]
  school_id?: string
  class_ids?: string[]
  teacher_id?: string
}

export interface LoginResponse {
  /** 登录失败时后端**仍返回 200**，靠这个字段区分 —— 见下面的登录守卫 */
  success?: boolean
  message?: string
  token: string | null
  refresh_token?: string
  user: LoginUser | null
}

/* ── 能力清单（阶段 5.2）─────────────────────────────────────
   后端在 login / refresh / /me 三处下发；这里只负责**存**与**读**。
   存下来是为了刷新页面不用重新登录；读出来供菜单过滤与路由守卫用。

   ⚠️ 这不是安全边界 —— 真正的边界在后端端点。这里写错只会让人看到点不动的菜单。 */

export interface Capabilities {
  role: string
  role_label: string
  permissions: string[]
  menus: string[]
}

const EMPTY_CAPS: Capabilities = { role: '', role_label: '', permissions: [], menus: [] }

export function getCaps(): Capabilities | null {
  try {
    const raw = localStorage.getItem(CAPS_KEY)
    if (!raw) return null
    const c = JSON.parse(raw)
    // 形状校验：坏数据当作「没有」，让调用方去 /me 重新水合，而不是让页面崩在 undefined 上
    if (!c || typeof c.role !== 'string' || !Array.isArray(c.menus) || !Array.isArray(c.permissions)) {
      return null
    }
    return c as Capabilities
  } catch {
    return null
  }
}

export function setCaps(user: LoginUser): Capabilities {
  const caps: Capabilities = {
    role: user.role || '',
    role_label: user.role_label || user.role || '',
    permissions: user.permissions || [],
    menus: user.menus || [],
  }
  localStorage.setItem(CAPS_KEY, JSON.stringify(caps))
  return caps
}

/** 该角色是否有某能力（按钮级判断用），形如 `can('exam:delete')`。 */
export function can(permission: string): boolean {
  return (getCaps() || EMPTY_CAPS).permissions.includes(permission)
}

/** 该角色是否能看到某菜单（路由守卫用）。 */
export function hasMenu(key: string): boolean {
  return (getCaps() || EMPTY_CAPS).menus.includes(key)
}

/** 从 `/me` 拉一次能力清单并落库 —— 有 token 但本地没有能力清单时用（老会话、清了缓存）。 */
export async function fetchCaps(): Promise<Capabilities> {
  const body = await api.get<{ success: boolean; user: LoginUser | null }>('/api/auth/me')
  if (!body?.user) throw new ApiError(401, '未登录')
  return setCaps(body.user)
}

/** 登录成功后的会话 —— `user` / `token` 一定存在（失败会抛异常，不会返回半个会话）。 */
export interface LoginSession extends LoginResponse {
  user: LoginUser
  token: string
}

export async function login(username: string, password: string): Promise<LoginSession> {
  const data = await api.post<LoginResponse>('/api/auth/login', { username, password }, { public: true })

  // ⚠️ 后端**登录失败也返回 200**（`{success: false, message, user: null}`），
  // 不走 `!resp.ok` 那条错误分支，所以这里必须自己判。
  // 此前直接 `data.user.teacher_id` —— 任何一次失败登录（密码错 / 账号被禁用 /
  // 账号不存在）都会把页面崩成 "Cannot read properties of null"，
  // 而不是告诉用户「用户名或密码错误」。
  if (!data?.success || !data.user || !data.token) {
    throw new ApiError(401, data?.message || '登录失败')
  }

  const { user, token } = data          // 已收窄，调用方不必再判空

  setToken(token)
  setCaps(user)
  const teacherId = user.teacher_id || user.id || (user.username === username ? user.id : '')
  if (teacherId) localStorage.setItem(TEACHER_ID_KEY, teacherId)
  return { ...data, user, token }
}

/* mobile-auth.ts — 学生/家长端会话（ADR-0001 并入 SPA 后统一走 api 客户端 token，
 * 用户画像沿用旧前端 sessionStorage['chemai_user'] 键（e2e 兼容）） */

import { setToken, clearAuth } from './api'

export interface MobileUser {
  id: string
  username?: string
  name?: string
  role?: string
  class_name?: string
  class_id?: string
  school?: string
  bind_code?: string
}

const USER_KEY = 'chemai_user'

export function getMobileUser(): MobileUser | null {
  try {
    const raw = sessionStorage.getItem(USER_KEY)
    return raw ? (JSON.parse(raw) as MobileUser) : null
  } catch {
    return null
  }
}

export function setMobileSession(token: string, user: MobileUser): void {
  setToken(token)
  sessionStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function clearMobileSession(): void {
  clearAuth()
  sessionStorage.removeItem(USER_KEY)
  sessionStorage.removeItem('chemai_student_cid')
  sessionStorage.removeItem('chemai_parent_cid')
}

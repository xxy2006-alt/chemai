import { useEffect, useState } from 'react'
import { ApiError, type Capabilities, clearAuth, fetchCaps, getCaps, getToken } from './api'

interface State {
  caps: Capabilities | null
  loading: boolean
}

/**
 * 当前登录者的能力清单（阶段 5.2）。
 *
 * 优先用本地缓存的 —— 刷新页面不用重新登录。本地没有、但**有 token** 时拉一次
 * `/api/auth/me`：这样「阶段 5 之前登录的老会话」和「清了 localStorage 但 token 还在」
 * 都能自愈，不用让用户重登。
 *
 * `caps` 为 null 表示「没登录或拿不到」→ 调用方弹回登录页；
 * `caps.menus` 为空数组表示「登录了但没有教师端权限」（学生/家长）→ 显示无权限页。
 * 两者是不同的状态，别合并。
 */
export function useCapabilities(): State {
  const [state, setState] = useState<State>(() => ({
    caps: getCaps(),
    loading: !getCaps() && !!getToken(),
  }))

  useEffect(() => {
    if (getCaps() || !getToken()) return
    let alive = true
    fetchCaps()
      .then((caps) => {
        if (alive) setState({ caps, loading: false })
      })
      .catch((err) => {
        if (!alive) return
        // token 失效 → 清干净，交给路由弹回登录页（不要留个半死状态）
        if (err instanceof ApiError && err.status === 401) clearAuth()
        setState({ caps: null, loading: false })
      })
    return () => {
      alive = false
    }
  }, [])

  return state
}

/* 401 统一拦截回归：token 失效必须清本地凭证并跳回登录页。
 * 背景：服务重启/token 过期后，页面停留在 chat 等页且全部数据接口 401，
 * 历史上有"数据看似全消失"的回归（根因：此前不处理 401，不登出不跳转）。 */
import { beforeEach, describe, expect, it, vi } from 'vitest'

const fetchMock = vi.fn()

vi.stubGlobal('fetch', fetchMock)

import { api, ApiError, clearAuth, setToken } from '../src/lib/api'

function locationHash(): string {
  return window.location.hash
}

describe('api 401 拦截', () => {
  beforeEach(() => {
    fetchMock.mockReset()
    localStorage.clear()
    window.location.hash = ''
  })

  it('401 时清除本地凭证并跳转 #/login', async () => {
    setToken('expired-token')
    fetchMock.mockResolvedValueOnce(new Response('{"detail":"Not authenticated"}', { status: 401 }))

    const err = await api.get('/api/classes').catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err.status).toBe(401)
    expect(localStorage.getItem('token')).toBeNull()
    expect(locationHash()).toBe('#/login')
  })

  it('public 接口的 401 不清除凭证、不跳转（避免登录页循环）', async () => {
    setToken('keep-me')
    fetchMock.mockResolvedValueOnce(new Response('{"detail":"Not authenticated"}', { status: 401 }))

    await api.get('/api/some-public', { public: true }).catch(() => undefined)
    expect(localStorage.getItem('token')).toBe('keep-me')
    expect(locationHash()).not.toBe('#/login')
  })

  it('clearAuth 清空 token/teacher_id/caps', () => {
    setToken('t')
    localStorage.setItem('teacher_id', 'teacher_zhou')
    localStorage.setItem('chemai_caps', 'x')
    clearAuth()
    expect(localStorage.getItem('token')).toBeNull()
    expect(localStorage.getItem('teacher_id')).toBeNull()
    expect(localStorage.getItem('chemai_caps')).toBeNull()
  })
})

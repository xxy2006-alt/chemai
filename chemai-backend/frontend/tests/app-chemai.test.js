// app.js — window.ChemAI 测试
// IIFE 加载时会检查 sessionStorage 登录态，无用户则跳转 login 且不挂载 ChemAI，
// 所以必须在 import 前用 vi.hoisted 预置 sessionStorage + fetch stub。
import { describe, it, expect, beforeEach, afterEach } from 'vitest'

const { fetchCalls } = vi.hoisted(() => {
  const calls = []
  globalThis.fetch = (url, opts) => {
    calls.push({ url, opts: opts || {} })
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) })
  }
  sessionStorage.setItem('chemai_user', JSON.stringify({ name: '海老师', token: 'tok-123', school: '市第一中学' }))
  return { fetchCalls: calls }
})

await import('../legacy/teacher/app.js')

describe('ChemAI 用户信息', () => {
  it('getUser 从 sessionStorage 解析用户', () => {
    const u = window.ChemAI.getUser()
    expect(u.name).toBe('海老师')
    expect(u.token).toBe('tok-123')
  })

  it('getToken 返回 token', () => {
    expect(window.ChemAI.getToken()).toBe('tok-123')
  })

  it('无用户时 getUser 返回 null', () => {
    sessionStorage.removeItem('chemai_user')
    expect(window.ChemAI.getUser()).toBeNull()
    expect(window.ChemAI.getToken()).toBe('')
  })
})

describe('ChemAI trackActivity', () => {
  beforeEach(() => sessionStorage.removeItem('chemai_activities'))

  it('记录活动并写回 sessionStorage', () => {
    window.ChemAI.trackActivity('chat', '问了反应方程式')
    const acts = JSON.parse(sessionStorage.getItem('chemai_activities'))
    expect(acts.length).toBe(1)
    expect(acts[0].type).toBe('chat')
    expect(acts[0].summary).toBe('问了反应方程式')
    expect(typeof acts[0].time).toBe('string')
  })

  it('最多保留 5 条', () => {
    for (let i = 1; i <= 7; i++) window.ChemAI.trackActivity('chat', 'a' + i)
    const acts = JSON.parse(sessionStorage.getItem('chemai_activities'))
    expect(acts.length).toBe(5)
    expect(acts[0].summary).toBe('a7')
  })
})

describe('ChemAI fetch token 注入', () => {
  beforeEach(() => {
    // 上一条用例删过 chemai_user，这里重新种回
    sessionStorage.setItem('chemai_user', JSON.stringify({ name: '海老师', token: 'tok-123', school: '市第一中学' }))
  })

  it('/api/ 请求自动加 Authorization 头', async () => {
    const res = await window.fetch('/api/classes', { headers: {} })
    expect(res.ok).toBe(true)
    const call = fetchCalls.find(c => c.url === '/api/classes')
    expect(call.opts.headers.Authorization).toBe('Bearer tok-123')
  })

  it('非 /api/ 请求不加 Authorization', async () => {
    await window.fetch('/login.html')
    const call = fetchCalls.find(c => c.url === '/login.html')
    expect(call.opts.headers?.Authorization).toBeUndefined()
  })

  it('已有 Authorization 头时不覆盖', async () => {
    await window.fetch('/api/x', { headers: { Authorization: 'Bearer manual' } })
    const call = fetchCalls.find(c => c.url === '/api/x')
    expect(call.opts.headers.Authorization).toBe('Bearer manual')
  })
})

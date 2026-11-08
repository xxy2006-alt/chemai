/* use-live-timer.test.tsx — 旧版 live-timer 计时器回归测试（evals）
 * 流式期间每 100ms 递增（1 位小数秒），停止归零。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { useLiveTimer } from '../src/lib/use-live-timer'

describe('useLiveTimer（旧版 Agent 状态计时器）', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('running=true 时每 100ms 递增，1 位小数秒', () => {
    const { result } = renderHook(() => useLiveTimer(true))
    expect(result.current).toBe(0)
    act(() => vi.advanceTimersByTime(350))
    expect(result.current).toBeGreaterThanOrEqual(0.3)
    expect(result.current).toBeLessThan(0.5)
    act(() => vi.advanceTimersByTime(700))
    expect(result.current).toBeGreaterThanOrEqual(1.0)
    expect(result.current).toBeLessThan(1.1)
  })

  it('running 变 false 归零并停止', () => {
    const { result, rerender } = renderHook(({ running }) => useLiveTimer(running), {
      initialProps: { running: true },
    })
    act(() => vi.advanceTimersByTime(500))
    expect(result.current).toBeGreaterThan(0.4)
    rerender({ running: false })
    expect(result.current).toBe(0)
    act(() => vi.advanceTimersByTime(1000))
    expect(result.current).toBe(0)
  })

  it('重新开始（false→true）时从 0 重新计时', () => {
    const { result, rerender } = renderHook(({ running }) => useLiveTimer(running), {
      initialProps: { running: false },
    })
    rerender({ running: true })
    act(() => vi.advanceTimersByTime(200))
    expect(result.current).toBeGreaterThanOrEqual(0.1)
    expect(result.current).toBeLessThan(0.4)
  })
})

/* use-live-timer.ts — 旧版 live-timer 计时器移植
 * 旧行为：思考状态旁注入 <span class="live-timer ticking">0.0s</span>，
 * 每 100ms 更新一次、1 位小数秒。 */

import { useEffect, useRef, useState } from 'react'

/** running 为 true 时每 100ms 递增返回秒数（1 位小数精度），停止时归零 */
export function useLiveTimer(running: boolean): number {
  const [sec, setSec] = useState(0)
  const t0 = useRef(0)

  useEffect(() => {
    if (running) {
      t0.current = Date.now()
      setSec(0)
      const iv = window.setInterval(() => setSec((Date.now() - t0.current) / 1000), 100)
      return () => window.clearInterval(iv)
    }
    setSec(0)
  }, [running])

  return sec
}

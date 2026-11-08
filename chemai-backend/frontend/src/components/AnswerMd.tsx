/* AnswerMd.tsx — 答案展示组件（KaTeX 公式渲染）
 * 2026-08-14 用户反馈：有机题答案里 $CH_3COOH$、\xrightarrow{{浓硫酸}} 等
 * 公式显示为原始源码 → 答案必须走 ChemMd 渲染。全站答案展示共用。 */

import { ChemMd } from './ChemMd'

export function AnswerMd({ text, className = '' }: { text: string; className?: string }) {
  if (!text) return null
  return (
    <div className={`flex items-start gap-1.5 ${className}`}>
      <span className="shrink-0 mt-0.5 inline-flex items-center rounded-[var(--radius-full)] font-medium whitespace-nowrap text-[11px] px-2 py-0.5 gap-1 bg-teal-soft text-teal">
        答案
      </span>
      <div className="min-w-0 flex-1">
        <ChemMd text={text} />
      </div>
    </div>
  )
}

/* OptionsRow.tsx — 选项展示组件（KaTeX 公式渲染）
 * 2026-08-14 用户反馈：选项里的 $CH_3COOH$ 等公式显示为原始源码。
 * 逐项 ChemMd 渲染（行内公式），flex 换行排列。 */

import { ChemMd } from './ChemMd'

export function OptionsRow({
  options,
  className = '',
}: {
  options?: string[] | string
  className?: string
}) {
  const opts = Array.isArray(options)
    ? options
    : typeof options === 'string'
      ? options
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean)
      : []
  if (!opts.length) return null
  return (
    <div className={`flex flex-wrap gap-x-5 gap-y-1 ${className}`}>
      {opts.map((o, i) => (
        <div key={i} className="min-w-0">
          <ChemMd text={o} />
        </div>
      ))}
    </div>
  )
}

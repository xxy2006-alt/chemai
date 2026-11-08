/* ChemMd.tsx — 共享化学 Markdown 渲染组件（KaTeX + 图片 + 表格），
 * AI 气泡与题目内容共用，避免样式类名散落。 */

import { renderChemMD } from '../lib/chem-markdown'

const MD_CLASSES = [
  'chem-md',
  'text-[14px] leading-relaxed text-ink',
  '[&_table]:w-full [&_table]:text-[13px] [&_table]:border-collapse',
  '[&_th]:text-left [&_th]:font-medium [&_th]:text-ink-muted [&_th]:py-1.5 [&_th]:border-b [&_th]:border-border',
  '[&_td]:py-1.5 [&_td]:border-b [&_td]:border-border/60',
  '[&_pre]:bg-surface-muted [&_pre]:rounded-[var(--radius-sm)] [&_pre]:p-3 [&_pre]:overflow-x-auto',
  '[&_code]:font-mono',
  '[&_blockquote]:border-l-2 [&_blockquote]:border-teal [&_blockquote]:pl-3 [&_blockquote]:text-ink-secondary [&_blockquote]:italic',
  '[&_hr]:border-border [&_strong]:font-semibold',
  '[&_h1]:text-lg [&_h2]:text-base [&_h3]:text-[15px] [&_h1],\\[&_h2],\\[&_h3]:font-semibold [&_h1],\\[&_h2],\\[&_h3]:mt-3 [&_h1],\\[&_h2],\\[&_h3]:mb-1',
  '[&_ul]:pl-4 [&_ol]:pl-4 [&_li]:my-0.5',
  '[&_p]:my-1 [&_p]:first:mt-0 [&_p]:last:mb-0',
  '[&_img]:max-w-full [&_img]:rounded-[var(--radius-sm)] [&_img]:my-2 [&_img]:block [&_img]:mx-auto',
].join(' ')

export function ChemMd({ text, className = '' }: { text: string; className?: string }) {
  return (
    <div
      className={`${MD_CLASSES} ${className}`}
      dangerouslySetInnerHTML={{ __html: renderChemMD(text) }}
    />
  )
}

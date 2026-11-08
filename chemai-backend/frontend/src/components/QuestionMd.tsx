/* QuestionMd.tsx — 题目内容渲染组件：ChemMd + 配图位置整理
 * 存量真题数据中配图常被格式化到解析/解答之后（题目底部），
 * 显示前统一把配图移到题干之后（reorganizeQuestionImages，见 exam-utils）。
 * 全站题目展示共用，避免各页面散落处理。 */

import { reorganizeQuestionImages } from '../lib/exam-utils'
import { ChemMd } from './ChemMd'

export function QuestionMd({ text, className }: { text: string; className?: string }) {
  return <ChemMd text={reorganizeQuestionImages(text)} className={className} />
}

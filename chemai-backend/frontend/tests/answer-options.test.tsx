/* answer-options.test.tsx — 答案/选项 KaTeX 公式渲染（evals）
 * 回归用户反馈：「生成有机化学的题就这样？答案: A:$CH_3COOH$ B:...」——
 * 答案与选项里的 LaTeX 公式必须以 KaTeX 渲染，不得显示原始 $...$ 源码。 */

import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import { AnswerMd } from '../src/components/AnswerMd'
import { OptionsRow } from '../src/components/OptionsRow'

describe('AnswerMd：答案公式 KaTeX 渲染', () => {
  it('答案含 $CH_3COOH$ → 渲染为 KaTeX（无原始 $ 源码）', () => {
    const { container } = render(<AnswerMd text="A：$CH_3COOH$ 与 $C_2H_5OH$ 酯化" />)
    expect(container.textContent).toContain('答案')
    // KaTeX 渲染产物：span.katex 出现，且不含裸 $CH_3COOH$ 文本
    expect(container.querySelectorAll('.katex').length).toBeGreaterThan(0)
    expect(container.textContent).not.toContain('$CH_3COOH$')
    expect(container.textContent).toContain('CH')
  })

  it('答案含 \\xrightarrow{浓硫酸} → KaTeX 渲染不报错', () => {
    const { container } = render(
      <AnswerMd text="$CH_3COOH + C_2H_5OH \\xrightarrow{{浓硫酸}} CH_3COOC_2H_5 + H_2O$" />,
    )
    expect(container.querySelectorAll('.katex').length).toBeGreaterThan(0)
    expect(container.querySelectorAll('.katex-error').length).toBe(0)
    expect(container.textContent).not.toContain('\\xrightarrow')
  })

  it('空答案 → 不渲染', () => {
    const { container } = render(<AnswerMd text="" />)
    expect(container.innerHTML).toBe('')
  })
})

describe('OptionsRow：选项公式 KaTeX 渲染', () => {
  it('选项数组逐项渲染公式，无原始 $ 源码', () => {
    const { container } = render(
      <OptionsRow options={['A. $CH_3COOH$', 'B. $CH_3COOC_2H_5$', 'C. $C_2H_5OH$']} />,
    )
    expect(container.querySelectorAll('.katex').length).toBeGreaterThanOrEqual(3)
    expect(container.textContent).not.toContain('$CH_3COOH$')
    expect(container.textContent).toContain('A.')
  })

  it('字符串选项（逗号分隔）也渲染', () => {
    const { container } = render(<OptionsRow options="A. $H_2O$, B. $CO_2$" />)
    expect(container.querySelectorAll('.katex').length).toBeGreaterThanOrEqual(2)
    expect(container.textContent).toContain('B.')
  })

  it('无选项 → 不渲染', () => {
    const { container } = render(<OptionsRow options={undefined} />)
    expect(container.innerHTML).toBe('')
  })
})

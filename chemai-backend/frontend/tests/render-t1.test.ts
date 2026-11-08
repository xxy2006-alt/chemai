/* render-t1.test.ts — 2020 全国卷 T1 渲染回归（evals）：
 * 双版本问题根因 = KaTeX CSS 缺失导致 MathML 可见；此处锁定内容层：
 * 选项 A/B/C/D 换行、公式单版本、cleanLatex 不破坏公式 */
import { describe, expect, it } from 'vitest'
import { renderChemMD, cleanLatex } from '../src/lib/chem-markdown'

const T1 = '国家卫健委公布的新型冠状病毒肺炎诊疗方案指出，乙醚、 $7 5 \\% Z$ 醇、含氯消毒剂、过氧乙酸 $\\mathrm { ( C H _ { 3 } C O O O H ) }$ ）、氯仿等均可有效灭活病毒。对于上述化学药品，下列说法错误的是（　　）A $\\mathrm { C H } _ { 3 } \\mathrm { C H } _ { 2 } \\mathrm { O H }$ 能与水互溶B $\\mathrm { N a C l O }$ 通过氧化灭活病毒C．过氧乙酸相对分子质量为76D．氯仿的化学名称是四氯化碳'

describe('T1 内容层回归', () => {
  it('选项 A/B/C/D 换行（互溶B$ → 互溶\\nB$）', () => {
    const cleaned = cleanLatex(T1)
    expect(cleaned).toContain('互溶\nB ')
    expect(cleaned).toContain('毒\nC．')
    expect(cleaned).toContain('76\nD．')
    // 选项 A 前是（　　）全角括号也应换行
    expect(cleaned).toContain('）\nA ')
  })

  it('数学公式内 "AB$" 不被误换行', () => {
    expect(cleanLatex('$AB$ 是物质')).toBe('$AB$ 是物质')
    expect(cleanLatex('$NaClO$ 通过氧化')).toBe('$NaClO$ 通过氧化')
  })

  it('渲染后无 katex-error', () => {
    const out = renderChemMD(T1)
    expect(out).not.toContain('katex-error')
  })

  it('cleanLatex 公式单版本（75%、CH₃COOOH）', () => {
    const cleaned = cleanLatex(T1)
    expect(cleaned).toContain('$75\\%$')
    expect(cleaned).toContain('$\\mathrm{(CH_{3}COOOH)}$')
    expect(cleaned).not.toContain('C H')
    expect(cleaned).not.toContain('7 5')
  })
})

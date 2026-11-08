/* chem-markdown-ts.test.ts — 题目内容渲染回归测试（evals）
 * 用户反馈：真题内容的 LaTeX 公式与图片被以纯文本渲染；全卷 LaTeX 带 OCR 垃圾。
 * 修复后：$...$/$$...$$/\ce{} 走 KaTeX，![...](...) 转 <img>，cleanLatex 清洗导入垃圾。 */
import { describe, expect, it } from 'vitest'
import { cleanLatex, renderChemMD } from '../src/lib/chem-markdown'

describe('renderChemMD（TS 版）题目内容渲染', () => {
  it('真题中的 $...$ LaTeX 渲染为 KaTeX', () => {
    const out = renderChemMD('相对分子质量为 $12 \\times 2 + 4 + 16 \\times 3 = 76$，故 C 正确')
    expect(out).toContain('katex')
    expect(out).not.toContain('$12')
  })

  it('真题中的 \\mathrm{...} 公式渲染为 KaTeX', () => {
    const out = renderChemMD('过氧乙酸 $\\mathrm{(CH_3COOH)}$ 可灭活病毒')
    expect(out).toContain('katex')
    // katex 的 MathML annotation 会保留原始源码，属正常行为；关键是渲染成功无错误
    expect(out).not.toContain('katex-error')
  })

  it('markdown 图片语法 ![..](url) 转 <img>（用户反馈回归）', () => {
    const out = renderChemMD('![](/static/figures/全国卷/2020/figures/633625df.jpg)')
    expect(out).toContain('<img')
    expect(out).toContain('/static/figures/全国卷/2020/figures/633625df.jpg')
    expect(out).not.toContain('![')
  })

  it('用户提供的 2020 全国卷真题样例：公式与图片同时正确', () => {
    const sample =
      '#T1 国家卫健委公布指出，乙醚、$75\\%$ 乙醇、含氯消毒剂、过氧乙酸 $\\mathrm{(CH_3COOH)}$ 均可有效灭活病毒。A $\\mathrm{CH_3CH_2OH}$ 能与水互溶 B $\\mathrm{NaClO}$ 通过氧化灭活病毒 ![](/static/figures/全国卷/2020/figures/633625dfe5370c0abe9543cb785143ecf0a61e149e01701d1c13bc5f328ecabf.jpg)'
    const out = renderChemMD(sample)
    expect(out).toContain('katex')
    expect(out).toContain('<img')
    expect(out).not.toContain('katex-error')
    expect(out).not.toContain('![')
  })

  it('\\ce{} 化学式渲染', () => {
    const out = renderChemMD('反应为 \\ce{Fe2O3 + 3CO -> 2Fe + 3CO2}')
    expect(out).toContain('katex')
  })

  it('纯文本题目原样保留', () => {
    const out = renderChemMD('下列关于氯气的说法正确的是（　　）')
    expect(out).toContain('下列关于氯气的说法正确的是')
  })
})

describe('cleanLatex（导入管线 OCR 垃圾清洗，2026 全卷数据质量修复）', () => {
  it('\\mathrm 组内空格归一：\\mathrm { C H } _ { 3 } \\mathrm { C O I } → \\mathrm{CH}_{3}\\mathrm{COI}', () => {
    expect(cleanLatex('$\\mathrm { C H } _ { 3 } \\mathrm { C O I }$')).toBe('$\\mathrm{CH}_{3}\\mathrm{COI}$')
  })

  it('下标含花括号带空格：\\mathrm { C H _ { 3 } C O I } → \\mathrm{CH_{3}COI}', () => {
    expect(cleanLatex('$\\mathrm { C H _ { 3 } C O I }$')).toBe('$\\mathrm{CH_{3}COI}$')
  })

  it('OCR 将下标误识为 \\Omega：(Rh(CO)Ω₂I₂ → (Rh(CO)₂I₂', () => {
    expect(cleanLatex('$\\mathrm { ( R h ~ ( C O ) ~ \\Omega _ { 2 } I _ { 2 } ] }$')).toBe(
      '$\\mathrm{(Rh~(CO)~_{2}I_{2}]}$',
    )
  })

  it('<sup>﹏</sup> 垃圾移除', () => {
    expect(cleanLatex(`可催化甲醇羰基化<sup>${'\ufe63'}</sup>反应`)).toBe('可催化甲醇羰基化反应')
  })

  it('\\textcircled{N} → 圈号数字', () => {
    expect(cleanLatex('$\\textcircled { 1 } \\mathrm { C H } _ { 3 } \\mathrm { O H }$')).toBe(
      '$①\\mathrm{CH}_{3}\\mathrm{OH}$',
    )
  })

  it('花括号运算符 { = } → =；孤立 $_ 移除', () => {
    expect(cleanLatex('$\\mathrm { H I } { = } \\mathrm { H I }$')).toBe('$\\mathrm{HI}=\\mathrm{HI}$')
    expect(cleanLatex('$_ \\mathrm { H I + H _ { 2 } O }$')).toBe('$\\mathrm{HI+H_{2}O}$')
  })

  it('数学段内多余空白（75%Z 乙醇 → 75% 乙醇）', () => {
    expect(cleanLatex('乙醚、 $7 5 \\% Z$ 醇、含氯消毒剂')).toBe('乙醚、 $75\\%$ 醇、含氯消毒剂')
  })

  it('真实题干样例：铑的配合物离子整段清洗后可渲染', () => {
    const stem =
      '铑的配合物离子 $\\mathrm { ( R h ~ ( C O ) ~ \\Omega _ { 2 } I _ { 2 } ] }$ <sup>﹏</sup>可催化甲醇羰基化'
    const out = renderChemMD(stem)
    expect(out).toContain('katex')
    expect(out).not.toContain('katex-error')
    expect(out).not.toContain('\\Omega')
  })

  it('真实解答样例：生成 CH3COI 公式清洗后渲染', () => {
    const ans =
      '生成 $\\mathrm { C H _ { 3 } C O I } , \\mathrm { C H _ { 3 } C O I }$ 继续与 $\\mathrm { H } _ { 2 } \\mathrm { O }$ 反应生成 HI 和 $\\mathrm { C H _ { 3 } C O _ { 2 } H }$'
    const out = renderChemMD(ans)
    expect(out).toContain('katex')
    expect(out).not.toContain('katex-error')
  })

  it('题目内嵌 HTML 表格透传（旧版 marked 行为）', () => {
    const out = renderChemMD('A．<td rowspan=1 colspan=1> $\\mathrm { N O }$ </td>B．选项')
    expect(out).toContain('<td')
    expect(out).not.toContain('&lt;td')
  })

  it('真实表格题（气体杂质 nat_2020_t3）A 单元格：\\ \\mathrm 不得变成逐字母 m a t h r m', () => {
    const src = '$\\mathrm { S O } _ { 2 } \\ \\mathrm { ( H } _ { 2 } \\mathrm { S ) }$'
    const cleaned = cleanLatex(src)
    expect(cleaned).toBe('$\\mathrm{SO}_{2}~\\mathrm{(H}_{2}\\mathrm{S)}$')
    const out = renderChemMD(src)
    expect(out).not.toContain('katex-error')
    // 回归：\\ 换行会把 \mathrm 的斜杠吃掉渲染成字母 m a t h r m（表现为 mspace newline）
    expect(out).not.toContain('mspace newline')
    expect(out).not.toContain('mathnormal">ma')
  })

  it('真实表格题 C 单元格：\\bf\\Gamma OCR 垃圾移除，渲染 N₂(O₂)', () => {
    const src = '${ \\bf N } _ { 2 } \\ { \\bf \\Gamma } ( { \\bf O } _ { 2 } )$'
    const cleaned = cleanLatex(src)
    expect(cleaned).toBe('${N}_{2}({O}_{2})$')
    const out = renderChemMD(src)
    expect(out).not.toContain('katex-error')
    expect(out).not.toContain('Gamma')
  })

  it('真实表格题 D 单元格：\\mathrm { N O } \\ \\mathrm { ~ ( N O } _ { 2 } ) 正常渲染', () => {
    const src = '$\\mathrm { N O } \\ \\mathrm { ~ ( N O } _ { 2 } )$'
    const out = renderChemMD(src)
    expect(out).not.toContain('katex-error')
    expect(cleanLatex(src)).toBe('$\\mathrm{NO}~\\mathrm{~(NO}_{2})$')
  })

  it('真实解答公式（nat_2020_t2）：14×2+2-8×2=14 单版本渲染', () => {
    const src = '$1 4 \\times 2 + 2 \\textmd { - } 8 \\times 2 = 1 4$'
    const out = renderChemMD(src)
    expect(out).not.toContain('katex-error')
  })

  it('真实分子式（nat_2020_t2）：C₁₄H₁₄O₄', () => {
    const src = '$\\mathrm { C _ { 1 4 } H _ { 1 4 } O _ { 4 } }$'
    expect(cleanLatex(src)).toBe('$\\mathrm{C_{14}H_{14}O_{4}}$')
    const out = renderChemMD(src)
    expect(out).not.toContain('katex-error')
  })

  it('\\Nu{0} OCR 误识 → NO', () => {
    expect(cleanLatex('$\\Nu { 0 } _ { 2 }$')).toBe('$NO_{2}$')
  })

  it('真实电极反应式（Zn-2e⁻+4OH⁻-Zn(OH)₄²⁻）：\\mathrm { - } 花括号不得被拆，^\\mathrm 错位修复', () => {
    const src = '$\\mathrm { Z n } - 2 \\mathbf { e } ^ { \\mathrm { - } } + 4 \\mathrm { O H } ^ { \\mathrm { - } } - \\mathrm { Z n } \\mathrm { ~ ( O H ) ~ } _ { 4 } ^ { 2 - }$'
    const cleaned = cleanLatex(src)
    expect(cleaned).toBe('$\\mathrm{Zn}-2\\mathbf{e}^{\\mathrm{-}}+4\\mathrm{OH}^{\\mathrm{-}}-\\mathrm{Zn}\\mathrm{~(OH)~}_{4}^{2-}$')
    const out = renderChemMD(src)
    expect(out).not.toContain('katex-error')
  })

  it('\\pH / \\pOH（LaTeX 无此命令）→ \\mathrm{pH} / \\mathrm{pOH}', () => {
    expect(cleanLatex('溶液的 \\pH = 1')).toBe('溶液的 \\mathrm{pH} = 1')
    expect(cleanLatex('$\\pOH$')).toBe('$\\mathrm{pOH}$')
    const out = renderChemMD('溶液的 \\pH = 1')
    expect(out).not.toContain('katex-error')
  })

  it('双反斜杠 OCR 垃圾（t4 ⑥ 方程式）：\\\\ = \\\\ → =，孤立 \\\\ 移除', () => {
    const src = '$$\\textcircled { 6 } \\mathrm { { C H } _ { 3 } \\mathrm { { C O I } + H _ { 2 } O \\\\ = \\\\ } }$$'
    const cleaned = cleanLatex(src)
    expect(cleaned).not.toContain('\\\\')
    expect(cleaned).toContain('=' )
    const out = renderChemMD(src)
    expect(out).not.toContain('katex-error')
  })

  it('<sub>/<sup> 上下标 HTML 透传（CH<sub>3</sub>I 渲染为下标）', () => {
    const out = renderChemMD('② +CH<sub>3</sub>I＝')
    expect(out).toContain('<sub>3</sub>')
    expect(out).not.toContain('&lt;sub&gt;')
  })

  it('存量损坏修复：\\r 回车符后接字母恢复为反斜杠（ightleftharpoons → \\rightleftharpoons）', () => {
    // 模拟 LLM JSON 未转义导致的存量坏数据：内容里 \r 变成了真正的回车符
    const src = `对于可逆反应 AX+B ${'\r'}ightleftharpoons C，平衡将如何变化？`
    const cleaned = cleanLatex(src)
    expect(cleaned).toContain('\\rightleftharpoons')
    const out = renderChemMD(cleaned)
    expect(out).not.toContain('katex-error')
    // 正常 CRLF 换行不受影响
    expect(cleanLatex('第一行\r\n第二行')).toBe('第一行\r\n第二行')
  })
})

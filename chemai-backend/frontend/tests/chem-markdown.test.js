// chem-markdown.js — window.renderChemMD 渲染测试
// 教师端/学生端/打印预览/在线做题共用的 Markdown+KaTeX 渲染器
import { describe, it, expect } from 'vitest'
import '../js/chem-markdown.js'

const render = (text) => window.renderChemMD(text)

describe('renderChemMD 化学渲染', () => {
  it('渲染 \\ce{} 化学式（mhchem）', () => {
    const out = render('水是 \\ce{H2O}')
    expect(out).toContain('katex')
    // mhchem 成功解析则无 katex-error；annotation 里保留原始 \ce 源码是 katex 正常行为
    expect(out).not.toContain('katex-error')
  })

  it('渲染 $...$ 行内公式', () => {
    const out = render('硫酸 $H_2SO_4$')
    expect(out).toContain('katex')
    expect(out).not.toContain('$')
  })

  it('渲染 $$...$$ 块级公式', () => {
    const out = render('反应：$$2H_2 + O_2 \\rightarrow 2H_2O$$')
    expect(out).toContain('katex')
  })

  it('空输入返回空串', () => {
    expect(render('')).toBe('')
    expect(render(null)).toBe('')
    expect(render(undefined)).toBe('')
  })
})

describe('renderChemMD Markdown', () => {
  it('渲染表格', () => {
    const out = render('| 物质 | 颜色 |\n|---|---|\n| CuO | 黑 |')
    expect(out).toContain('<table>')
    expect(out).toContain('<th>')
    expect(out).toContain('CuO')
  })

  it('渲染无序/有序列表', () => {
    expect(render('- 甲\n- 乙')).toContain('<ul>')
    expect(render('1. 甲\n2. 乙')).toContain('<ol>')
  })

  it('渲染标题', () => {
    expect(render('## 实验现象')).toContain('<h2>')
  })

  it('渲染引用块', () => {
    expect(render('> 注意安全')).toContain('<blockquote>')
  })

  it('渲染围栏代码块', () => {
    const out = render('```\n2H2 + O2 = 2H2O\n```')
    expect(out).toContain('<pre>')
    expect(out).toContain('<code>')
  })

  it('纯文本包成段落', () => {
    expect(render('这是一个普通题目')).toContain('<p>')
  })

  it('加粗与斜体', () => {
    expect(render('**重点**')).toContain('<strong>')
    expect(render('*斜体*')).toContain('<em>')
  })
})

describe('renderChemMD 图片与安全', () => {
  it('保留 <img> 结构图标签', () => {
    const out = render('结构如下 <img src="/static/question_images/abc.png">')
    expect(out).toContain('<img src="/static/question_images/abc.png">')
  })

  it('转义 <script> 等危险 HTML（XSS）', () => {
    const out = render('<script>alert(1)</script>')
    expect(out).not.toContain('<script>alert')
    expect(out).toContain('&lt;script&gt;')
  })

  it('转义 < 等尖括号', () => {
    const out = render('a < b 且 c > d')
    expect(out).toContain('&lt;')
    expect(out).toContain('&gt;')
  })
})

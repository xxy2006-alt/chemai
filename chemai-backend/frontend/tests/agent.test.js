// agent.js — window.renderChemistry 渲染 + 化学式实时预览（formatChemicalText）测试
// agent.js 是 IIFE：`window.ChemAI.startTimer` 直接赋值，需先定义 window.ChemAI；
// 化学式预览依赖 DOMContentLoaded 绑定 input 事件——readyState 已是 complete，
// 所以手动 dispatch DOMContentLoaded 触发绑定。
import { describe, it, expect, beforeEach } from 'vitest'
// marked v12+ 移除了 default export，必须具名导入
import { marked } from 'marked'

const { inputEl } = vi.hoisted(() => {
  window.ChemAI = window.ChemAI || {}
  const input = document.createElement('textarea')
  input.id = 'chat-input'
  const preview = document.createElement('div')
  preview.id = 'chem-preview'
  document.body.appendChild(input)
  document.body.appendChild(preview)
  return { inputEl: input }
})

await import('../legacy/teacher/js/agent.js')

globalThis.marked = marked
// 手动触发 DOMContentLoaded，让 agent.js 绑定 #chat-input 的 input 事件
document.dispatchEvent(new Event('DOMContentLoaded'))

describe('renderChemistry 渲染', () => {
  it('空输入返回空串', () => {
    expect(window.renderChemistry('')).toBe('')
  })

  it('转义危险 HTML', () => {
    const out = window.renderChemistry('<script>alert(1)</script>')
    expect(out).not.toContain('<script>alert')
    expect(out).toContain('&lt;script&gt;')
  })

  it('渲染 Markdown 加粗', () => {
    const out = window.renderChemistry('**重点**')
    expect(out).toContain('<strong>重点</strong>')
  })

  it('渲染 $...$ 行内公式', () => {
    const out = window.renderChemistry('硫酸 $H_2SO_4$')
    expect(out).toContain('katex')
  })

  it('\\ce{} 化学式走 mhchem（含下标）', () => {
    const out = window.renderChemistry('水是 \\ce{H2O}')
    expect(out).toContain('katex')
    // mhchem 把 H2O 渲染成带下标结构（<msub>）；若漏了 \ce 前缀只会渲染成普通数学 H2O
    expect(out).toContain('msub')
  })

  it('保留白名单 <img>（结构图），其余标签转义', () => {
    const out = window.renderChemistry('结构 <img src="/static/question_images/x.png"> <b>粗</b>')
    expect(out).toContain('<img src="/static/question_images/x.png">')
    expect(out).not.toContain('<b>')
    expect(out).toContain('&lt;b&gt;')
  })
})

describe('化学式实时预览 formatChemicalText', () => {
  const type = (text) => {
    inputEl.value = text
    inputEl.dispatchEvent(new Event('input'))
    return document.getElementById('chem-preview').textContent
  }

  it('元素下标：H2O → H₂O', () => {
    expect(type('H2O')).toBe('H₂O')
  })

  it('离子电荷：Fe3+ → Fe³⁺，Na+ → Na⁺', () => {
    expect(type('Fe3+')).toBe('Fe³⁺')
    expect(type('Na+')).toBe('Na⁺')
  })

  it('多元素电荷拆分：SO42- → SO₄²⁻', () => {
    expect(type('SO42-')).toBe('SO₄²⁻')
  })

  it('箭头：2H2O = 2H2 + O2 → 2H₂O → 2H₂ + O₂', () => {
    expect(type('2H2O = 2H2 + O2')).toBe('2H₂O → 2H₂ + O₂')
  })

  it('括号下标：Ca(OH)2 → Ca(OH)₂', () => {
    expect(type('Ca(OH)2')).toBe('Ca(OH)₂')
  })

  it('预览用 textContent 赋值，HTML 注入被中和', () => {
    // 前缀 H2O 触发格式化，但 <b> 原样保留——textContent 赋值使其不成为真实元素
    expect(type('H2O <b>x</b>')).toBe('H₂O <b>x</b>')
    expect(document.querySelector('#chem-preview b')).toBeNull()
  })
})

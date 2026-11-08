import { describe, expect, it } from 'vitest'
import { formatChemicalText } from '../src/lib/chem-format'

describe('formatChemicalText 化学式实时预览（旧版 agent.js 移植）', () => {
  it('单元素电荷：Fe3+ → Fe³⁺', () => {
    expect(formatChemicalText('Fe3+')).toBe('Fe³⁺')
  })

  it('多元素下标+电荷：SO42- → SO₄²⁻', () => {
    expect(formatChemicalText('SO42-')).toBe('SO₄²⁻')
  })

  it('下标+电荷：NH4+ → NH₄⁺', () => {
    expect(formatChemicalText('NH4+')).toBe('NH₄⁺')
  })

  it('元素直接电荷：Na+ → Na⁺', () => {
    expect(formatChemicalText('Na+')).toBe('Na⁺')
  })

  it('纯下标：H2O → H₂O', () => {
    expect(formatChemicalText('H2O')).toBe('H₂O')
  })

  it('括号下标：(OH)3 → (OH)₃', () => {
    expect(formatChemicalText('(OH)3')).toBe('(OH)₃')
  })

  it('等号转箭头：CuO + H2 = Cu + H2O', () => {
    expect(formatChemicalText('CuO + H2 = Cu + H2O')).toBe('CuO + H₂ → Cu + H₂O')
  })

  it('普通文本不变（不触发预览）', () => {
    const t = '请讲解盐类水解'
    expect(formatChemicalText(t)).toBe(t)
  })
})

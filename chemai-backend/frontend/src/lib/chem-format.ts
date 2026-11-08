/* chem-format.ts — legacy/teacher/js/agent.js formatChemicalText 的 TS 移植
 * 输入化学式文本，输出 Unicode 上下标预览（Fe3+ → Fe³⁺，SO42- → SO₄²⁻） */

const SUB: Record<string, string> = {
  '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
  '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉',
}
const SUP: Record<string, string> = {
  '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
  '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
}

function subDigits(s: string): string {
  let r = ''
  for (const c of s) r += SUB[c] ?? c
  return r
}

function superDigits(s: string): string {
  let r = ''
  for (const c of s) r += SUP[c] ?? c
  return r
}

export function formatChemicalText(text: string): string {
  let result = ''
  let i = 0
  let elemCount = 0
  const t = text.replace(/-->/g, '→').replace(/->/g, '→')

  const resetWord = () => {
    elemCount = 0
  }

  while (i < t.length) {
    const ch = t[i]

    // = between words → arrow
    if (ch === '=' && (i === 0 || t[i - 1] === ' ') && (i + 1 >= t.length || t[i + 1] === ' ')) {
      result += '→'
      i++
      resetWord()
      continue
    }
    // + or - preceded by space → separator (not charge), reset word
    if ((ch === '+' || ch === '-') && (i === 0 || t[i - 1] === ' ')) {
      result += ch
      i++
      resetWord()
      continue
    }

    // Element symbol
    if (/[A-Z]/.test(ch)) {
      let elem = ch
      i++
      if (i < t.length && /[a-z]/.test(t[i])) {
        elem += t[i]
        i++
      }
      elemCount++

      // Digits after element
      if (i < t.length && /[0-9]/.test(t[i])) {
        let num = ''
        while (i < t.length && /[0-9]/.test(t[i])) {
          num += t[i]
          i++
        }
        // Followed by charge sign at end of compound?
        if (i < t.length && /[+-]/.test(t[i]) && (i + 1 >= t.length || /[\s+=→]/.test(t[i + 1]))) {
          const chargeSign = t[i]
          // Single element + short number → all charge: Fe3+ → Fe³⁺
          if (elemCount === 1 && parseInt(num) <= 3) {
            result += elem + superDigits(num) + (chargeSign === '+' ? '⁺' : '⁻')
            i++
            resetWord()
            continue
          }
          // Multi-element: last digit ≤3 → split into subscript + charge: SO42- → SO₄²⁻
          if (elemCount > 1 && num.length > 1 && parseInt(num[num.length - 1]) <= 3) {
            result += elem + subDigits(num.slice(0, -1)) + superDigits(num.slice(-1)) + (chargeSign === '+' ? '⁺' : '⁻')
            i++
            resetWord()
            continue
          }
          // Subscript + separate charge: MnO4- → MnO₄⁻, NH4+ → NH₄⁺
          result += elem + subDigits(num) + (chargeSign === '+' ? '⁺' : '⁻')
          i++
          resetWord()
          continue
        }
        result += elem + subDigits(num)
        continue
      }

      // Element directly + charge: Na+ → Na⁺
      if (i < t.length && /[+-]/.test(t[i]) && (i + 1 >= t.length || /[\s+=→]/.test(t[i + 1]))) {
        result += elem + (t[i] === '+' ? '⁺' : '⁻')
        i++
        resetWord()
        continue
      }
      result += elem
      continue
    }

    // Standalone number + charge: 2e-, 3+
    if (/[0-9]/.test(ch)) {
      let n = ''
      while (i < t.length && /[0-9]/.test(t[i])) {
        n += t[i]
        i++
      }
      if (i < t.length && /[+-]/.test(t[i]) && (i + 1 >= t.length || /[\s+=→]/.test(t[i + 1]))) {
        result += superDigits(n) + (t[i] === '+' ? '⁺' : '⁻')
        i++
        resetWord()
        continue
      }
      result += n
      continue
    }

    // ) + digits → )₃
    if (ch === ')' && i + 1 < t.length && /[0-9]/.test(t[i + 1])) {
      result += ')'
      i++
      let pn = ''
      while (i < t.length && /[0-9]/.test(t[i])) {
        pn += t[i]
        i++
      }
      result += subDigits(pn)
      continue
    }

    if (ch === ' ' || ch === '+' || ch === '→') resetWord()
    result += ch
    i++
  }
  return result
}

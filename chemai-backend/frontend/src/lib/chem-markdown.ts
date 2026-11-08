/* chem-markdown.ts — js/chem-markdown.js 的 TS 移植（教师端新应用专用）
 * 渲染逻辑与旧版完全一致：Markdown 子集 + KaTeX/mhchem 化学式 */

import katex from 'katex'
import 'katex/contrib/mhchem'

type LatexBlock = { t: 'd' | 'i' | 'c'; f: string }

function escHtml(s: string): string {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function renderInline(text: string): string {
  return escHtml(text)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
}

function splitTableRow(line: string): string[] {
  const parts = line.split('|')
  if (parts[0].trim() === '') parts.shift()
  if (parts.length && parts[parts.length - 1].trim() === '') parts.pop()
  return parts
}

function parseTable(lines: string[], startIdx: number): string {
  const headers = splitTableRow(lines[startIdx].trim())
  let html = '<table><thead><tr>'
  for (const h of headers) html += `<th>${renderInline(h.trim())}</th>`
  html += '</tr></thead><tbody>'
  let i = startIdx + 2
  while (i < lines.length && /^\|.*\|$/.test(lines[i].trim())) {
    const cells = splitTableRow(lines[i].trim())
    html += '<tr>'
    for (let c = 0; c < Math.min(cells.length, headers.length); c++) {
      html += `<td>${renderInline(cells[c].trim())}</td>`
    }
    html += '</tr>'
    i++
  }
  html += '</tbody></table>'
  return html
}

function katexRender(formula: string, displayMode: boolean): string {
  try {
    return katex.renderToString(formula, {
      throwOnError: false,
      displayMode,
      trust: true,
      strict: false,
    })
  } catch {
    return `<code>${escHtml(formula)}</code>`
  }
}

const CIRCLED = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳'

/** 清洗导入管线（OCR→LLM 格式化）产生的 LaTeX 垃圾（2026 数据质量修复，全卷生效）：
 *  \mathrm { C H } _ { 3 } 带空格 → \mathrm{CH}_{3}；{ = } → =；\textcircled{1} → ①；
 *  <sup>﹏</sup> 移除；$_ 多余下标标记；OCR 将下标误识为 \Omega/\Gamma/\Nu；
 *  \bf 加粗装饰标记移除；\\(反斜杠空格) → ~（避免被后续空格清理破坏成 \\ 换行）；
 *  数学段内多余空白；"\%Z" OCR 垃圾（75%Z乙醇 → 75%乙醇）。 */
export function cleanLatex(text: string): string {
  return text
    // 0. 选项标记换行：ABCD 选项黏在一起时（"互溶B．NaClO"/"互溶B $NaClO$" → 换行）
    //    前置字符限中文/标点/数字，避免误伤数学公式内的 "AB$"（B 前是拉丁字母则不触发）
    .replace(/([\u4e00-\u9fff\u3000-\u303f\uff00-\uffef0-9])([A-D])([．、.]|\s\$)/g, '$1\n$2$3')
    // 0.5 存量损坏修复：LLM JSON 未转义 \rightleftharpoons 时 json.loads 把 \r 变回车符 →
    //    回车符后紧跟字母恢复为 \r（CR + "ightleftharpoons" → \rightleftharpoons）
    .replace(/\r(?=[a-zA-Z])/g, '\\r')
    // 1. <sup>﹏</sup>（U+FE63 小波浪横线）垃圾
    .replace(/<sup>\s*\ufe63\s*<\/sup>/g, '')
    // 2. OCR 垃圾组：\ { \bf ... } / \ { \Gamma ... } / \ { \Nu ... }（如 { \bf \Gamma } 误识的公式碎片）
    .replace(/\\\s*\{\s*[^{}]*?(?:\\bf|\\Gamma|\\Nu)[^{}]*?\s*\}/g, '')
    // 2.5 双反斜杠 \\（OCR 垃圾换行）："\\ = \\" → "="，孤立 \\ 移除（须在第 7 步前）
    .replace(/\\\\\s*([=+\-×÷→←])\s*\\\\/g, '$1')
    .replace(/\\\\/g, '')
    // 3. \bf / \Gamma 装饰与误识标记（\Gamma 在高中化学语料中为 OCR 垃圾）
    .replace(/\\bf\s*/g, '')
    .replace(/\\Gamma\s*/g, '')
    // 4. \Nu{0}（OCR 将 NO₂ 误识为希腊字母）→ NO；清空花括号组 {}
    .replace(/\\Nu\s*\{\s*0\s*\}/g, 'NO')
    .replace(/\{\s*\}/g, '')
    // 4.5 \pH / \pOH（LaTeX 无此命令，KaTeX 报错）→ \mathrm{pH} / \mathrm{pOH}
    .replace(/\\p[Hh](?![a-zA-Z])/g, '\\mathrm{pH}')
    .replace(/\\pOH(?![a-zA-Z])/g, '\\mathrm{pOH}')
    // 5. \textcircled{N} → ①②③…
    .replace(/\\textcircled\s*\{\s*(\d+)\s*\}/g, (_m, n: string) => CIRCLED[Number(n) - 1] || n)
    // 6. 归一 \mathrm/\mathbf/\mathsf/\operatorname 组内空白（~ 为数学空格原意，保留）
    .replace(
      /\\(mathrm|mathbf|mathsf|operatorname)\s*\{\s*([^{}]*?)\s*\}/g,
      (_m, cmd: string, inner: string) => `\\${cmd}{${inner.replace(/[ \t]+/g, '')}}`,
    )
    // 6.5 \mathrm 组内垃圾：空组含反斜杠 \mathrm { \ }、裸 \bar、\mathrm- 缺组
    .replace(/\\mathrm\s*\{\s*\\\s*\}/g, '')
    .replace(/\\mathrm\s*\{\s*\\bar\s*\}/g, '')
    .replace(/\\mathrm\s*([+\-])/g, '\\mathrm{$1}')
    // 6.6 单参 \stackrel{...} 垃圾（OCR 误识，缺第二参）
    .replace(/\\stackrel\s*\{\s*[^{}]*\s*\}(?!\s*\{)/g, '')
    // 7. 反斜杠空格 \  → ~（数学空格；避免被第 10 步删成 \\ 换行把 \mathrm 吃成 "mathrm" 字母）
    .replace(/\\(?=\s)/g, '~')
    // 8. OCR 将下标误识为 \Omega（仅当紧邻下标 2 时，如 (Rh(CO)Ω₂I₂ → (Rh(CO)₂I₂）
    .replace(/\\Omega\s*(?=_\s*\{?\s*2\s*\}?)/g, '')
    // 9. 带空格下标 _ { 3 } / _ 3 → _{3} / _3
    .replace(/_\s*\{\s*(\d+)\s*\}/g, '_{$1}')
    .replace(/_\s*(\d+)/g, '_$1')
    // 10. 花括号包裹运算符 { = } { + } { - }（排除命令组花括号，如 \mathrm{-} 的括号不得拆）
    .replace(/(?<![a-zA-Z])\{\s*([=+\-×÷→←])\s*\}/g, '$1')
    // 10.5 \mathrm 后紧跟 ^（OCR 错位）→ 移除 \mathrm
    .replace(/\\mathrm\s*(?=\^)/g, '')
    // 11. 孤立 $_（多余下标标记）
    .replace(/\$_/g, '$')
    // 12. 数学段内多余空白（数学模式忽略空格；"7 5" → "75"）
    .replace(/\$([^$\n]*)\$/g, (_m, inner: string) => `$${inner.replace(/[ \t]+/g, '')}$`)
    // 13. OCR 垃圾 Z：\%Z$ → \%$（"75%Z乙醇" 应为 "75%乙醇"）
    .replace(/(\\%)\s*Z(\s*\$)/g, '$1$2')
}

export function renderChemMD(text: string | null | undefined): string {
  if (!text) return ''
  const latexBlocks: LatexBlock[] = []
  const htmlBlocks: string[] = []

  // 先清洗导入管线产生的 LaTeX 垃圾（OCR→LLM 格式化数据）
  text = cleanLatex(text)

  // Protect raw HTML tags + markdown 图片语法（旧版经 marked 渲染，此处等价支持）
  let safe = text
    .replace(/<img\b[^>]*\/?>/gi, (m) => {
      htmlBlocks.push(m)
      return `\x00H${htmlBlocks.length - 1}\x00`
    })
    .replace(/<br\s*\/?>/gi, (m) => {
      htmlBlocks.push(m)
      return `\x00H${htmlBlocks.length - 1}\x00`
    })
    .replace(/!\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)/g, (_m, alt: string, src: string) => {
      htmlBlocks.push(`<img src="${src}" alt="${alt || ''}" />`)
      return `\x00H${htmlBlocks.length - 1}\x00`
    })
    // 表格/上下标片段透传（题目内容中嵌入的 HTML，旧版经 marked 渲染）
    .replace(/<\/?(?:table|thead|tbody|tr|td|th|sub|sup)\b[^>]*>/gi, (m) => {
      htmlBlocks.push(m)
      return `\x00H${htmlBlocks.length - 1}\x00`
    })

  // Protect LaTeX / chemistry before parsing
  safe = safe
    .replace(/\$\$([\s\S]*?)\$\$/g, (_m, f: string) => {
      latexBlocks.push({ t: 'd', f })
      return `\x00L${latexBlocks.length - 1}\x00`
    })
    .replace(/\\\[([\s\S]*?)\\\]/g, (_m, f: string) => {
      latexBlocks.push({ t: 'd', f })
      return `\x00L${latexBlocks.length - 1}\x00`
    })
    .replace(/\\\(([\s\S]*?)\\\)/g, (_m, f: string) => {
      latexBlocks.push({ t: 'i', f })
      return `\x00l${latexBlocks.length - 1}\x00`
    })
    .replace(/\$([^$]+?)\$/g, (_m, f: string) => {
      latexBlocks.push({ t: 'i', f })
      return `\x00l${latexBlocks.length - 1}\x00`
    })
    .replace(/\\ce\{([^}]+)\}/g, (_m, f: string) => {
      latexBlocks.push({ t: 'c', f })
      return `\x00c${latexBlocks.length - 1}\x00`
    })

  // Line-by-line parsing
  const lines = safe.split('\n')
  let html = ''
  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    const trimmed = line.trim()

    if (!trimmed) {
      i++
      continue
    }

    // Table
    if (/^\|.*\|$/.test(trimmed)) {
      const next = i + 1 < lines.length ? lines[i + 1].trim() : ''
      if (/^\|[\s\-:|]+\|$/.test(next)) {
        html += parseTable(lines, i)
        while (i < lines.length && lines[i].trim() && /^\|.*\|$/.test(lines[i].trim())) i++
        continue
      }
    }

    // Fenced code block
    if (/^```/.test(trimmed)) {
      html += '<pre><code>'
      i++
      while (i < lines.length && !/^```/.test(lines[i].trim())) {
        html += escHtml(lines[i]) + '\n'
        i++
      }
      html += '</code></pre>'
      i++
      continue
    }

    // Heading
    const hm = trimmed.match(/^(#{1,6})\s+(.+)$/)
    if (hm) {
      html += `<h${hm[1].length}>${renderInline(hm[2])}</h${hm[1].length}>`
      i++
      continue
    }

    // Horizontal rule
    if (/^(---|\*\*\*|___)\s*$/.test(trimmed)) {
      html += '<hr>'
      i++
      continue
    }

    // Blockquote
    if (trimmed.startsWith('> ')) {
      html += `<blockquote><p>${renderInline(trimmed.slice(2))}</p></blockquote>`
      i++
      continue
    }

    // Unordered list
    if (/^[\-\*\+]\s+/.test(trimmed)) {
      html += '<ul>'
      while (i < lines.length && /^[\-\*\+]\s+/.test(lines[i].trim())) {
        html += `<li>${renderInline(lines[i].trim().replace(/^[\-\*\+]\s+/, ''))}</li>`
        i++
      }
      html += '</ul>'
      continue
    }

    // Ordered list
    if (/^\d+\.\s+/.test(trimmed)) {
      html += '<ol>'
      while (i < lines.length && /^\d+\.\s+/.test(lines[i].trim())) {
        html += `<li>${renderInline(lines[i].trim().replace(/^\d+\.\s+/, ''))}</li>`
        i++
      }
      html += '</ol>'
      continue
    }

    // Paragraph
    html += `<p>${renderInline(trimmed)}</p>`
    i++
  }

  // Restore KaTeX placeholders
  html = html.replace(/\x00L(\d+)\x00/g, (_m, idx: string) => {
    const b = latexBlocks[parseInt(idx)]
    return katexRender(b.f, true)
  })
  html = html.replace(/\x00l(\d+)\x00/g, (_m, idx: string) => {
    const b = latexBlocks[parseInt(idx)]
    return katexRender(b.f, false)
  })
  html = html.replace(/\x00c(\d+)\x00/g, (_m, idx: string) => {
    const b = latexBlocks[parseInt(idx)]
    return katexRender(`\\ce{${b.f}}`, false)
  })

  // Restore protected HTML
  html = html.replace(/\x00H(\d+)\x00/g, (_m, idx: string) => htmlBlocks[parseInt(idx)])

  // Auto-detect chemical equations in text
  html = html.replace(/>([^<]+)</g, (_m, text: string) => {
    return (
      '>' +
      text.replace(
        /([A-Z][a-z]?\d*(?:[+\-]\d*)?(?:\s*[→=⇌＋+]\s*[A-Z][a-z]?\d*(?:[+\-]\d*)?)+)/g,
        (eq) => {
          try {
            const fixed = eq.replace(/=/g, '=').replace(/→/g, '->').replace(/⇌/g, '<=>')
            return katex.renderToString(`\\ce{${fixed}}`, {
              throwOnError: false,
              trust: true,
              strict: false,
            })
          } catch {
            return `<code>${escHtml(eq)}</code>`
          }
        },
      ) +
      '<'
    )
  })

  return html
}

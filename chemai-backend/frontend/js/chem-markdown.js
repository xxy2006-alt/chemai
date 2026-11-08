/* chem-markdown.js — 共享 Markdown/KaTeX 渲染器 (教师端 & 学生端)
 * 依赖: katex (CDN), mhchem (CDN), marked (CDN, optional)
 * 依赖: esc() from app.js
 */

(function() {
  var _latexBlocks = []
  var _htmlBlocks = []

  function escHtml(s) {
    return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')
  }

  function renderInline(text) {
    return escHtml(text)
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
  }

  function splitTableRow(line) {
    var parts = line.split('|')
    if (parts[0].trim() === '') parts.shift()
    if (parts.length && parts[parts.length-1].trim() === '') parts.pop()
    return parts
  }

  function parseTable(lines, startIdx) {
    var headerLine = lines[startIdx].trim()
    var headers = splitTableRow(headerLine)
    var html = '<table><thead><tr>'
    for (var h = 0; h < headers.length; h++) {
      html += '<th>' + renderInline(headers[h].trim()) + '</th>'
    }
    html += '</tr></thead><tbody>'
    var i = startIdx + 2
    while (i < lines.length && /^\|.*\|$/.test(lines[i].trim())) {
      var cells = splitTableRow(lines[i].trim())
      html += '<tr>'
      for (var c = 0; c < Math.min(cells.length, headers.length); c++) {
        html += '<td>' + renderInline(cells[c].trim()) + '</td>'
      }
      html += '</tr>'
      i++
    }
    html += '</tbody></table>'
    return html
  }

  window.renderChemMD = function(text) {
    if (!text) return ''
    _latexBlocks = []
    _htmlBlocks = []

    // Protect raw HTML tags
    var safe = text
      .replace(/<img\b[^>]*\/?>/gi, function(m) { _htmlBlocks.push(m); return '\x00H' + (_htmlBlocks.length-1) + '\x00' })
      .replace(/<br\s*\/?>/gi, function(m) { _htmlBlocks.push(m); return '\x00H' + (_htmlBlocks.length-1) + '\x00' })

    // Protect LaTeX / chemistry before parsing
    safe = safe
      .replace(/\$\$([\s\S]*?)\$\$/g, function(m, f) { _latexBlocks.push({t:'d',f:f}); return '\x00L' + (_latexBlocks.length-1) + '\x00' })
      .replace(/\\\[([\s\S]*?)\\\]/g, function(m, f) { _latexBlocks.push({t:'d',f:f}); return '\x00L' + (_latexBlocks.length-1) + '\x00' })
      .replace(/\\\(([\s\S]*?)\\\)/g, function(m, f) { _latexBlocks.push({t:'i',f:f}); return '\x00l' + (_latexBlocks.length-1) + '\x00' })
      .replace(/\$([^$]+?)\$/g, function(m, f) { _latexBlocks.push({t:'i',f:f}); return '\x00l' + (_latexBlocks.length-1) + '\x00' })
      .replace(/\\ce\{([^}]+)\}/g, function(m, f) { _latexBlocks.push({t:'c',f:f}); return '\x00c' + (_latexBlocks.length-1) + '\x00' })

    // Line-by-line parsing
    var lines = safe.split('\n')
    var html = '', i = 0
    while (i < lines.length) {
      var line = lines[i], trimmed = line.trim()

      if (!trimmed) { i++; continue }

      // Table
      if (/^\|.*\|$/.test(trimmed)) {
        var next = i + 1 < lines.length ? lines[i + 1].trim() : ''
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
      var hm = trimmed.match(/^(#{1,6})\s+(.+)$/)
      if (hm) {
        html += '<h' + hm[1].length + '>' + renderInline(hm[2]) + '</h' + hm[1].length + '>'
        i++; continue
      }

      // Horizontal rule
      if (/^(---|\*\*\*|___)\s*$/.test(trimmed)) {
        html += '<hr>'
        i++; continue
      }

      // Blockquote
      if (trimmed.startsWith('> ')) {
        html += '<blockquote><p>' + renderInline(trimmed.slice(2)) + '</p></blockquote>'
        i++; continue
      }

      // Unordered list
      if (/^[\-\*\+]\s+/.test(trimmed)) {
        html += '<ul>'
        while (i < lines.length && /^[\-\*\+]\s+/.test(lines[i].trim())) {
          html += '<li>' + renderInline(lines[i].trim().replace(/^[\-\*\+]\s+/, '')) + '</li>'
          i++
        }
        html += '</ul>'
        continue
      }

      // Ordered list
      if (/^\d+\.\s+/.test(trimmed)) {
        html += '<ol>'
        while (i < lines.length && /^\d+\.\s+/.test(lines[i].trim())) {
          html += '<li>' + renderInline(lines[i].trim().replace(/^\d+\.\s+/, '')) + '</li>'
          i++
        }
        html += '</ol>'
        continue
      }

      // Paragraph
      html += '<p>' + renderInline(trimmed) + '</p>'
      i++
    }

    // Restore KaTeX placeholders
    if (typeof katex !== 'undefined') {
      html = html.replace(/\x00L(\d+)\x00/g, function(m, idx) {
        var b = _latexBlocks[parseInt(idx)]
        try { return katex.renderToString(b.f, {throwOnError:false, displayMode:true, trust:true, strict:false}) }
        catch(e) { return '<code>' + escHtml(b.f) + '</code>' }
      })
      html = html.replace(/\x00l(\d+)\x00/g, function(m, idx) {
        var b = _latexBlocks[parseInt(idx)]
        try { return katex.renderToString(b.f, {throwOnError:false, displayMode:false, trust:true, strict:false}) }
        catch(e) { return '<code>' + escHtml(b.f) + '</code>' }
      })
      html = html.replace(/\x00c(\d+)\x00/g, function(m, idx) {
        var b = _latexBlocks[parseInt(idx)]
        try { return katex.renderToString('\\ce{' + b.f + '}', {throwOnError:false, displayMode:false, trust:true, strict:false}) }
        catch(e) { return '<code>\\ce{' + escHtml(b.f) + '}</code>' }
      })
    } else {
      html = html.replace(/\x00[Ll](\d+)\x00/g, function(m, i) { return '<code>' + escHtml(_latexBlocks[parseInt(i)].f) + '</code>' })
      html = html.replace(/\x00c(\d+)\x00/g, function(m, i) { return '<code>\\ce{' + escHtml(_latexBlocks[parseInt(i)].f) + '}</code>' })
    }

    // Restore protected HTML
    html = html.replace(/\x00H(\d+)\x00/g, function(m, idx) { return _htmlBlocks[parseInt(idx)] })

    // Auto-detect chemical equations in text
    if (typeof katex !== 'undefined') {
      html = html.replace(/>([^<]+)</g, function(m, text) {
        return '>' + text.replace(/([A-Z][a-z]?\d*(?:[+\-]\d*)?(?:\s*[→=⇌＋+]\s*[A-Z][a-z]?\d*(?:[+\-]\d*)?)+)/g, function(eq) {
          try {
            var fixed = eq.replace(/=/g, '=').replace(/→/g, '->').replace(/⇌/g, '<=>')
            return katex.renderToString('\\ce{' + fixed + '}', {throwOnError:false, trust:true, strict:false})
          } catch(e) { return '<code>' + escHtml(eq) + '</code>' }
        }) + '<'
      })
    }

    return html
  }
})()

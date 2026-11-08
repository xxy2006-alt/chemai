// OCR 答题卡识别 — 拖拽上传 + 置信度标记 + 可编辑结果 + 确认入库
(function () {
  'use strict'
  var currentResults = []  // [{student_id, name, answers: {Q1: {answer, confidence}}, ...}]
  var editedCells = {}  // key: "student_id|qNum" → new answer

  document.addEventListener('DOMContentLoaded', function () {
    loadClasses()
    initDropZone()
  })

  function loadClasses() {
    fetch('/api/classes').then(function (r) { return r.json() }).then(function (d) {
      var sel = document.getElementById('ocr-class'), list = d.classes || []
      list.forEach(function (c) { var o = document.createElement('option'); o.value = c.class_id; o.textContent = c.name; sel.appendChild(o) })
    })
  }

  // ═══════════════════════════════════════════════
  // 3.1: 拖拽上传
  // ═══════════════════════════════════════════════
  function initDropZone() {
    var zone = document.getElementById('drop-zone')
    if (!zone) return
    zone.addEventListener('dragover', function (e) { e.preventDefault(); zone.classList.add('dragover') })
    zone.addEventListener('dragleave', function () { zone.classList.remove('dragover') })
    zone.addEventListener('drop', function (e) {
      e.preventDefault(); zone.classList.remove('dragover')
      handleFiles(e.dataTransfer.files)
    })
  }

  window.handleFiles = function (files) {
    if (!files || !files.length) return
    var cls = document.getElementById('ocr-class')
    if (!cls.value) { alert('请先选择班级'); return }
    editedCells = {}; currentResults = []

    var progress = document.getElementById('ocr-progress')
    progress.style.display = 'block'
    progress.innerHTML = '<div class="card"><p class="text-sm mb-2">正在识别 ' + files.length + ' 个文件...</p><div class="progress-bar" style="width:300px"><div class="progress-fill pulse" style="width:30%"></div></div></div>'
    document.getElementById('ocr-results').innerHTML = ''

    var completed = 0
    Array.from(files).forEach(function (f) {
      var fd = new FormData(); fd.append('file', f)
      fetch('/api/ocr/recognize', { method: 'POST', body: fd })
        .then(function (r) { return r.json() })
        .then(function (d) {
          completed++
          var pct = Math.round(completed / files.length * 100)
          progress.innerHTML = '<div class="card"><p class="text-sm mb-2">识别中... (' + completed + '/' + files.length + ')</p><div class="progress-bar" style="width:300px"><div class="progress-fill" style="width:' + pct + '%"></div></div></div>'

          if (d.success && d.results) {
            d.results.forEach(function (r) {
              // Convert answers to per-question detail with mock confidence
              var answers = {}
              var ans = r.answers || {}
              Object.keys(ans).forEach(function (k) {
                var conf = 0.65 + Math.random() * 0.3  // mock: 0.65-0.95
                answers[k] = { answer: ans[k], confidence: Math.round(conf * 100) / 100 }
              })
              currentResults.push({
                student_id: r.student_id,
                student_name: r.student_name || r.student_id,
                answers: answers
              })
            })
          }

          if (completed === files.length) {
            progress.style.display = 'none'
            renderResults()
          }
        })
        .catch(function (e) {
          completed++
          if (completed === files.length) { progress.style.display = 'none'; renderResults() }
        })
    })
  }

  // ═══════════════════════════════════════════════
  // 3.2 + 3.3: 结果预览表（可编辑 + 置信度标记）
  // ═══════════════════════════════════════════════
  function renderResults() {
    var container = document.getElementById('ocr-results')
    if (!currentResults.length) { container.innerHTML = '<div class="empty-state"><p style="color:#74777f">无识别结果</p></div>'; return }

    // Collect all question numbers
    var qNums = []
    var seen = {}
    currentResults.forEach(function (r) {
      Object.keys(r.answers).forEach(function (k) { if (!seen[k]) { seen[k] = true; qNums.push(k) } })
    })
    qNums.sort()

    // Legend
    var html = '<div class="flex gap-4 mb-3 text-xs"><span><span class="conf-label conf-high">●</span> 高置信度 ≥85%</span><span><span class="conf-label conf-mid">●</span> 中 60-85%</span><span><span class="conf-label conf-low">●</span> 低 &lt;60%</span></div>'

    // Table
    html += '<div style="overflow-x:auto"><table class="data-table"><thead><tr><th>学号</th><th>姓名</th>'
    qNums.forEach(function (q) { html += '<th>' + q + '</th>' })
    html += '<th>操作</th></tr></thead><tbody>'

    currentResults.forEach(function (r) {
      var hasLowConf = false
      var cellsHtml = ''
      qNums.forEach(function (q) {
        var a = r.answers[q]
        if (!a) { cellsHtml += '<td>--</td>'; return }
        var conf = a.confidence || 0
        var confCls = conf >= 0.85 ? 'conf-high' : conf >= 0.6 ? 'conf-mid' : 'conf-low'
        if (conf < 0.6) hasLowConf = true
        var key = r.student_id + '|' + q
        var displayVal = editedCells[key] !== undefined ? editedCells[key] : a.answer
        var editedStyle = editedCells[key] !== undefined ? ' style="background:rgba(19,105,106,.08)"' : ''
        cellsHtml += '<td class="' + (conf < 0.6 ? 'low-conf-row' : '') + '"><input class="editable-cell" value="' + escHtml(displayVal) + '" data-key="' + key + '" onchange="editCell(this)"' + editedStyle + '><div class="conf-label ' + confCls + '" style="margin-top:2px">' + Math.round(conf * 100) + '%</div></td>'
      })

      html += '<tr' + (hasLowConf ? ' class="low-conf-row"' : '') + '><td style="font-family:JetBrains Mono;font-size:12px">' + escHtml(r.student_id) + '</td><td>' + escHtml(r.student_name) + '</td>' + cellsHtml +
        '<td><button class="btn-teal btn-sm" onclick="confirmOne(\'' + esc(r.student_id) + '\')">入库</button></td></tr>'
    })

    html += '</tbody></table></div>'
    // Batch confirm
    html += '<div class="flex gap-3 mt-4"><button class="btn-primary" onclick="batchConfirm()">全部确认入库</button><span class="text-sm" style="color:#43474e;line-height:36px">已入库数据可跳转到 <a href="/pages/students.html" style="color:#13696a">学生管理</a> 查看</span></div>'

    container.innerHTML = html
  }

  // ═══════════════════════════════════════════════
  // 3.3: 人工修正
  // ═══════════════════════════════════════════════
  window.editCell = function (input) {
    var key = input.getAttribute('data-key')
    var val = input.value.trim()
    if (val) {
      editedCells[key] = val
      input.style.background = 'rgba(19,105,106,.08)'
    } else {
      delete editedCells[key]
      input.style.background = ''
    }
  }

  // ═══════════════════════════════════════════════
  // 3.4: 确认入库
  // ═══════════════════════════════════════════════
  function confirmOne(sid) {
    var cls = document.getElementById('ocr-class').value
    fetch('/api/ocr/confirm', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ student_id: sid, class_id: cls })
    }).then(function (r) { return r.json() })
      .then(function (d) {
        if (d.success) { alert('已入库!'); if (ChemAI.trackActivity) ChemAI.trackActivity('ocr', '确认入库: ' + sid) }
        else { alert('入库失败') }
      }).catch(function (e) { alert('入库失败: ' + e.message) })
  }

  window.batchConfirm = function () {
    var cls = document.getElementById('ocr-class').value
    if (!currentResults.length) { alert('无识别结果'); return }
    var total = currentResults.length
    var done = 0
    currentResults.forEach(function (r) {
      fetch('/api/ocr/confirm', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ student_id: r.student_id, class_id: cls })
      }).then(function () {
        done++
        if (done === total) {
          alert('全部入库完成! (' + total + ' 条)')
          if (ChemAI.trackActivity) ChemAI.trackActivity('ocr', '批量入库 ' + total + ' 条')
        }
      }).catch(function () { done++ })
    })
  }

  // ═══════════════════════════════════════════════
  // Helpers
  // ═══════════════════════════════════════════════
  function escHtml(s) { if (!s) return ''; return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;') }
  function esc(s) { if (!s) return ''; return String(s).replace(/\\/g, '\\\\').replace(/'/g, "\\'") }
})()

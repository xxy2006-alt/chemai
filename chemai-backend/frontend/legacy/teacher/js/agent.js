/**
 * ChemAI Agent Chat — SSE 流式对话
 */
(function () {
  'use strict'
  sessionStorage.removeItem('chemai_navigate')  // 清除旧版跳转残留
  var history = []
  var isSending = false
  var currentConvId = sessionStorage.getItem('chemai_active_cid') || null
  var agentContext = { class_id: '', class_name: '', exam_id: '', exam_name: '', student_id: '', student_name: '' }
  var _toolStartTime = 0
  var _timerInterval = 0

  // ─── 共享计时器（渲染到传入的 DOM 容器内）───
  window.ChemAI.startTimer = function(container) {
    _toolStartTime = Date.now()
    clearInterval(_timerInterval)

    // Create inline timer element inside the given container
    var el = document.createElement('span')
    el.className = 'live-timer ticking'
    el.style.cssText = 'font-family:\'JetBrains Mono\',monospace;font-size:11px;color:#b43c28;margin-left:6px'
    el.textContent = '0.0s'
    if (container) container.appendChild(el)

    _timerInterval = setInterval(function() {
      var sec = ((Date.now() - _toolStartTime) / 1000).toFixed(1)
      el.textContent = sec + 's'
    }, 100)
  }

  window.ChemAI.stopTimer = function() {
    clearInterval(_timerInterval)
    _timerInterval = 0
    _toolStartTime = 0
  }

  // ─── 历史对话管理 ───
  function getConversations() {
    try { return JSON.parse(sessionStorage.getItem('chemai_convs') || '[]') } catch(e) { return [] }
  }
  function saveConversations(convs) { sessionStorage.setItem('chemai_convs', JSON.stringify(convs)) }
  function newConvId() { return 't-' + Date.now() }

  function renderHistory() {
    // Now rendered in the sidebar via refreshSidebarConvs()
    refreshSidebarConvs()
  }

  window.newConversation = function() {
    currentConvId = null; history = [];
    sessionStorage.removeItem('chemai_active_cid');
    var chat = document.getElementById('chat-messages')
    chat.innerHTML = '<div class="msg-ai"><div class="avatar">CHEMAI · 教研助手</div><p>你好，老师。</p><p style="font-size:13px;color:#555;margin-top:4px;line-height:1.7">我能帮你：配平化学方程式 · 生成练习题 · 诊断学习障碍 · 搜索历年真题 · 模拟化学实验 · 生成学习报告</p></div>'
    renderHistory()
  }

  window.loadConversation = function(id) {
    currentConvId = id
    var convs = getConversations(); var c = convs.find(function(x){return x.id===id})
    if (!c) { history = []; renderEmptyChat(); renderHistory(); return }

    // 优先从服务端加载, 有数据则直接展示
    if (c._has_server) {
      loadHistoryFromServer(id)
      renderHistory()
      return
    }

    // sessionStorage 兜底
    var chat = document.getElementById('chat-messages')
    history = c.messages || []
    if (!history.length) { renderEmptyChat(); renderHistory(); return }
    chat.innerHTML = ''
    history.forEach(function(m){
      var el = document.createElement('div')
      el.className = m.role === 'user' ? 'msg-user' : 'msg-ai'
      if (m.role === 'user') { el.textContent = m.content }
      else { el.innerHTML = '<div class="avatar">CHEMAI · 教研助手</div>' + renderChemMD(m.content) }
      chat.appendChild(el)
    })
    renderHistory()
  }

  // ── Approval card ──
  function addApprovalCard(message, callback) {
    var chat = document.getElementById('chat-messages') || document.getElementById('chatBody')
    if (!chat) return
    var card = document.createElement('div')
    card.className = 'msg-system'
    card.style.cssText = 'background:#fef9f0;border:1px solid #f0d89c;border-radius:12px;padding:14px 16px;margin:8px 0;text-align:center;max-width:90%;align-self:center'
    card.innerHTML = '<div style="font-size:14px;color:#8a6d3b;margin-bottom:10px">⚠ ' + escHtml(message) + '</div>' +
      '<div style="display:flex;gap:8px;justify-content:center">' +
        '<button class="approve-yes" style="padding:8px 20px;background:#2d5a4b;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:14px">确认</button>' +
        '<button class="approve-no" style="padding:8px 20px;background:#f5f0e8;color:#8a6d3b;border:1px solid #d5c89c;border-radius:6px;cursor:pointer;font-size:14px">取消</button>' +
      '</div>'
    chat.appendChild(card)
    chat.scrollTop = chat.scrollHeight
    card.querySelector('.approve-yes').onclick = function() { card.remove(); callback(true) }
    card.querySelector('.approve-no').onclick = function() { card.remove(); callback(false) }
  }

  function renderEmptyChat() {
    var chat = document.getElementById('chat-messages')
    chat.innerHTML = '<div class="msg-ai"><div class="avatar">CHEMAI · 教研助手</div><p>你好，老师。</p><p style="font-size:13px;color:#555;margin-top:4px;line-height:1.7">我能帮你：配平化学方程式 · 生成练习题 · 诊断学习障碍 · 搜索历年真题 · 模拟化学实验 · 生成学习报告</p></div>'
  }

  window.deleteConversation = function(id) {
    var convs = getConversations().filter(function(x){return x.id!==id})
    saveConversations(convs)
    if (currentConvId === id) { currentConvId = null; history = [] }
    renderHistory()
    refreshSidebarConvs()
    // 同步删除后端数据
    fetch('/api/agent/chat/conversations/' + id, { method: 'DELETE' }).catch(function(){})
  }

  // ── 从服务端同步对话列表 (checkpointer 是数据源, sessionStorage 是缓存) ──
  function syncFromServer() {
    fetch('/api/agent/chat/conversations?prefix=t-,c')
      .then(function(r) { return r.json() })
      .then(function(d) {
        if (!d.conversations || !d.conversations.length) return
        var localConvs = getConversations()
        var merged = {}
        // 先加载本地 (sessionStorage)
        localConvs.forEach(function(c) { merged[c.id] = c })
        // 服务端数据覆盖 (source of truth)
        d.conversations.forEach(function(svc) {
          var id = svc.thread_id
          merged[id] = merged[id] || {}
          merged[id].id = id
          merged[id].title = svc.title || merged[id].title || '新对话'
          merged[id].server_updated = svc.last_at
          merged[id].message_count = svc.message_count
          // 用服务端时间戳保持顺序稳定，避免全刷新在同一时刻导致乱序
          merged[id].updated = merged[id].updated || ((svc.last_at ? new Date(svc.last_at).getTime() : 0) || Date.now())
          // 标记有服务端数据
          merged[id]._has_server = true
        })
        // 写回 sessionStorage cache
        var mergedList = Object.values(merged)
        if (mergedList.length > 0) {
          saveConversations(mergedList)
          refreshSidebarConvs()
          // 自动加载对话（没有选中对话或聊天区为空时触发）
          if (!currentConvId || !history.length) {
            mergedList.sort(function(a, b) { return (b.updated || 0) - (a.updated || 0) })
            var best = mergedList.find(function(c) { return c.messages && c.messages.length > 0 }) || mergedList[0]
            if (best) { currentConvId = best.id; sessionStorage.setItem('chemai_active_cid', best.id); loadConversation(best.id) }
          }
        }
      })
      .catch(function() { /* 服务端不可用时用 sessionStorage 兜底 */ })
  }

  // ── 从服务端加载对话消息 ──
  function loadHistoryFromServer(threadId) {
    fetch('/api/agent/chat/history/' + threadId)
      .then(function(r) { return r.json() })
      .then(function(d) {
        if (!d.messages || !d.messages.length) return
        var msgs = []
        d.messages.forEach(function(m) {
          if (m.role === 'human' || m.role === 'user') {
            msgs.push({ role: 'user', content: m.content })
          } else if (m.role === 'assistant' || m.role === 'ai') {
            msgs.push({ role: 'assistant', content: m.content })
          }
        })
        if (msgs.length > 0) {
          history = msgs
          // 渲染消息
          var chat = document.getElementById('chat-messages')
          chat.innerHTML = ''
          msgs.forEach(function(m) {
            var el = document.createElement('div')
            el.className = m.role === 'user' ? 'msg-user' : 'msg-ai'
            if (m.role === 'user') { el.textContent = m.content }
            else { el.innerHTML = '<div class="avatar">CHEMAI · 教研助手</div>' + renderChemMD(m.content) }
            chat.appendChild(el)
          })
          // 更新 sessionStorage 缓存
          var convs = getConversations()
          var c = convs.find(function(x) { return x.id === threadId })
          if (c) { c.messages = msgs; c._has_server = true; saveConversations(convs) }
        }
      })
      .catch(function() {})
  }

  function refreshSidebarConvs() {
    var el = document.getElementById('conv-list')
    if (!el) {
      if (typeof renderSidebar === 'function') { renderSidebar('chat'); el = document.getElementById('conv-list') }
      if (!el) return
    }
    var convs = getConversations()
    convs.sort(function(a, b) { return (b.updated || 0) - (a.updated || 0) })
    var html = ''
    convs.forEach(function(c) {
      html += '<div class="history-item' + (c.id === currentConvId ? ' active' : '') + '" onclick="loadConversation(\'' + c.id + '\')">' +
        '<span class="title">' + (c.title || '新对话') + '</span>' +
        (c._has_server ? '<span style="font-size:10px;color:#3d8b5e;margin-left:4px">☁</span>' : '') +
        '<button class="del" onclick="event.stopPropagation();deleteConversation(\'' + c.id + '\')" title="删除">×</button></div>'
    })
    el.innerHTML = html || '<div style="padding:20px 12px;text-align:center;color:#999;font-size:13px">暂无对话记录</div>'
  }

  function saveCurrentConv() {
    var convs = getConversations()
    if (!currentConvId) { currentConvId = newConvId(); var c = {id:currentConvId,title:'',messages:[],updated:Date.now()}; convs.push(c) }
    var c = convs.find(function(x){return x.id===currentConvId})
    if (!c) { c = {id:currentConvId,title:'',messages:[],updated:Date.now()}; convs.push(c) }
    c.messages = history.slice()
    c.updated = Date.now()
    if (!c.title && history.length>0) {
      var firstUser = history.find(function(m){return m.role==='user'})
      if (firstUser) c.title = firstUser.content.substring(0,40)
    }
    saveConversations(convs)
    renderHistory()
  }

  window.setContext = function(ctx) {
    Object.assign(agentContext, ctx || {})
    renderContextBar()
  }
  window.clearContext = function() {
    agentContext = { class_id: '', class_name: '', exam_id: '', exam_name: '', student_id: '', student_name: '' }
    renderContextBar()
  }
  function renderContextBar() {
    var bar = document.getElementById('agent-context')
    if (!bar) return
    var visible = !!(agentContext.class_id || agentContext.exam_id || agentContext.student_id)
    bar.style.display = visible ? 'flex' : 'none'
    document.getElementById('ctx-class').textContent = agentContext.class_name || ''
    document.getElementById('ctx-class').style.display = agentContext.class_id ? '' : 'none'
    document.getElementById('ctx-exam').textContent = agentContext.exam_name || ''
    document.getElementById('ctx-exam').style.display = agentContext.exam_id ? '' : 'none'
    document.getElementById('ctx-student').textContent = agentContext.student_name || ''
    document.getElementById('ctx-student').style.display = agentContext.student_id ? '' : 'none'
  }

  // ─── 化学式实时格式化 ───
  var SUB = ['₀','₁','₂','₃','₄','₅','₆','₇','₈','₉']
  var SUP = ['⁰','¹','²','³','⁴','⁵','⁶','⁷','⁸','⁹']
  function subDigits(s) { var r=''; for (var i=0;i<s.length;i++) r+=SUB[s[i]]; return r }
  function superDigits(s) { var r=''; for (var i=0;i<s.length;i++) r+=SUP[s[i]]; return r }

  function formatChemicalText(text) {
    var result = '', i = 0, elemCount = 0
    text = text.replace(/-->/g, '→').replace(/->/g, '→')

    function resetWord() { elemCount = 0 }
    function isSep(ch) { return !ch || /[\s+=→\+\-\(\)]/.test(ch) }

    while (i < text.length) {
      var ch = text[i]

      // = between words → arrow
      if (ch === '=' && (i===0 || text[i-1]===' ') && (i+1>=text.length || text[i+1]===' ')) {
        result += '→'; i++; resetWord(); continue
      }
      // + or - preceded by space → separator (not charge), reset word
      if ((ch === '+' || ch === '-') && (i===0 || text[i-1]===' ')) {
        result += ch; i++; resetWord(); continue
      }

      // Element symbol
      if (/[A-Z]/.test(ch)) {
        var elem = ch; i++
        if (i < text.length && /[a-z]/.test(text[i])) { elem += text[i]; i++ }
        elemCount++

        // Digits after element
        if (i < text.length && /[0-9]/.test(text[i])) {
          var num = ''; while (i < text.length && /[0-9]/.test(text[i])) { num += text[i]; i++ }
          // Followed by charge sign at end of compound?
          if (i < text.length && /[+-]/.test(text[i]) && (i+1>=text.length || /[\s+=→]/.test(text[i+1]))) {
            var chargeSign = text[i]
            // Single element + short number → all charge: Fe3+ → Fe³⁺
            if (elemCount === 1 && parseInt(num) <= 3) {
              result += elem + superDigits(num) + (chargeSign==='+'?'⁺':'⁻'); i++; resetWord(); continue
            }
            // Multi-element: last digit ≤3 → split into subscript + charge: SO42- → SO₄²⁻
            if (elemCount > 1 && num.length > 1 && parseInt(num[num.length-1]) <= 3) {
              result += elem + subDigits(num.slice(0,-1)) + superDigits(num.slice(-1)) + (chargeSign==='+'?'⁺':'⁻'); i++; resetWord(); continue
            }
            // Subscript + separate charge: MnO4- → MnO₄⁻, NH4+ → NH₄⁺
            result += elem + subDigits(num) + (chargeSign==='+'?'⁺':'⁻'); i++; resetWord(); continue
          }
          result += elem + subDigits(num); continue
        }

        // Element directly + charge: Na+ → Na⁺
        if (i < text.length && /[+-]/.test(text[i]) && (i+1>=text.length || /[\s+=→]/.test(text[i+1]))) {
          result += elem + (text[i]==='+'?'⁺':'⁻'); i++; resetWord(); continue
        }
        result += elem; continue
      }

      // Standalone number + charge: 2e-, 3+
      if (/[0-9]/.test(ch)) {
        var n = ''; while (i < text.length && /[0-9]/.test(text[i])) { n += text[i]; i++ }
        if (i < text.length && /[+-]/.test(text[i]) && (i+1>=text.length || /[\s+=→]/.test(text[i+1]))) {
          result += superDigits(n) + (text[i]==='+'?'⁺':'⁻'); i++; resetWord(); continue
        }
        result += n; continue
      }

      // ) + digits → )₃
      if (ch === ')' && i+1 < text.length && /[0-9]/.test(text[i+1])) {
        result += ')'; i++; var pn = ''; while (i < text.length && /[0-9]/.test(text[i])) { pn += text[i]; i++ }
        result += subDigits(pn); continue
      }

      if (ch === ' ' || ch === '+' || ch === '→') resetWord()
      result += ch; i++
    }
    return result
  }

  function updateChemPreview() {
    var input = document.getElementById('chat-input')
    var preview = document.getElementById('chem-preview')
    if (!input || !preview) return
    var raw = input.value.trim()
    if (!raw) { preview.className = 'chem-preview'; preview.textContent = ''; return }
    var formatted = formatChemicalText(raw)
    if (formatted === raw) { preview.className = 'chem-preview'; preview.textContent = ''; return }
    preview.textContent = formatted
    preview.className = 'chem-preview show'
  }

  // ─── 事件绑定 ───
  document.addEventListener('DOMContentLoaded', function () {
    var input = document.getElementById('chat-input')
    if (input) {
      input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() }
        autoResize(input)
      })
      input.addEventListener('input', function () { autoResize(input); updateChemPreview() })
    }

    // Suggestion chips — fill input with template, let user complete
    document.querySelectorAll('.chip[data-prompt]').forEach(function (c) {
      c.addEventListener('click', function () {
        var input = document.getElementById('chat-input')
        input.value = c.dataset.prompt
        input.focus()
        autoResize(input)
        updateChemPreview()
      })
    })
  })

  function autoResize(el) {
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 120) + 'px'
  }

  // ─── 全局发送入口 ───
  // ─── 文件上传 ───
  window.handleFileUpload = function (event) {
    var file = event.target.files[0]
    if (!file) return
    if (file.size > 10 * 1024 * 1024) { alert('文件不能超过 10MB'); return }

    var fd = new FormData(); fd.append('file', file)
    addMsg('user', '📎 上传文件: ' + file.name)

    fetch('/api/agent/upload', { method: 'POST', body: fd })
      .then(function(r) { return r.json() })
      .then(function(d) {
        var html = '<div class="upload-card" style="background:#f0fdf4;border:1px solid #86efac;border-radius:8px;padding:12px;margin:8px 0">'
        html += '<p style="font-weight:600;margin:0 0 8px">📄 ' + (d.file_name || '文件') + '</p>'
        html += '<p style="font-size:13px;color:#555;margin:0 0 10px">' + (d.preview_text || '').substring(0, 200) + '</p>'
        html += '<div style="display:flex;gap:6px">'
        ;(d.actions || []).forEach(function(a) {
          html += '<button onclick="confirmUploadAction(\'' + d.upload_id + '\',\'' + a.id + '\')" '
          html += 'style="padding:4px 14px;border:1px solid #ccc;border-radius:4px;background:white;cursor:pointer;font-size:13px">' + a.label + '</button>'
        })
        html += '</div></div>'
        addMsg('ai', html)
        event.target.value = ''  // reset file input
      })
      .catch(function(e) {
        addMsg('ai', '<span style="color:#b43c28">上传失败: ' + e.message + '</span>')
      })
  }

  window.confirmUploadAction = function(uploadId, action) {
    var actionLabels = { import: '导入题库', grade: '批改判卷', search: '搜题解析' }
    var msg = actionLabels[action] + ' [upload_id=' + uploadId + ']'
    sendMessage(msg)
  }

  // ─── 批量上传答题卡（📄）：直连 OCR batch，拿 batch_id 后注入消息触发 agent ───
  window.handleBatchUpload = function (event) {
    var files = Array.prototype.slice.call(event.target.files || [])
    event.target.value = ''  // reset so same files can be re-selected
    if (!files.length) return
    if (files.length > 10) { addMsg('ai', '<span style="color:#b43c28">一次最多上传 10 张答题卡</span>'); return }
    for (var i = 0; i < files.length; i++) {
      if (files[i].size > 10 * 1024 * 1024) { addMsg('ai', '<span style="color:#b43c28">单张答题卡不能超过 10MB</span>'); return }
    }
    var uid = localStorage.getItem('teacher_id') || ''
    try { var u = JSON.parse(sessionStorage.getItem('chemai_user') || '{}'); uid = u.id || u.teacher_id || '' } catch (_) {}

    var fd = new FormData()
    fd.append('teacher_id', uid)
    files.forEach(function (f) { fd.append('files', f) })

    addMsg('user', '已选择 ' + files.length + ' 张答题卡，正在提交识别...')
    fetch('/api/ocr/tasks/batch', { method: 'POST', body: fd })
      .then(function (r) { return r.json() })
      .then(function (d) {
        if (!d.success || !d.batch_id) {
          addMsg('ai', '<span style="color:#b43c28">批量上传失败: ' + escHtml(d.detail || '未知错误') + '</span>')
          return
        }
        sendMessage('我已上传 ' + d.count + ' 张答题卡，批次号 ' + d.batch_id + '（teacher_id=' + uid + '）。请识别这批答题卡并批改。')
      })
      .catch(function (e) {
        addMsg('ai', '<span style="color:#b43c28">批量上传失败: ' + escHtml(e.message) + '</span>')
      })
  }

  window.sendMessage = function (text) {
    if (isSending) return
    sessionStorage.removeItem('chemai_navigate')  // 清除旧版跳转残留
    var input = document.getElementById('chat-input')
    var preview = document.getElementById('chem-preview')
    var msg = text || (preview && preview.textContent) || input.value.trim()
    if (!msg) return
    if (!text) { input.value = ''; input.style.height = 'auto'; if (preview) { preview.className = 'chem-preview'; preview.textContent = '' } }
    if (ChemAI.trackActivity) ChemAI.trackActivity('chat', msg.substring(0, 30))

    // Ensure conversation_id exists and is persisted
    if (!currentConvId) {
      currentConvId = sessionStorage.getItem('chemai_active_cid') || newConvId()
    }
    sessionStorage.setItem('chemai_active_cid', currentConvId)

    isSending = true
    var sendBtn = document.getElementById('chat-send')
    if (sendBtn) { sendBtn.disabled = true; sendBtn.style.opacity = '.5' }
    if (input) input.disabled = true

    // Show status bar (tool name only)
    var stBar = document.getElementById('agent-status')
    if (stBar) stBar.style.display = 'flex'
    var stTool = document.getElementById('status-tool')
    if (stTool) stTool.textContent = '分析中...'
    var stTime = document.getElementById('status-time')
    if (stTime) stTime.textContent = ''

    // 思考状态进气泡（计时器注入到这里）
    addMsg('user', msg)
    history.push({ role: 'user', content: msg })
    var bubble = addMsg('ai', '<div class="think-status"><span class="dot"></span>思考中...</div><div class="think-dots"><span></span><span></span><span></span></div>')
    ChemAI.startTimer(bubble.querySelector('.think-status'))

    fetch('/api/agent/chat/langgraph/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ persona: 'teacher', message: msg, provider: 'deepseek', conversation_id: currentConvId, history: history.slice(0, -1), version: 'v2' })
    }).then(function (resp) {
      if (!resp.ok) throw new Error('HTTP ' + resp.status)
      return streamResponse(resp, bubble)
    }).catch(function (e) {
      ChemAI.stopTimer()
      bubble.innerHTML = '<span style="color:#b43c28">抱歉，请求失败: ' + e.message + '</span>'
      resetSendState()
    })
  }

  // ─── SSE 流式读取 ───
  async function streamResponse(resp, bubble) {
    var reader = resp.body.getReader()
    var decoder = new TextDecoder()
    var buffer = '', reply = '', _subPanel = null, _subAgentName = '', _subToolCount = 0, _routeCard = null, _topToolCards = [], _pendingImages = []

    while (true) {
      var r = await reader.read()
      if (r.done) break
      buffer += decoder.decode(r.value, { stream: true })
      var lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (var i = 0; i < lines.length; i++) {
        var line = lines[i]
        if (!line.startsWith('data: ')) continue
        var payload = line.slice(6)
        if (payload === '[DONE]') break

        // ── Legacy think markers (backward compat) ──
        if (payload === '<think>' || payload === '</think>') continue

        try {
          var evt = JSON.parse(payload)
        } catch (e) { console.error('SSE event error:', e, payload); continue }
        if (evt.type === 'done') break

        if (evt.type !== 'text' && evt.type !== 'phase' && evt.type !== 'step') {
          console.log('[IMG-DBG] SSE EVENT:', evt.type)
        }

        if (evt.type !== 'text' && evt.type !== 'phase' && evt.type !== 'step') {
          console.log('[IMG-DBG] SSE EVENT:', evt.type)
        }

        switch (evt.type) {
          case 'phase':
            if (evt.phase === 'awaiting_approval') {
              var thinkEl = bubble.querySelector('.think-status');
              if (thinkEl) thinkEl.remove();
              var msg = evt.message || '请确认操作'
              addApprovalCard(msg, function(approved) {
                isSending = true
                fetch('/api/agent/chat/langgraph/resume', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ persona: 'teacher', message: approved ? 'approved' : 'cancelled', provider: 'deepseek', conversation_id: currentConvId, version: 'v2' })
                }).then(function(resp) {
                  if (!resp.ok) throw new Error('HTTP ' + resp.status)
                  return streamResponse(resp, bubble)
                }).catch(function(e) {
                  ChemAI.stopTimer()
                  bubble.insertAdjacentHTML('beforeend', '<div style="color:#b43c28;font-size:13px;padding:8px 0">操作失败: ' + escHtml(e.message) + '</div>')
                  resetSendState()
                })
              })
            }
            var st = bubble.querySelector('.think-status')
            var phaseLabels = {thinking:'分析中...', executing:'执行中...', reply:'回复中...', planning:'生成计划...'}
            if (st) st.innerHTML = '<span class="dot"></span>' + (phaseLabels[evt.phase] || evt.phase)
            break

          // ── Route card ──
          case 'route':
            // Clear any coordinator chatter before route
            bubble.textContent = ''; reply = ''
            _routeCard = addRouteCard(evt)
            break

          // ── Sub-agent panel ──
          case 'sub_agent_start':
            _subAgentName = evt.agent
            _subToolCount = 0
            _subPanel = addSubAgentPanel(evt)
            if (_routeCard) updateRouteCard(_routeCard, 'dispatched', evt)
            break

          case 'sub_agent_end':
            if (_subPanel) closeSubAgentPanel(_subPanel, _subToolCount)
            _subPanel = null
            _subAgentName = ''
            break

          case 'subagent_text':
            if (_subPanel) appendSubAgentText(_subPanel, evt.content)
            scrollBottom()
            break

          // ── Tool cards (always standalone) ──
          case 'tool_call':
            if (evt.name && (evt.name + '').startsWith('route_to_')) break
            // Always show a tool card, regardless of sub-agent state
            if (_subPanel) { _subToolCount++; addSubAgentTool(_subPanel, evt.name, 'running') }
            try {
              var card = addToolCard(evt.name)
              if (card) { card._toolName = evt.name; _topToolCards.push(card) }
            } catch(e) { console.error('[tool_call] addToolCard failed:', e) }
            var stTool2 = document.getElementById('status-tool')
            if (stTool2) stTool2.textContent = evt.name
            break

          case 'tool_result':
            if (_subPanel) { addSubAgentTool(_subPanel, evt.name, evt.success !== false ? 'done' : 'error') }
            var pending = _topToolCards.filter(function(c) { return c._toolName === evt.name && !c._filled })
            if (pending.length) {
              try { updateToolCard(pending[0], evt); pending[0]._filled = true }
              catch(e) { console.error('[tool_result] updateToolCard failed:', e) }
            }
            break

          case 'tool_error':
            if (_subPanel) { addSubAgentTool(_subPanel, evt.name, 'error') }
            break

          // ── Main dialog streaming ──
          case 'text':
            if (!reply) bubble.textContent = ''
            reply += evt.content
            bubble.textContent = reply
            scrollBottom()
            break

          case 'plan_summary':
            bubble.innerHTML += addPlanCard(evt)
            scrollBottom()
            break

          case 'plan_progress':
            updatePlanCard(evt)
            break

          case 'exam_images':
            console.log('[IMG-DBG] exam_images event RECEIVED:', evt.urls ? evt.urls.length : 0, 'urls')
            _pendingImages = _pendingImages || []
            _pendingImages.push(evt)
            break

          default:
            console.log('[IMG-DBG] unhandled SSE event type:', evt.type)
            break

          case 'step':
            var st3 = bubble.querySelector('.think-status')
            var labels = {search_exam_bank:'搜索真题', generate_questions:'AI出题', diagnose_barrier:'障碍诊断', chemistry_tutor:'智能辅导', simulate_experiment:'模拟实验', weekly_report:'生成周报', import_exam_paper:'导入试卷', assign_adaptive_practice:'布置练习', balance_equation:'配平审核', web_search:'联网搜索'}
            var label = labels[evt.skill] || evt.skill
            if (st3) st3.innerHTML = '<span class="dot"></span>第 ' + (evt.current || '?') + ' 步：' + label
            break

          case 'navigate':
            var nav = {page: evt.page, params: evt.params || {}, data: {}, actions: []}
            sessionStorage.setItem('chemai_navigate', JSON.stringify(nav))
            break

          case 'populate':
            try {
              var navData = JSON.parse(sessionStorage.getItem('chemai_navigate') || '{}')
              if (!navData.data) navData.data = {}
              navData.data[evt.target] = evt.data
              sessionStorage.setItem('chemai_navigate', JSON.stringify(navData))
            } catch(e) {}
            break

          case 'action':
            try {
              var navAct = JSON.parse(sessionStorage.getItem('chemai_navigate') || '{}')
              if (!navAct.actions) navAct.actions = []
              navAct.actions.push({action: evt.action, payload: evt.payload})
              sessionStorage.setItem('chemai_navigate', JSON.stringify(navAct))
            } catch(e) {}
            break

          case 'component':
            sessionStorage.removeItem('chemai_navigate')
            var rawText = bubble.textContent || ''
            if (rawText.trim()) {
              rawText = rawText.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/^- /gm, '· ').replace(/\n\n/g, '<br>')
              bubble.textContent = ''; bubble.insertAdjacentHTML('afterbegin', '<div style="font-size:14px">'+rawText+'</div>')
            }
            if (evt.component === 'exam-workbench') renderExamWorkbench(evt.params || {}, bubble)
            else if (evt.component === 'diagnosis') renderDiagnosis(evt.params || {}, bubble)
            else if (evt.component === 'learning_plan') renderLearningPlanPanel(evt.params || {}, bubble)
            else if (evt.component === 'student-list') renderStudentList(evt.params || {}, bubble)
            break

          case 'error':
            var errHtml = '<div style="color:#b43c28;padding:8px 0;font-size:13px;border-top:1px solid #fecaca;margin-top:8px">' +
              escHtml(evt.message || '未知错误') + '</div>'
            if (evt.recoverable) {
              errHtml += '<button class="btn btn-sm" onclick="ChemAI.retryLastMessage()" style="margin-top:6px;font-size:12px">重试</button>'
            }
            bubble.insertAdjacentHTML('beforeend', errHtml)
            ChemAI.stopTimer()
            resetSendState()
            break
        }
      }
    }

    // ── Cleanup ──
    var thinkEl = bubble.querySelector('.think-status')
    if (thinkEl) thinkEl.remove()
    var hasPanel = bubble.querySelector('.inline-exam-panel, .inline-diag-panel')
    if (reply && !hasPanel) {
      bubble.innerHTML = renderChemMD(reply)
    }
    // Inject collected exam images — match by q_index to question position
    if (_pendingImages && _pendingImages.length > 0) {
      _pendingImages.forEach(function(evt) {
        var urls = evt.urls || []
        var qIdx = evt.q_index || 0
        if (urls.length > 0) {
          var qLabel = '第' + (qIdx + 1) + '题'
          var nextLabel = '第' + (qIdx + 2) + '题'
          var allEls = bubble.querySelectorAll('*')
          var targetEl = null, nextEl = null

          // Pass 1: find question heading by exact label match
          for (var h = 0; h < allEls.length; h++) {
            var el = allEls[h]
            // Only check leaf-level elements (avoid matching whole bubble)
            if (el.children.length > 0) continue
            var txt = el.textContent || ''
            if (!targetEl && txt.indexOf(qLabel) !== -1) {
              targetEl = el.parentElement  // insert after the line containing the label
            }
            if (!nextEl && txt.indexOf(nextLabel) !== -1) {
              nextEl = el.parentElement
            }
            if (targetEl) break  // found our question, stop
          }

          // Pass 2: broader search — match by question text anywhere
          if (!targetEl) {
            for (var j = 0; j < allEls.length; j++) {
              var ej = allEls[j]
              if (ej.children.length > 0) continue
              if ((ej.textContent||'').indexOf(qLabel) !== -1) {
                targetEl = ej; break
              }
            }
          }

          // Image container
          var container = document.createElement('div')
          container.style.cssText = 'margin:6px 0;display:flex;flex-wrap:wrap;gap:8px'
          urls.forEach(function(url) {
            var img = document.createElement('img')
            img.src = url
            img.style.cssText = 'max-width:100%;max-height:400px;border:1px solid #e5e0d8;border-radius:8px;cursor:pointer;background:#fff'
            img.title = evt.title || ''
            img.onclick = function() { window.open(url, '_blank') }
            img.onerror = function() { this.style.display = 'none' }
            container.appendChild(img)
          })

          // Insert at best position
          if (targetEl) {
            targetEl.insertAdjacentElement('afterend', container)
          } else if (nextEl) {
            nextEl.insertAdjacentElement('beforebegin', container)
          } else {
            // Last resort: insert before the closing hint paragraph
            var hints = bubble.querySelectorAll('blockquote')
            if (hints.length > 0) {
              hints[hints.length-1].insertAdjacentElement('beforebegin', container)
            } else {
              bubble.appendChild(container)
            }
          }
        }
      })
      _pendingImages = []
      scrollBottom()
    }
    // Always save conversation history, even with inline panels
    if (reply || hasPanel) {
      history.push({ role: 'assistant', content: reply || '[面板交互]' })
      saveCurrentConv()
    }
    // Remove empty coordinator bubble when sub-agent handled everything
    if (!reply && !hasPanel && !bubble.textContent.trim() &&
        (bubble.nextElementSibling || bubble.previousElementSibling)) {
      bubble.remove()
    }
    // Check if agent wants to navigate to another page
    var navigateTo = sessionStorage.getItem('chemai_navigate')
    if (navigateTo) {
      try {
        var nav = JSON.parse(navigateTo)
        if (nav.page) {
          if (currentConvId) sessionStorage.setItem('chemai_active_cid', currentConvId)
          var url = '/pages/' + nav.page + '.html'
          if (nav.params && Object.keys(nav.params).length) {
            url += '?' + Object.keys(nav.params).map(function(k) { return encodeURIComponent(k) + '=' + encodeURIComponent(nav.params[k]) }).join('&')
          }
          setTimeout(function() { window.location.href = url }, 500)
        }
      } catch(e) {}
    }
    resetSendState()
  }

  function escHtml(s) { if (!s) return ''; return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;') }

  // ─── UI Helpers ───
  function addMsg(role, text) {
    var container = document.getElementById('chat-messages')
    var el = document.createElement('div')
    el.className = role === 'user' ? 'msg-user' : role === 'system' ? 'msg-system' : 'msg-ai'
    if (role === 'ai') {
      el.innerHTML = '<div class="avatar">CHEMAI · 教研助手</div>' + text
    } else if (role === 'system') {
      el.innerHTML = '<div style="padding:6px 12px;font-size:12px;color:#2c6e49;background:rgba(44,110,73,.06);border-radius:6px;margin:4px 0">'+text+'</div>'
    } else {
      el.textContent = text
    }
    container.appendChild(el)
    scrollBottom()
    return el
  }

  function addToolCard(name, status) {
    var container = document.getElementById('chat-messages')
    if (!container) return null
    var card = document.createElement('div')
    card.className = 'tool-card running'
    card.innerHTML = '<div class="tool-card-header">' +
      '<span class="chevron" style="font-size:10px;color:#aaa;display:inline-block;transition:transform .2s">▶</span>' +
      '<span style="color:#b43c28">⚗</span>' +
      '<span style="font-weight:500">' + escHtml(name) + '</span>' +
      '<span style="color:#e6a817;font-size:10px;margin-left:auto">运行中...</span>' +
      '</div><div class="tool-card-body collapsible-body"><div class="collapsible-inner"></div></div>'
    card.onclick = function(e) {
      if (e.target.closest('.collapsible-inner a') || e.target.closest('.collapsible-inner button')) return
      var body = card.querySelector('.tool-card-body')
      var chev = card.querySelector('.chevron')
      if (!body) return
      var expanded = body.classList.contains('open')
      body.classList.toggle('open', !expanded)
      if (chev) chev.style.transform = expanded ? 'rotate(0deg)' : 'rotate(90deg)'
    }
    container.appendChild(card)
    scrollBottom()
    return card
  }

  function addToolCardMsg(bubble, name, status) {
    bubble.innerHTML = '<div class="think-status"><span class="dot"></span>调用工具: ' + name + '</div>'
  }

  // ── Route Card ──
  function addRouteCard(evt) {
    var container = document.getElementById('chat-messages')
    var card = document.createElement('div')
    card.className = 'route-card'
    card.style.cssText = 'display:flex;align-items:center;gap:8px;padding:8px 12px;margin:4px 0;border:1.5px solid #e0d5c1;border-radius:8px;background:linear-gradient(135deg,#fef9f0,#fdf5e6);font-size:13px;color:#8b7355'
    card.innerHTML = '<span style="font-size:16px">🔀</span>' +
      '<span style="font-weight:600;color:#6b5340">路由至 ' + escHtml(evt.display || evt.agent) + '</span>' +
      '<span class="route-status" style="font-family:\'JetBrains Mono\',monospace;font-size:10px;color:#b8a88a;margin-left:auto">分析意图中...</span>'
    container.appendChild(card)
    scrollBottom()
    return card
  }

  function updateRouteCard(card, status, evt) {
    var st = card.querySelector('.route-status')
    if (!st) return
    if (status === 'dispatched') {
      st.textContent = '已分派 ✓'
      st.style.color = '#2c6e49'
      card.style.borderColor = '#c8e6c9'
      card.style.background = 'linear-gradient(135deg,#f4faf4,#e8f5e9)'
    }
  }

  // ── Sub-Agent Panel (streaming) ──
  function addSubAgentPanel(evt) {
    var container = document.getElementById('chat-messages')
    var panel = document.createElement('div')
    panel.className = 'sub-agent-panel'
    panel.style.cssText = 'border:1.5px solid #e0e0e0;border-radius:8px;margin:4px 0;background:#fcfcfc'
    var display = evt.display || evt.agent

    // Get icon for sub-agent type
    var icon = '🤖'
    var iconMap = {search_expert:'🔍', exam_expert:'📝', diagnosis_expert:'🩺', tutor_expert:'📚', bank_manager:'🗄️', browser_expert:'🌐'}
    icon = iconMap[evt.agent] || icon

    panel.innerHTML =
      '<div class="sa-header" style="padding:8px 12px;cursor:pointer;font-size:13px;color:#555;background:#fafafa;display:flex;align-items:center;gap:8px;user-select:none;border-bottom:1px solid #f0f0f0">' +
      '<span class="sa-chevron" style="transition:transform .2s;font-size:10px;color:#aaa">▶</span>' +
      '<span>' + icon + '</span>' +
      '<span style="font-weight:600">' + escHtml(display) + '</span>' +
      '<span class="sa-status" style="font-family:\'JetBrains Mono\',monospace;font-size:10px;color:#b43c28;margin-left:auto">⏳ 执行中</span>' +
      '</div>' +
      '<div class="sa-body collapsible-body open">' +
      '<div class="collapsible-inner">' +
      '<div class="sa-tools" style="padding:4px 12px"></div>' +
      '<div class="sa-text" style="padding:6px 12px 10px;font-size:13px;line-height:1.65;color:#666;border-top:1px dashed #eee;display:none;white-space:pre-wrap;word-break:break-word"></div>' +
      '</div>' +
      '</div>'
    container.appendChild(panel)
    scrollBottom()

    panel.querySelector('.sa-header').addEventListener('click', function() {
      var body = this.nextElementSibling
      var chev = this.querySelector('.sa-chevron')
      var expanded = body.classList.contains('open')
      body.classList.toggle('open', !expanded)
      chev.style.transform = expanded ? 'rotate(0deg)' : 'rotate(90deg)'
    })
    return panel
  }

  function appendSubAgentText(panel, content) {
    var textEl = panel.querySelector('.sa-text')
    if (textEl) {
      textEl.style.display = 'block'
      textEl.textContent += content
      panel.querySelector('.sa-body').scrollTop = panel.querySelector('.sa-body').scrollHeight
    }
  }

  function addSubAgentTool(panel, name, status) {
    var tools = panel.querySelector('.sa-tools')
    if (!tools) return
    var existing = tools.querySelector('[data-tool="' + name + '"]')
    if (status === 'running') {
      if (existing) return
      var div = document.createElement('div')
      div.setAttribute('data-tool', name)
      div.style.cssText = 'font-size:11px;color:#888;padding:1px 0;font-family:JetBrains Mono,monospace'
      div.textContent = '⏳ ' + name
      tools.appendChild(div)
    } else {
      if (existing) {
        existing.textContent = (status === 'error' ? '✗ ' : '✓ ') + name
        existing.style.color = status === 'error' ? '#b43c28' : '#2c6e49'
      }
    }
  }

  function closeSubAgentPanel(panel, toolCount) {
    var header = panel.querySelector('.sa-header')
    var status = panel.querySelector('.sa-status')
    if (header) {
      var chev = header.querySelector('.sa-chevron')
      if (chev) chev.style.transform = 'rotate(90deg)'
    }
    if (status) {
      status.textContent = '✓ 完成 (' + toolCount + '工具)'
      status.style.color = '#2c6e49'
    }
    // Collapse the panel
    var body = panel.querySelector('.sa-body')
    if (body) body.classList.remove('open')
  }

  function updateToolCard(card, evt) {
    var ok = evt.success !== false
    card.classList.remove('running')
    card.classList.add(ok ? 'done' : 'error')
    var status = card.querySelector('.tool-card-header span:last-child')
    if (status) { status.textContent = ok ? '完成' : '失败'; status.style.color = ok ? '#2c6e49' : '#b43c28' }
    var inner = card.querySelector('.collapsible-inner')
    if (!inner) return
    var toolName = evt.name || evt.tool

    var data = evt.result
    if (typeof data === 'string') {
      try { data = JSON.parse(data) } catch(e) { /* keep as string */ }
    }

    try {
      var rendered = window.ChemRender ? window.ChemRender(toolName, data) : '<pre>'+JSON.stringify(data,null,2)+'</pre>'
      inner.innerHTML = rendered
    } catch(e) {
      inner.innerHTML = '<pre style="color:#C53030;font-size:11px">渲染失败: ' + escHtml(String(e.message || e)) + '</pre>'
    }
    var body = card.querySelector('.tool-card-body')
    var chev = card.querySelector('.chevron')
    if (body) body.classList.add('open')
    if (chev) chev.style.transform = 'rotate(90deg)'
    setTimeout(function() {
      if (body) body.classList.remove('open')
      if (chev) chev.style.transform = 'rotate(0deg)'
    }, 4000)
  }

  // ─── Plan Card ───
  var _planSteps = []  // Track plan step states

  function addPlanCard(plan) {
    _planSteps = plan.steps.map(function(s) {
      return {step: s.step, skill: s.skill, description: s.description, status: 'pending'}
    })
    var html = '<div class="plan-card" id="plan-card">' +
      '<div class="plan-card-header" style="font-family:\'Cormorant Garamond\',Georgia,serif;font-size:16px;font-weight:600;margin-bottom:10px">' +
        '📋 ' + escHtml(plan.goal || '执行计划') +
        '<span style="font-family:\'JetBrains Mono\',monospace;font-size:10px;color:#999;margin-left:8px">' + plan.total_steps + ' 步</span>' +
      '</div>' +
      '<div class="plan-card-body">' +
      '<div class="plan-card-body-inner">'
    plan.steps.forEach(function(s, i) {
      html += '<div class="plan-step" id="plan-step-' + i + '" style="display:flex;align-items:center;gap:10px;padding:6px 0;font-size:13px">' +
        '<span class="plan-step-num" style="width:24px;height:24px;border-radius:50%;border:1.5px solid rgba(0,0,0,.15);display:flex;align-items:center;justify-content:center;font-family:\'JetBrains Mono\',monospace;font-size:11px;flex-shrink:0">' + s.step + '</span>' +
        '<span style="flex:1">' + escHtml(s.description) + '</span>' +
        '<span class="plan-step-status" style="font-family:\'JetBrains Mono\',monospace;font-size:10px;color:#999">等待中</span>' +
        '</div>'
    })
    html += '</div></div>' +
      '<div class="plan-card-summary" style="display:none;font-family:\'JetBrains Mono\',monospace;font-size:11px;color:#2c6e49;padding:4px 0"></div>'
    html += '</div>'
    return html
  }

  function updatePlanCard(progress) {
    var idx = (progress.current_step || 1) - 1
    var stepEl = document.getElementById('plan-step-' + idx)
    if (!stepEl) return
    var numEl = stepEl.querySelector('.plan-step-num')
    var statusEl = stepEl.querySelector('.plan-step-status')
    if (progress.status === 'running') {
      numEl.style.background = '#b43c28'; numEl.style.color = '#fff'; numEl.style.borderColor = '#b43c28'
      statusEl.textContent = '执行中...'; statusEl.style.color = '#b43c28'
      _planSteps[idx].status = 'running'
    } else if (progress.status === 'completed') {
      numEl.style.background = '#2c6e49'; numEl.style.color = '#fff'; numEl.style.borderColor = '#2c6e49'
      numEl.textContent = '✓'
      statusEl.textContent = '完成'; statusEl.style.color = '#2c6e49'
      _planSteps[idx].status = 'completed'
    } else if (progress.status === 'failed') {
      numEl.style.background = '#b43c28'; numEl.style.color = '#fff'; numEl.style.borderColor = '#b43c28'
      numEl.textContent = '✗'
      statusEl.textContent = '失败'; statusEl.style.color = '#b43c28'
      _planSteps[idx].status = 'failed'
    }
    // Check if all done
    if (_planSteps.every(function(s) { return s.status === 'completed' || s.status === 'failed' })) {
      setTimeout(function() {
        var card = document.getElementById('plan-card')
        if (!card) return
        var summary = card.querySelector('.plan-card-summary')
        var done = _planSteps.filter(function(s){return s.status==='completed'}).length
        var total = _planSteps.length
        summary.textContent = done + '/' + total + ' 步骤已完成'
        summary.style.display = ''
        card.classList.add('collapsed')
        card.onclick = function() {
          card.classList.toggle('collapsed')
        }
      }, 2000)
    }
  }

  function showStatus(show, text, tool) {
    var bar = document.getElementById('agent-status')
    var txt = document.getElementById('status-text')
    if (!bar || !txt) return
    bar.style.display = show ? 'flex' : 'none'
    txt.textContent = text || ''
  }

  function scrollBottom() {
    var el = document.querySelector('.chat-area') || document.getElementById('chat-messages')
    if (el) { el.scrollTop = el.scrollHeight }
  }

  function resetSendState() {
    isSending = false
    ChemAI.stopTimer()
    var sendBtn = document.getElementById('chat-send')
    var input = document.getElementById('chat-input')
    if (sendBtn) { sendBtn.disabled = false; sendBtn.style.opacity = '' }
    if (input) input.disabled = false
    var stBar = document.getElementById('agent-status')
    if (stBar) setTimeout(function() { stBar.style.display = 'none' }, 2000)
  }

  // KaTeX + Markdown rendering provided by shared /js/chem-markdown.js (renderChemMD)

  // KaTeX + Markdown 渲染（marked.js 路径）
  window.renderChemistry = function(text) {
    if (!text) return ''
    if (typeof katex === 'undefined' || typeof marked === 'undefined') return escHtml(text)
    try {
      var idx=0, blocks=[], h=text
      // Protect allowed raw HTML (结构图 <img> / <br>)，其余 < > 转义防 XSS（与 chem-markdown.js 一致）
      var htmlBlocks=[]
      h=h.replace(/<img\b[^>]*\/?>/gi,function(m){var k='\uE002H'+htmlBlocks.length+'\uE003';htmlBlocks.push(m);return k})
      h=h.replace(/<br\s*\/?>/gi,function(m){var k='\uE002H'+htmlBlocks.length+'\uE003';htmlBlocks.push(m);return k})
      h=h.replace(/</g,'&lt;').replace(/>/g,'&gt;')
      // Protect paired $$...$$
      h=h.replace(/\$\$([\s\S]*?)\$\$/g,function(m,e){var k='\uE000LATEX'+idx+'\uE001';blocks.push({key:k,tex:e,display:true});idx++;return k})
      // Protect paired $...$
      h=h.replace(/\$(?!\$)([\s\S]*?)\$/g,function(m,e){if(e.length<300){var k='\uE000LATEX'+idx+'\uE001';blocks.push({key:k,tex:e,display:false});idx++;return k}return m})
      // Escape any remaining unpaired $ signs
      h=h.replace(/\$/g,'<span>$</span>')
      // Markdown → HTML
      h=marked.parse(h,{breaks:true,gfm:true})
      // Render LaTeX blocks
      blocks.forEach(function(b){try{var ren=katex.renderToString(b.tex,{displayMode:b.display,throwOnError:false,trust:true,strict:false});h=h.replace(b.key,ren)}catch(_){h=h.replace(b.key,b.tex)}})
      // Render \ce{} blocks
      h=h.replace(/\\ce\{([^}]+)\}/g,function(m,f){try{return katex.renderToString('\\ce{'+f+'}',{throwOnError:false,trust:true,strict:false})}catch(_){return m}})
      // Restore protected raw HTML (img/br)
      h=h.replace(/\uE002H(\d+)\uE003/g,function(m,i){return htmlBlocks[parseInt(i)]})
      return h
    } catch(e) { return text }
  }

  // ─── Inline Exam Workbench Panel (Full Interactive) ───
  function renderExamWorkbench(params, bubble) {
    if (!bubble) return
    var preKps = (params.knowledge_points || []).join('、')
    var preDiff = params.difficulty || 'medium'
    var preTypes = params.types || [{val:'single_choice',active:true,qty:3}]
    var preVariant = params.variant_source || ''
    var preFolder = params.set_name || ''

    // Update mode: search entire chat for existing panel, update in-place
    var existingPanel = document.querySelector('.inline-exam-panel')
    if (existingPanel) {
      var qa = existingPanel.querySelector('.inline-exam-questions')
      if (!qa) return
      // Remove the new bubble that triggered this update (panel already exists)
      if (!bubble.contains(existingPanel)) { bubble.remove() }
      // Update question list from params
      var questions = params.questions || []
      if (questions.length) {
        qa.style.display = 'block'
        qa._qs = questions
        qa._fid = preFolder || qa._fid || 'auto-' + Date.now()
        qa._fn = preFolder || qa._fn || '自动创建'
        qa.innerHTML = '<div class="exam-qcards"></div>'
        _renderQs(qa._qs, qa.querySelector('.exam-qcards'))
        _renderQsFooter(qa)
      }
      // Update status
      var st = existingPanel.querySelector('.inline-exam-status')
      if (st) st.textContent = questions.length ? '已生成 ' + questions.length + ' 道题目' : ''
      // Stop any running timer
      var timer = existingPanel.querySelector('.live-timer')
      if (timer && timer.classList.contains('ticking')) ChemAI.stopTimer()
      return
    }

    var html = '<style>'+
      '.inline-exam-btn{display:inline-block;padding:6px 14px;border:1px solid #ddd;border-radius:6px;font-size:12px;cursor:pointer;background:#fff;color:#555;transition:all .15s;margin:2px}'+
      '.inline-exam-btn:hover{background:#f5f5f5;border-color:#bbb}'+
      '.inline-exam-btn.primary{background:#b43c28;color:#fff;border-color:#b43c28;font-weight:600}'+
      '.inline-exam-btn.primary:hover{background:#9a3522}'+
      '.inline-exam-btn.sm{padding:3px 10px;font-size:11px}'+
      '.inline-exam-btn-sm{padding:3px 8px;border:1px solid #ddd;border-radius:4px;font-size:11px;cursor:pointer;background:#fff;color:#555;margin:1px}'+
      '.inline-exam-btn-sm:hover{background:#f5f5f5}'+
      '.inline-exam-btn-sm.danger{color:#b43c28;border-color:#b43c28}'+
      '.inline-exam-btn-sm.danger:hover{background:rgba(180,60,40,.06)}'+
      '.inline-exam-qcard{border:1px solid #eee;border-radius:6px;padding:10px;margin:8px 0;background:#fff}'+
      '.inline-exam-qcard:hover{border-color:#ddd}'+
      '</style>'+
      '<div class="inline-exam-panel">'+
      '<div class="inline-exam-header" style="font-weight:700;margin-bottom:10px;font-size:15px;border-bottom:2px solid #b43c28;padding-bottom:8px">考试工作台</div>'+
      '<div style="margin-bottom:12px"><div style="font-size:12px;color:#888;margin-bottom:4px">题型与数量</div><div class="inline-exam-types"></div></div>'+
      '<div style="margin-bottom:12px"><span style="font-size:12px;color:#888">难度</span> <select class="inline-exam-diff" style="padding:4px 8px;border:1px solid #ddd;border-radius:4px;font-size:13px"><option value="easy"'+(preDiff==='easy'?' selected':'')+'>容易</option><option value="medium"'+(preDiff==='medium'?' selected':'')+'>中等</option><option value="hard"'+(preDiff==='hard'?' selected':'')+'>偏难</option></select></div>'+
      '<div style="margin-bottom:12px;border-top:1px solid #eee;padding-top:10px"><div style="font-size:12px;color:#888;margin-bottom:4px">知识点 <span style="font-weight:400">（搜索并点击选中）</span></div><div class="inline-exam-kps-active" style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:6px;min-height:20px"></div><input class="inline-exam-kp-search" placeholder="搜索知识点..." style="width:100%;padding:6px 10px;border:1px solid #ddd;border-radius:4px;font-size:13px;box-sizing:border-box;margin-bottom:6px"><div class="inline-exam-kps-list" style="display:flex;flex-wrap:wrap;gap:4px;max-height:100px;overflow-y:auto"></div></div>'+
      '<div style="margin-bottom:12px;border-top:1px solid #eee;padding-top:10px"><label style="font-size:13px;cursor:pointer"><input type="checkbox" class="inline-exam-use-variant" style="margin-right:4px"'+(preVariant?' checked':'')+'>基于真题生成变种题</label><div class="inline-exam-variant-info" style="margin-top:4px;font-size:12px;color:#b43c28">'+(preVariant?'当前蓝本: '+escHtml(preVariant):'')+'</div><div style="display:flex;gap:6px;align-items:center;margin-top:4px"><button class="inline-exam-btn sm inline-exam-variant-browse" style="display:'+(preVariant?'inline-block':'none')+'">浏览真题蓝本</button><button class="inline-exam-btn sm inline-exam-variant-clear" style="display:none;color:#999;border-color:#ddd">✕ 清除蓝本</button></div></div>'+
      '<div style="margin-bottom:12px;border-top:1px solid #eee;padding-top:10px"><div style="font-size:12px;color:#888;margin-bottom:4px">保存到</div><select class="inline-exam-folder" style="padding:4px 8px;border:1px solid #ddd;border-radius:4px;font-size:13px;min-width:200px"><option value="">自动创建</option></select><button class="inline-exam-btn sm inline-exam-new-folder" style="margin-left:6px">+ 新建</button></div>'+
      '<div class="inline-exam-actions" style="margin-bottom:10px"><button class="inline-exam-btn primary inline-exam-gen-btn">AI 出题</button></div>'+
      '<div class="inline-exam-questions" style="display:none"></div><div class="inline-exam-status" style="font-size:13px;color:#888"></div></div>'

    bubble.insertAdjacentHTML('beforeend', html)

    // Post-render: populate interactive controls
    var panel = bubble.querySelector('.inline-exam-panel:last-child')
    if (!panel) return

    panel._preKps = preKps; panel._variantSource = preVariant; panel._variantQid = ''
    if(preVariant) panel.querySelector('.inline-exam-variant-clear').style.display = 'inline-block'

    // Types
    var typesContainer = panel.querySelector('.inline-exam-types')
    var typeDefs = [{val:'single_choice',label:'选择题',active:false,qty:3},{val:'fill_blank',label:'填空题',active:false,qty:2},{val:'calculation',label:'计算题',active:false,qty:1},{val:'experiment',label:'实验题',active:false,qty:1},{val:'inference',label:'推断题',active:false,qty:1}]
    preTypes.forEach(function(pt){ var m=typeDefs.find(function(t){return t.val===pt.val}); if(m){m.active=pt.active;m.qty=pt.qty||m.qty} })
    function _renderTypes(){ typesContainer.innerHTML = typeDefs.map(function(t,i){ return '<span class="inline-exam-type-chip" data-idx="'+i+'" style="display:inline-flex;align-items:center;gap:4px;padding:4px 10px;margin:2px;border:1.5px solid '+(t.active?'#b43c28':'#ddd')+';border-radius:14px;cursor:pointer;font-size:12px;background:'+(t.active?'rgba(180,60,40,.06)':'#fff')+';color:'+(t.active?'#b43c28':'#888')+'">'+(t.active?'●':'○')+' '+t.label+(t.active?' <input type="number" min="1" max="10" value="'+t.qty+'" style="width:36px;padding:2px 4px;border:1px solid #ddd;border-radius:3px;font-size:12px;text-align:center" onclick="event.stopPropagation()">':'')+'</span>' }).join('') }
    _renderTypes()
    typesContainer.addEventListener('click',function(e){ var chip=e.target.closest('.inline-exam-type-chip'); if(!chip)return; var t=typeDefs[parseInt(chip.dataset.idx)]; t.active=!t.active; _renderTypes() })
    typesContainer.addEventListener('change',function(e){ if(e.target.tagName==='INPUT'){ var chip=e.target.closest('.inline-exam-type-chip'); typeDefs[parseInt(chip.dataset.idx)].qty=parseInt(e.target.value)||1 } })

    // KPs
    fetch('/api/knowledge/list', {credentials: 'include'}).then(function(r){return r.json()}).then(function(data){
      var allKps=(data.knowledge_points||data.data||[]).map(function(k){var n=typeof k==='string'?k:(k.name||k);return{name:n,active:false}})
      if(preKps){preKps.split('、').forEach(function(pk){var m=allKps.find(function(k){return k.name===pk});if(m)m.active=true})}
      panel._kps=allKps; _renderKps()
    }).catch(function(){})
    var kpSearch=panel.querySelector('.inline-exam-kp-search'); kpSearch.addEventListener('input',function(){_renderKps()})
    function _renderKps(){
      var kps=panel._kps||[], s=kpSearch.value.toLowerCase()
      var active=panel.querySelector('.inline-exam-kps-active'), list=panel.querySelector('.inline-exam-kps-list')
      var aKps=kps.filter(function(k){return k.active})
      active.innerHTML=aKps.length?aKps.map(function(k){return '<span style="display:inline-flex;align-items:center;gap:4px;padding:3px 8px;background:rgba(180,60,40,.08);border:1px solid #b43c28;border-radius:12px;font-size:12px;color:#b43c28;cursor:pointer" data-kp="'+escHtml(k.name)+'">'+escHtml(k.name)+'<span style="font-size:14px">&times;</span></span>'}).join(''):'<span style="font-size:12px;color:#bbb">未选择</span>'
      active.querySelectorAll('span[data-kp]').forEach(function(c){c.addEventListener('click',function(){var m=kps.find(function(k){return k.name===c.dataset.kp});if(m)m.active=false;_renderKps()})})
      var filtered=kps.filter(function(k){return!k.active&&(!s||k.name.toLowerCase().includes(s))})
      list.innerHTML=filtered.slice(0,30).map(function(k){return '<span style="display:inline-block;padding:3px 8px;border:1.5px solid #ddd;border-radius:12px;font-size:12px;cursor:pointer;color:#555;white-space:nowrap" data-kp="'+escHtml(k.name)+'">'+escHtml(k.name)+'</span>'}).join('')
      list.querySelectorAll('span[data-kp]').forEach(function(c){c.addEventListener('click',function(){var m=kps.find(function(k){return k.name===c.dataset.kp});if(m)m.active=true;_renderKps()})})
    }

    // Folders
    fetch('/api/exam-bank/exam-sets', {credentials: 'include'}).then(function(r){return r.json()}).then(function(data){
      var sets=(data.data&&data.data.exam_sets)||data.exam_sets||[]
      var sel=panel.querySelector('.inline-exam-folder'); sets.forEach(function(s){sel.innerHTML+='<option value="'+s.set_id+'">'+escHtml(s.name)+' ('+(s.question_count||0)+')</option>'})
    }).catch(function(){})

    // Generate — via Agent resume (not direct API call)
    panel.querySelector('.inline-exam-gen-btn').addEventListener('click',function(){
      var active=typeDefs.filter(function(t){return t.active}), st=panel.querySelector('.inline-exam-status'), qa=panel.querySelector('.inline-exam-questions')
      if(!active.length){st.textContent='请至少选择一种题型';return}
      var diff=panel.querySelector('.inline-exam-diff').value
      var kps=(panel._kps||[]).filter(function(k){return k.active}).map(function(k){return k.name})
      if(!kps.length)kps=['高中化学综合']
      var fs=panel.querySelector('.inline-exam-folder'), fid=fs.value, fn=fs.selectedOptions&&fs.selectedOptions[0]?fs.selectedOptions[0].textContent.replace(/\s*\(\d+\)\s*$/,''):'自动创建'
      if(!fid){fid='auto-'+Date.now();fn='自动创建'}
      qa.style.display='block'; qa.innerHTML=''; qa._qs=[]; qa._fid=fid; qa._fn=fn

      var typeLabels={single_choice:'选择题',fill_blank:'填空题',calculation:'计算题',experiment:'实验题',inference:'推断题'}
      var typeStr=active.map(function(t){return t.val+':'+t.qty}).join(',')
      var totalQty=active.reduce(function(s,t){return s+t.qty},0)
      var progressHTML='<div style="margin:8px 0;padding:10px;background:#f9f9f9;border-radius:6px;font-size:13px"><b>⚡ AI 出题</b><span class="live-timer ticking" style="font-family:\'JetBrains Mono\',monospace;font-size:11px;color:#b43c28;margin-left:8px"></span><br>'
      active.forEach(function(t){ progressHTML+='<div class="exam-prog-'+t.val+'" style="margin:2px 0">⏳ '+typeLabels[t.val]+' ×'+t.qty+' 等待 Agent...</div>' })
      progressHTML+='</div><div class="exam-qcards"></div>'
      qa.innerHTML=progressHTML; st.textContent=''
      ChemAI.startTimer(qa.querySelector('.live-timer'))

      // Direct API: panel handles exam generation, Agent handles conversation
      var pending = active.length
      active.forEach(function(t){
        var progEl = qa.querySelector('.exam-prog-'+t.val)
        if (progEl) progEl.textContent = '⏳ ' + typeLabels[t.val] + ' ×' + t.qty + ' 已提交'
        var t0 = Date.now()
        var body = {knowledge_points: kps, difficulty: diff, quantity: t.qty, question_types: [t.val]}
        if (panel._variantSource) { body.variant_source = panel._variantSource; body.variant_qid = panel._variantQid }
        fetch('/api/question/generate', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)})
          .then(function(r){return r.json()}).then(function(d){
            if (progEl) progEl.textContent = '🔄 ' + typeLabels[t.val] + ' ×' + t.qty + ' AI组织题目中...(' + Math.round((Date.now()-t0)/1000) + 's)'
            var qs = d.questions || []
            qs.forEach(function(q){q._typeLabel = t.val; q._saved = false})
            qa._qs = qa._qs.concat(qs)
            if (qa.querySelector('.exam-qcards').textContent.includes('正在提交')) qa.querySelector('.exam-qcards').innerHTML = ''
            _renderQs(qs, qa.querySelector('.exam-qcards'))
            if (progEl) progEl.textContent = '✅ ' + typeLabels[t.val] + ' ×' + qs.length + ' 完成 (' + Math.round((Date.now()-t0)/1000) + 's)'
            pending--
            if (pending === 0) { ChemAI.stopTimer(); _renderQsFooter(qa) }
          }).catch(function(){
            if (progEl) progEl.textContent = '❌ ' + typeLabels[t.val] + ' 失败'
            pending--
            if (pending === 0) { ChemAI.stopTimer(); _renderQsFooter(qa) }
          })
      })
    })

    function _renderQs(qs,container){
      qs.forEach(function(q,i){
        var o=(q.options||[]).map(function(o,j){return '<div>'+String.fromCharCode(65+j)+'. '+escHtml(String(o).replace(/^[A-F]\.\s*/,''))+'</div>'}).join('')
        container.insertAdjacentHTML('beforeend',
          '<div class="inline-exam-qcard" style="border:1px solid #eee;border-radius:6px;padding:10px;margin:8px 0;background:#fff">'+
          '<div><b>'+(container.querySelectorAll('.inline-exam-qcard').length+1)+'.</b> '+(typeof renderChemistry==='function'?renderChemistry(q.content||''):escHtml(q.content||''))+'</div>'+
          (q.options?'<div style="margin:8px 0 0 20px;font-size:13px">'+o+'</div>':'')+
          '<div style="margin-top:6px;font-size:12px;color:#999">答案: <span style="color:#b43c28">'+(typeof renderChemistry==='function'?renderChemistry(q.answer||''):escHtml(q.answer||''))+'</span></div>'+
          '<div style="margin-top:6px"><button class="inline-exam-btn-sm inline-exam-save-q">保存</button><button class="inline-exam-btn-sm inline-exam-del-q">删除</button></div></div>')
      })
      // Bind save/delete for the new cards
      container.querySelectorAll('.inline-exam-save-q').forEach(function(btn){
        btn.addEventListener('click',function(){var card=btn.closest('.inline-exam-qcard'),idx=Array.from(card.parentNode.querySelectorAll('.inline-exam-qcard')).indexOf(card);ChemAI._saveQinPanel(card.closest('.inline-exam-questions'),idx,btn)})})
      container.querySelectorAll('.inline-exam-del-q').forEach(function(btn){
        btn.addEventListener('click',function(){var card=btn.closest('.inline-exam-qcard');if(card)card.style.display='none'})})
    }

    function _renderQsFooter(qa){
      var total=qa._qs.length, saved=qa._qs.filter(function(q){return q._saved}).length
      var fname=qa._fn
      var h='<div style="margin-top:10px;padding-top:10px;border-top:1px solid #eee;font-size:13px">'+
        '<span style="color:#2c6e49">'+total+' 题 · 已保存 '+saved+'/道 · 目标:「'+escHtml(fname)+'」</span>'+
        '<div style="margin-top:6px"><button class="inline-exam-btn primary inline-exam-save-all-btn">全部保存到「'+escHtml(fname)+'」</button>'+
        '<button class="inline-exam-btn inline-exam-redo-btn">全部重出</button>'+
        '<button class="inline-exam-btn inline-exam-done-btn">完成</button></div></div>'
      qa.insertAdjacentHTML('beforeend',h)
      // Bind footer buttons
      var fb=qa.lastElementChild
      fb.querySelector('.inline-exam-save-all-btn').addEventListener('click',function(){ChemAI._saveAllInPanel(qa)})
      fb.querySelector('.inline-exam-redo-btn').addEventListener('click',function(){panel.querySelector('.inline-exam-gen-btn').click()})
      fb.querySelector('.inline-exam-done-btn').addEventListener('click',function(){
        this.disabled=true;this.style.opacity='.4';this.textContent='已完成'
        // Save all remaining before closing
        ChemAI._saveAllInPanel(qa)
        panel.querySelector('.inline-exam-status').textContent='已完成'
        addMsg('system','✅ 出题完成：共生成'+qa._qs.length+'道题，已保存'+qa._qs.filter(function(q){return q._saved}).length+'道到「'+qa._fn+'」')
      })
    }

    // Variant — clear selection
    panel.querySelector('.inline-exam-variant-clear').addEventListener('click',function(){
      panel._variantQid = ''; panel._variantSource = ''
      panel.querySelector('.inline-exam-variant-info').textContent = ''
      panel.querySelector('.inline-exam-variant-clear').style.display = 'none'
    })

    // Variant — multi-select with toggle
    panel._selQs = panel._selQs || []
    panel.querySelector('.inline-exam-use-variant').addEventListener('change',function(){panel.querySelector('.inline-exam-variant-browse').style.display=this.checked?'inline-block':'none'})
    panel.querySelector('.inline-exam-variant-browse').addEventListener('click',function(){
      var ov=document.createElement('div'); ov.className='inline-exam-vb-overlay'; ov.style.cssText='position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.3);z-index:9999;display:flex;align-items:center;justify-content:center'
      ov.innerHTML='<div style="background:#fff;border-radius:8px;padding:16px;max-width:650px;max-height:85vh;display:flex;flex-direction:column;width:92%"><div style="font-weight:700;margin-bottom:6px">选择真题蓝本 <span class="ivb-sel-count" style="color:#b43c28;font-size:12px;font-weight:400"></span></div><div class="ivb-content" style="font-size:13px;flex:1;overflow-y:auto">加载中...</div><div style="margin-top:10px;display:flex;justify-content:flex-end;gap:8px"><button class="ivb-clear-btn" style="padding:4px 12px;border:1px solid #ddd;border-radius:4px;cursor:pointer;font-size:12px">清除选择</button><button class="ivb-close-btn" style="padding:4px 16px;border:1px solid #ddd;border-radius:4px;cursor:pointer;font-size:12px">取消</button><button class="ivb-confirm-btn" style="padding:4px 20px;background:#b43c28;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:12px">确认蓝本</button></div></div>'
      document.body.appendChild(ov)
      var selQs = []
      function updateSelCount(){ var el=ov.querySelector('.ivb-sel-count'); el.textContent=selQs.length?'已选 '+selQs.length+' 题':'' }
      ov.querySelector('.ivb-close-btn').addEventListener('click',function(){document.body.removeChild(ov)})
      ov.addEventListener('click',function(e){if(e.target===ov)document.body.removeChild(ov)})
      ov.querySelector('.ivb-clear-btn').addEventListener('click',function(){selQs=[];updateSelCount();ov.querySelectorAll('.ivb-q').forEach(function(e){e.classList.remove('ivb-q-sel');e.style.borderLeft='1px solid #eee';e.style.background=''})})
      ov.querySelector('.ivb-confirm-btn').addEventListener('click',function(){
        if(!selQs.length) return
        panel._variantQid = selQs[0].qid
        panel._variantSource = selQs.map(function(s){return s.label}).join('、')
        panel.querySelector('.inline-exam-variant-info').textContent = '当前蓝本: ' + panel._variantSource
        if(selQs.length>1) panel.querySelector('.inline-exam-variant-info').textContent += ' ('+selQs.length+'题)'
        panel.querySelector('.inline-exam-variant-clear').style.display = selQs.length?'inline-block':'none'
        document.body.removeChild(ov)
      })
      fetch('/api/exam-bank/papers').then(function(r){return r.json()}).then(function(data){var groups=(data.data&&data.data.groups)||data.groups||[]; var ps=[]; groups.forEach(function(g){var r=g.region; (g.years||[]).forEach(function(y){ (y.papers||[]).forEach(function(p){ p.region=r; p.year=y.year; ps.push(p) }) }) }); var c=ov.querySelector('.ivb-content')
        c.innerHTML='<div style="font-size:12px;color:#888;margin-bottom:8px">点击试卷浏览题目</div>'+ps.slice(0,50).map(function(p){return '<div class="ivb-paper" style="padding:6px 8px;margin:2px 0;border:1px solid #eee;border-radius:4px;cursor:pointer;font-size:12px" data-r="'+escHtml(p.region||'')+'" data-y="'+(p.year||'')+'">'+escHtml(p.source||p.name||'')+' · '+(p.year||'')+' ('+(p.question_count||p.total||'?')+'题)</div>'}).join('')
        c.querySelectorAll('.ivb-paper').forEach(function(el){el.addEventListener('click',function(){c.innerHTML='加载中...'
          fetch('/api/exam-bank/historical?region='+encodeURIComponent(el.dataset.r)+'&year='+encodeURIComponent(el.dataset.y)+'&page_size=30').then(function(r){return r.json()}).then(function(qd){var qs=(qd.data&&qd.data.questions)||qd.questions||[]
            c.innerHTML='<div style="font-size:12px;color:#888;margin-bottom:8px">点击题目多选，再次点击取消</div>'+qs.map(function(q,i){var imgHtml=''; if(q.page_image){var pi=q.page_image; if(!pi.startsWith('/'))pi='/static/figures/'+encodeURIComponent(q.region||'')+'/'+(q.year||'')+'/'+pi; imgHtml='<img src=\"'+pi+'\" style=\"width:50px;height:35px;object-fit:cover;border-radius:3px;margin-right:6px;float:left;border:1px solid #eee\">'} var rendered=(typeof renderChemistry==='function'?renderChemistry(q.content||''):escHtml(q.content||'')); var stripped=rendered.replace(/<[^>]*>/g,'').substring(0,100); return '<div class=\"ivb-q\" data-qid=\"'+(q.exam_id||q.question_id||'')+'\" data-label=\"'+(el.dataset.r||'')+' #'+(i+1)+'\" style=\"padding:6px 8px;margin:2px 0;border:1px solid #eee;border-radius:4px;cursor:pointer;font-size:12px;overflow:hidden;transition:.15s\">'+imgHtml+'<b>#'+(i+1)+'</b> '+stripped+'<div style=\"clear:both\"></div></div>'}).join('')
            c.querySelectorAll('.ivb-q').forEach(function(qel){qel.addEventListener('click',function(){
              var qid=qel.dataset.qid,label=qel.dataset.label,idx=selQs.findIndex(function(s){return s.qid===qid})
              if(idx>=0){ selQs.splice(idx,1); qel.classList.remove('ivb-q-sel'); qel.style.borderLeft='1px solid #eee'; qel.style.background='' }
              else{ selQs.push({qid:qid,label:label}); qel.classList.add('ivb-q-sel'); qel.style.borderLeft='3px solid #b43c28'; qel.style.background='rgba(180,60,40,.04)' }
              updateSelCount()
            })})
          }).catch(function(){c.innerHTML='加载失败'})
        })})
      }).catch(function(){ov.querySelector('.ivb-content').innerHTML='加载失败'})
    })

    // New folder — create + select + feedback
    panel.querySelector('.inline-exam-new-folder').addEventListener('click',function(){var n=prompt('请输入新题库名称：');if(!n)return
      var st=panel.querySelector('.inline-exam-status');st.textContent='创建文件夹...'
      fetch('/api/exam-bank/exam-sets',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:n})}).then(function(r){return r.json()}).then(function(d){
        if(d.success&&d.exam_set){
          var s=panel.querySelector('.inline-exam-folder')
          s.insertAdjacentHTML('beforeend','<option value="'+d.exam_set.set_id+'" selected>'+escHtml(n)+' (0)</option>')
          s.value=d.exam_set.set_id; st.textContent='✅ 已创建「'+escHtml(n)+'」'
        }else{st.textContent='创建失败'}
      }).catch(function(){st.textContent='创建失败'})})
  }

  // ─── Shared panel helpers (in-panel save with auto-folder) ───
  window.ChemAI._saveQinPanel = function(qArea, idx, btn) {
    var q = (qArea._qs || [])[idx]; if (!q || q._saved) return
    _ensureFolder(qArea, function(fid){ _doSaveQ(qArea, q, btn, fid) })
  }
  function _doSaveQ(qArea, q, btn, fid) {
    fetch('/api/exam-bank/import-questions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({set_id:fid,questions:[{content:q.content,options:q.options||[],answer:q.answer||'',knowledge_points:q.knowledge_points||[],difficulty:q.difficulty||'medium'}]})})
      .then(function(r){return r.json()}).then(function(d){if(d.success){q._saved=true;btn.textContent='已保存';btn.disabled=true;btn.style.opacity='.4';_updatePanelCount(qArea)}})
  }
  window.ChemAI._saveAllInPanel = function(qArea) {
    var qs=(qArea._qs||[]).filter(function(q){return!q._saved});if(!qs.length)return
    _ensureFolder(qArea, function(fid){ _doSaveAll(qArea, qs, fid) })
  }
  function _doSaveAll(qArea, qs, fid) {
    var body = JSON.stringify({set_id: fid, questions: qs.map(function(q) { return {content: q.content, options: q.options || [], answer: q.answer || '', knowledge_points: q.knowledge_points || [], difficulty: q.difficulty || 'medium'} })})
    fetch('/api/exam-bank/import-questions', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: body})
      .then(function(r) { return r.json() })
      .then(function(d) {
        if (d.success) {
          qs.forEach(function(q) { q._saved = true })
          _updatePanelCount(qArea)
          var fn = qArea._fn || ''
          addMsg('system', '已保存 ' + qs.length + ' 道题到「' + fn + '」')
          var fb = qArea.querySelector('.inline-exam-qcards+div') || qArea.lastElementChild
          if (fb) {
            var b = fb.querySelector('.inline-exam-save-all-btn')
            if (b) { b.disabled = true; b.style.opacity = '.4'; b.textContent = '已保存' }
          }
        }
      })
  }
  function _ensureFolder(qArea, cb) {
    var fid=qArea._fid; if(fid&&!String(fid).startsWith('auto-')){cb(fid);return}
    var fn=qArea._fn||'AI出题'
    fetch('/api/exam-bank/exam-sets',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:fn})})
      .then(function(r){return r.json()}).then(function(d){if(d.success&&d.exam_set){qArea._fid=d.exam_set.set_id;qArea._fn=fn;cb(d.exam_set.set_id)}else{cb('unknown')}}).catch(function(){cb('unknown')})
  }
  function _updatePanelCount(qArea) {
    var total=qArea._qs.length, saved=qArea._qs.filter(function(q){return q._saved}).length
    var fb=qArea.querySelector('.inline-exam-qcards+div')||qArea.lastElementChild
    if(fb){var s=fb.querySelector('span');if(s)s.textContent=total+' 题 · 已保存 '+saved+' 道 · 目标:'+escHtml(qArea._fn||'');var b=fb.querySelector('.inline-exam-save-all-btn');if(b)b.textContent='全部保存到「'+escHtml(qArea._fn||'')+'」('+saved+'/'+total+')'}
  }
  // Legacy
  window.ChemAI._saveQ = function(btn,idx){var c=btn.closest('.inline-exam-questions');if(c)ChemAI._saveQinPanel(c,idx,btn)}
  window.ChemAI._saveAll = function(btn){var c=btn.closest('.inline-exam-questions');if(c)ChemAI._saveAllInPanel(c)}
  window.ChemAI._delQ = function(){}
  window.ChemAI._redo = function(btn){var p=btn.closest('.inline-exam-panel');if(p)p.querySelector('.inline-exam-gen-btn').click()}
  window.ChemAI._done = function(btn){var p=btn.closest('.inline-exam-panel'),c=p.querySelector('.inline-exam-questions'),qs=(c&&c._qs)||[];if(p)p.querySelector('.inline-exam-status').textContent='已完成';sendMessage('出题完成：共生成'+qs.length+'道题，已保存'+qs.filter(function(q){return q._saved}).length+'道到「'+(c?c._fn||'':'')+'」。')}

  // ─── Inline Diagnosis Panel ───
  function renderDiagnosis(params, bubble) {
    console.log('[DIAG] renderDiagnosis params keys:', Object.keys(params))
    console.log('[DIAG] total_answers:', params.total_answers, 'accuracy:', params.accuracy, 'wkps:', params.weak_knowledge_points, 'trend:', params.score_trend)
    var barrierLabels = {concept:'概念理解', reading:'审题能力', expression:'规范表述'}
    var barrierColors = {concept:'#b43c28', reading:'#d97706', expression:'#2c6e49'}

    var barrier = params.barrier_distribution || {}
    var vals = Object.values(barrier)
    var isRawCount = vals.length > 0 && Math.max.apply(null, vals) > 1

    var h = '<style>'+
      '.inline-exam-btn{display:inline-block;padding:6px 14px;border:1px solid #ddd;border-radius:6px;font-size:12px;cursor:pointer;background:#fff;color:#555;transition:all .15s;margin:2px}'+
      '.inline-exam-btn:hover{background:#f5f5f5;border-color:#bbb}'+
      '.inline-exam-btn.primary{background:#b43c28;color:#fff;border-color:#b43c28;font-weight:600}'+
      '.inline-exam-btn.primary:hover{background:#9a3522}'+
      '.diag-bar-wrap{display:flex;align-items:center;margin:6px 0}'+
      '.diag-bar-label{width:72px;font-size:13px;color:#555;flex-shrink:0}'+
      '.diag-bar-track{flex:1;height:18px;background:#f0f0f0;border-radius:4px;overflow:hidden;margin:0 8px}'+
      '.diag-bar-fill{height:100%;border-radius:4px;transition:width .4s ease}'+
      '.diag-bar-val{font-size:13px;font-weight:700;min-width:44px;text-align:right}'+
      '</style>'

    h += '<div class="inline-diag-panel" style="border:1px solid #e0d5c8;border-radius:10px;padding:16px;margin:8px 0;background:#fdfaf5">'
    var hasNewData = params.total_answers !== undefined
    h += '<div style="font-weight:700;margin-bottom:12px;font-size:15px;color:#4a3728">学情诊断: ' + escHtml(params.student_name || params.student_id || '') + (hasNewData ? ' <span style=\"font-size:10px;color:#2c6e49;background:#e0f2e0;padding:1px 6px;border-radius:4px\">V2</span>' : ' <span style=\"font-size:10px;color:#b43c28;background:#fef2f2;padding:1px 6px;border-radius:4px\">V1-无新数据</span>') + '</div>'

    if (params.dominant_barrier) {
      var domLabel = barrierLabels[params.dominant_barrier] || params.dominant_barrier
      h += '<div style="margin-bottom:12px;font-size:13px;color:#666">主导障碍: <b style="color:#b43c28">' + escHtml(domLabel) + '</b> &middot; 完成练习: <b>' + (params.exercises_completed || 0) + '</b></div>'
    }

    // 学生列表（班级诊断时）
    if (params.students && params.students.length) {
      h += '<div style="font-size:12px;color:#888;margin-bottom:6px">共 ' + params.total_students + ' 名学生，显著障碍分布：</div>'
    }

    // CSS 柱状条 — 替代 ECharts
    if (Object.keys(barrier).length && vals.length) {
      var maxVal = isRawCount ? Math.max.apply(null, vals) : 1
      Object.keys(barrier).forEach(function (k) {
        var v = barrier[k] || 0
        var pct = Math.round((v / maxVal) * 100)
        var label = barrierLabels[k] || k
        var color = barrierColors[k] || '#b43c28'
        var displayVal = isRawCount ? v + '人' : Math.round(v * 100) + '%'
        h += '<div class="diag-bar-wrap">'
        h += '<span class="diag-bar-label">' + escHtml(label) + '</span>'
        h += '<div class="diag-bar-track"><div class="diag-bar-fill" style="width:' + pct + '%;background:' + color + '"></div></div>'
        h += '<span class="diag-bar-val" style="color:' + color + '">' + displayVal + '</span>'
        h += '</div>'
      })
    }

    // 答题统计
    if (params.total_answers !== undefined) {
      h += '<div style="margin-top:10px;border-top:1px solid #eee;padding-top:10px;display:flex;gap:16px;font-size:13px">'
      h += '<div>答题总数: <b>' + params.total_answers + '</b></div>'
      h += '<div>正确率: <b style="color:' + ((params.accuracy||0) >= 0.6 ? '#2c6e49' : '#b43c28') + '">' + Math.round((params.accuracy || 0) * 100) + '%</b></div>'
      h += '</div>'
    }

    // 薄弱知识点
    var wkps = params.weak_knowledge_points || []
    if (wkps.length) {
      h += '<div style="margin-top:8px;border-top:1px solid #eee;padding-top:8px">'
      h += '<div style="font-size:12px;color:#888;margin-bottom:4px">薄弱知识点</div>'
      h += '<div style="display:flex;flex-wrap:wrap;gap:4px">'
      wkps.forEach(function(k) {
        h += '<span style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;background:#fef2f2;color:#b43c28;border:1px solid #fecaca">' + escHtml(k.name) + ' ×' + k.errors + '</span>'
      })
      h += '</div></div>'
    }

    // 成绩趋势 — ECharts 折线图，和學生详情页一致
    var trend = params.score_trend || []
    if (trend.length) {
      h += '<div style="margin-top:8px;border-top:1px solid #eee;padding-top:8px">'
      h += '<div style="font-size:12px;color:#888;margin-bottom:4px">成绩趋势</div>'
      h += '<div class="inline-trend-chart" style="width:100%;height:140px" data-trend=\'' + JSON.stringify(trend) + '\'></div>'
      h += '</div>'
    }

    h += '<div style="margin-top:12px;border-top:1px solid #eee;padding-top:10px"><button onclick="ChemAI._diagToExam(this)" class="inline-exam-btn primary">针对障碍出题练习</button></div>'
    h += '</div>'

    bubble.insertAdjacentHTML('beforeend', h)

    // ECharts 折线图 — 成绩趋势（和學生详情页一致）
    var trendChartEl = bubble.querySelector('.inline-trend-chart')
    if (trendChartEl && typeof echarts !== 'undefined' && trend.length) {
      try {
        var chart = echarts.init(trendChartEl)
        var dates = trend.map(function(t) { return t.date || t.exam || '' })
        var rates = trend.map(function(t) { return Math.round((t.cumulative_rate || t.rate || 0) * 100) })
        chart.setOption({
          grid: { top: 8, right: 8, bottom: 20, left: 36 },
          xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 10, color: '#999' } },
          yAxis: { type: 'value', min: 0, max: 100, axisLabel: { fontSize: 10, color: '#999' } },
          series: [{
            type: 'line', data: rates,
            lineStyle: { color: '#b43c28', width: 2 },
            itemStyle: { color: '#b43c28' },
            areaStyle: { color: 'rgba(180,60,40,0.06)' },
            symbol: 'circle', symbolSize: 4
          }]
        })
      } catch(e) {
        trendChartEl.style.display = 'none'
      }
    }
  }

  window.ChemAI._diagToExam = function(btn){sendMessage('针对学习障碍出题练习')}

  // ─── Inline Learning Plan Panel ───
  function renderLearningPlanPanel(params, bubble) {
    var plan = params.plan_data || {}
    var h = '<style>'+
      '.lp-panel{background:#f8fcf9;border:1px solid #c8e0d0;border-radius:10px;padding:16px;margin:8px 0}'+
      '.lp-section{margin-top:10px;padding-top:10px;border-top:1px solid #e0ece0}'+
      '.lp-section-label{font-size:12px;font-weight:600;color:#2c6e49;margin-bottom:6px}'+
      '.lp-btn{display:inline-block;padding:6px 14px;border-radius:6px;font-size:12px;cursor:pointer;margin:2px;border:1px solid #ddd;background:#fff;color:#555;transition:all .15s}'+
      '.lp-btn:hover{background:#f5f5f5}'+
      '.lp-btn.primary{background:#2c6e49;color:#fff;border-color:#2c6e49;font-weight:600}'+
      '.lp-btn.primary:hover{background:#1e4d32}'+
      '.lp-btn.warn{background:#b43c28;color:#fff;border-color:#b43c28;font-weight:600}'+
      '.lp-btn.warn:hover{background:#9a3522}'+
      '.lp-edit-area{display:none;width:100%;min-height:200px;font-size:13px;font-family:inherit;padding:10px;border:1px solid #ddd;border-radius:6px;margin-top:8px;resize:vertical;box-sizing:border-box}'+
      '</style>'

    h += '<div class="lp-panel">'

    // Header
    var title = params.plan_title || plan.plan_title || '个性化学习计划'
    h += '<div style="font-weight:700;font-size:15px;color:#2c6e49;margin-bottom:4px">'+escHtml(title)+'</div>'
    h += '<div style="font-size:12px;color:#888">学生: '+escHtml(params.student_name||'') + (params.plan_period||plan.plan_period ? ' · 周期: '+escHtml(params.plan_period||plan.plan_period||'') : '')+'</div>'

    // Content blocks
    var weeks = params.weekly_goals || plan.weekly_goals || []
    var tasks = params.daily_tasks || plan.daily_tasks || []
    var barriers = params.barrier_interventions || plan.barrier_interventions || {}
    var tips = params.motivation_tips || plan.motivation_tips || []

    function lpContent() {
      var c = ''
      if (weeks.length) {
        c += '<div class="lp-section"><div class="lp-section-label">🎯 周目标</div>'
        weeks.forEach(function(w){ var g=typeof w==='string'?w:(w.milestone||w.goal||''); c+='<div style="padding:3px 0;font-size:13px;color:#444">• '+escHtml(g)+'</div>' })
        c += '</div>'
      }
      if (tasks.length) {
        c += '<div class="lp-section"><div class="lp-section-label">📅 每日任务</div>'
        tasks.slice(0,14).forEach(function(t){ var d=t.day||'',tx=t.task||t.content||(typeof t==='string'?t:''); c+='<div style="padding:2px 0;font-size:13px;color:#444"><span style="font-family:JetBrains Mono;font-size:11px;color:#2c6e49">'+escHtml(d)+'</span> '+escHtml(tx)+'</div>' })
        c += '</div>'
      }
      if (!Array.isArray(barriers) && typeof barriers==='object' && Object.keys(barriers).length) {
        c += '<div class="lp-section"><div class="lp-section-label">🧠 障碍干预</div>'
        var bl={concept:'概念理解',reading:'审题仔细',expression:'答题表述'}
        Object.keys(barriers).forEach(function(b){ c+='<div style="padding:2px 0;font-size:13px;color:#444"><b>'+escHtml(bl[b]||b)+'</b>: '+escHtml(barriers[b])+'</div>' })
        c += '</div>'
      }
      if (tips.length) {
        c += '<div class="lp-section"><div class="lp-section-label">💡 激励建议</div>'
        tips.forEach(function(t){ var tx=typeof t==='string'?t:(t.tip||t.text||''); c+='<div style="padding:2px 0;font-size:13px;color:#444">• '+escHtml(tx)+'</div>' })
        c += '</div>'
      }
      return c
    }

    h += '<div class="lp-content">'+lpContent()+'</div>'
    h += '<textarea class="lp-edit-area" id="lp-edit-'+Date.now()+'"></textarea>'

    // Buttons
    var sid = params.student_id || ''
    var sname = params.student_name || ''
    h += '<div class="lp-section">'
    h += '<button class="lp-btn" onclick="ChemAI._editPlan(this)">✏ 修改</button>'
    h += '<button class="lp-btn warn" onclick="ChemAI._sendPlan(this,\''+sid+'\',\''+escHtml(sname)+'\')" style="margin-left:8px">📤 发送给学生</button>'
    h += '</div>'
    h += '</div>'

    bubble.insertAdjacentHTML('beforeend', h)
  }

  window.ChemAI._editPlan = function(btn) {
    var panel = btn.closest('.lp-panel')
    var content = panel.querySelector('.lp-content')
    var editArea = panel.querySelector('.lp-edit-area')
    if (editArea.style.display === 'block') {
      editArea.style.display = 'none'
      content.style.display = 'block'
      btn.textContent = '✏ 修改'
    } else {
      // Populate edit area with content text
      editArea.value = content.innerText || content.textContent || ''
      editArea.style.display = 'block'
      content.style.display = 'none'
      btn.textContent = '✓ 完成修改'
    }
  }

  window.ChemAI._sendPlan = function(btn, sid, sname) {
    var panel = btn.closest('.lp-panel')
    // Check if in edit mode
    var editArea = panel.querySelector('.lp-edit-area')
    var planText = editArea.style.display === 'block' ? editArea.value : (panel.querySelector('.lp-content').innerText || '')
    btn.disabled = true; btn.textContent = '发送中...'
    sendMessage('将以下学习方案发送给学生 '+sname+'（学号'+sid+'）：\n'+planText.substring(0,500))
  }

  // ─── Inline Student List Panel ───
  function renderStudentList(params, bubble) {
    var students = params.students || []
    var className = params.class_name || params.class_id || ''
    var barrierLabels = {concept:'计算能力', reading:'审题障碍', expression:'表述障碍', unknown:'未诊断'}

    function barrierColor(score) {
      if (score >= 0.7) return '#b43c28'   // red
      if (score >= 0.3) return '#d4a017'   // yellow
      return '#2c6e49'                      // green
    }

    var html = '<style>'+
      '.sl-search{width:100%;padding:8px 12px;border:1.5px solid #e0e0e0;border-radius:6px;font-size:13px;box-sizing:border-box;margin-bottom:8px;outline:none}'+
      '.sl-search:focus{border-color:#b43c28}'+
      '.sl-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px}'+
      '.sl-card{display:flex;align-items:center;gap:8px;padding:8px 10px;border:1.5px solid #eee;border-radius:8px;cursor:pointer;transition:all .15s;background:#fff;font-size:13px}'+
      '.sl-card:hover{border-color:#ccc;background:#fafafa}'+
      '.sl-card.selected{border-color:#b43c28;background:rgba(180,60,40,.04)}'+
      '.sl-barrier-tag{padding:1px 8px;border-radius:12px;font-size:10px;font-weight:600;font-family:\'JetBrains Mono\',monospace;white-space:nowrap}'+
      '.sl-scroll{max-height:360px;overflow-y:auto}'+
      '</style>'+
      '<div class="inline-sl-panel" style="border:1px solid #eee;border-radius:8px;padding:12px;margin:8px 0">'+
      '<div style="font-weight:700;margin-bottom:10px;font-size:15px;border-bottom:2px solid #b43c28;padding-bottom:8px">' + escHtml(className) + ' · ' + students.length + '名学生</div>'+
      '<input class="sl-search" placeholder="搜索姓名或学号..." oninput="var v=this.value.toLowerCase();this.parentNode.querySelectorAll(\'.sl-card\').forEach(function(c){c.style.display=(c.textContent||\'\').toLowerCase().indexOf(v)===-1?\'none\':\'flex\'})">'+
      '<div class="sl-scroll sl-grid">'

    var barrierBg = function(score) { var c=barrierColor(score); return 'background:'+c+'14;color:'+c+';border:1px solid '+c+'33' }

    students.forEach(function(s) {
      var label = barrierLabels[s.dominant_barrier] || s.dominant_barrier
      var bg = barrierBg(s.barrier_score)
      html += '<div class="sl-card" data-sid="' + escHtml(s.student_id) + '" data-sname="' + escHtml(s.name) + '">' +
        '<div style="flex:1;min-width:0">' +
        '<div style="font-weight:600;font-size:14px">' + escHtml(s.name) + '</div>' +
        '<div style="font-size:11px;color:#999;font-family:\'JetBrains Mono\',monospace\">' + escHtml(s.student_id) + '</div>' +
        '</div>' +
        '<span class="sl-barrier-tag" style="' + bg + '">' + label + ' ' + Math.round(s.barrier_score * 100) + '%</span>' +
        '<span style="font-size:11px;color:#999;white-space:nowrap">练习: ' + s.exercises_completed + '</span>' +
        '</div>'
    })

    html += '</div></div>'

    bubble.insertAdjacentHTML('beforeend', html)

    // Click to select student → send targeted diagnosis with student ID
    var panel = bubble.querySelector('.inline-sl-panel:last-child')
    if (!panel) return
    panel.querySelectorAll('.sl-card').forEach(function(card) {
      card.addEventListener('click', function() {
        panel.querySelectorAll('.sl-card.selected').forEach(function(c) { c.classList.remove('selected') })
        card.classList.add('selected')
        var sid = card.dataset.sid
        var name = card.dataset.sname
        sendMessage('诊断学生 ' + sid + ' ' + name)
      })
    })
  }

  // ── 清理非教师对话 (m-/p- 前缀是学生/家长的) ──
  setTimeout(function() {
    var convs = getConversations()
    var cleaned = convs.filter(function(c) {
      var id = (c.id || c.thread_id || '') + ''
      // 保留教师对话 (t- / c 前缀) 和无前缀的老对话, 删学生(m-)和家长(p-)
      return !id.startsWith('m-') && !id.startsWith('p-')
    })
    if (cleaned.length < convs.length) {
      saveConversations(cleaned)
      refreshSidebarConvs()
    }
  }, 500)
  // ── 初始化: 从服务端同步对话列表 ──
  setTimeout(syncFromServer, 200)
})()

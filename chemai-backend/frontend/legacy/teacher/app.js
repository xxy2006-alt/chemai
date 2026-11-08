/**
 * ChemAI — 全局应用逻辑
 * 认证检查 / 侧边栏渲染 / fetch token 注入 / 页面路由
 */
(function () {
  'use strict'

  // ─── 图标字体预加载（防止各页面漏加导致乱码）───
  if (!document.querySelector('link[href*="Material+Symbols"]')) {
    var _iconLink = document.createElement('link')
    _iconLink.rel = 'stylesheet'
    _iconLink.href = 'https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap'
    document.head.appendChild(_iconLink)
  }

  // ─── 认证检查 ───
  var user = getUser()
  if (!user) { window.location.href = '/login.html'; return }

  // ─── fetch 拦截：自动注入 token ───
  var _fetch = window.fetch
  window.fetch = function (url, opts) {
    opts = opts || {}
    var u = typeof url === 'string' ? url : (url.url || '')
    if (u.indexOf('/api/') >= 0) {
      var token = getToken()
      if (token) {
        opts.headers = opts.headers || {}
        if (opts.headers instanceof Headers) {
          if (!opts.headers.has('Authorization'))
            opts.headers = Object.assign({ Authorization: 'Bearer ' + token }, Object.fromEntries(opts.headers.entries()))
        } else if (!opts.headers.Authorization && !opts.headers['Authorization']) {
          opts.headers['Authorization'] = 'Bearer ' + token
        }
      }
    }
    return _fetch.call(this, url, opts)
  }

  // ─── 侧边栏渲染 ───
  function renderSidebar(active) {
    var html = ''

    if (active === 'chat') {
      // Chat page: conversation history + compact manual nav
      var convs = []
      try { convs = JSON.parse(sessionStorage.getItem('chemai_convs') || '[]') } catch(e) {}
      convs.sort(function(a, b) { return (b.updated || 0) - (a.updated || 0) })

      if (convs.length) {
        html += '<div style="padding:0 8px;margin-bottom:4px"><span style="font-family:\'JetBrains Mono\',monospace;font-size:9px;color:#999;text-transform:uppercase;letter-spacing:.5px">对话历史</span></div>'
        html += '<div style="flex:1;overflow-y:auto;padding:0 4px" id="conv-list">'
        convs.forEach(function(c) {
          html += '<div class="history-item' + (c.id === window.__activeConvId ? ' active' : '') + '" onclick="loadConversation(\'' + c.id + '\')">' +
            '<span class="title" style="font-family:\'IBM Plex Sans\',sans-serif;font-size:13px">' + escHtml(c.title || '新对话') + '</span>' +
            '<button class="del" onclick="event.stopPropagation();deleteConversation(\'' + c.id + '\')" title="删除">×</button></div>'
        })
        html += '</div>'
      } else {
        html += '<div style="flex:1;overflow-y:auto;padding:0 4px" id="conv-list"><div style="padding:20px 12px;text-align:center;color:#999;font-size:13px;font-family:\'IBM Plex Sans\',sans-serif">暂无对话记录</div></div>'
      }

      // Compact manual nav — 5 icon buttons
      html += '<div style="display:flex;justify-content:center;gap:6px;padding:8px;border-top:1px solid rgba(0,0,0,.04);margin-top:auto">' +
        '<a href="/pages/ocr.html" title="答题卡识别" style="display:flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:4px;color:#555;text-decoration:none;transition:.15s" onmouseover="this.style.background=\'rgba(0,0,0,.03)\'" onmouseout="this.style.background=\'transparent\'"><span class="material-symbols-outlined" style="font-size:19px">document_scanner</span></a>' +
        '<a href="/pages/exam-v2.html" title="考试工作台" style="display:flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:4px;color:#555;text-decoration:none;transition:.15s" onmouseover="this.style.background=\'rgba(0,0,0,.03)\'" onmouseout="this.style.background=\'transparent\'"><span class="material-symbols-outlined" style="font-size:19px">edit_note</span></a>' +
        '<a href="/pages/diagnosis.html" title="障碍诊断" style="display:flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:4px;color:#555;text-decoration:none;transition:.15s" onmouseover="this.style.background=\'rgba(0,0,0,.03)\'" onmouseout="this.style.background=\'transparent\'"><span class="material-symbols-outlined" style="font-size:19px">clinical_notes</span></a>' +
        '<a href="/pages/teacher.html" title="学情面板" style="display:flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:4px;color:#555;text-decoration:none;transition:.15s" onmouseover="this.style.background=\'rgba(0,0,0,.03)\'" onmouseout="this.style.background=\'transparent\'"><span class="material-symbols-outlined" style="font-size:19px">monitoring</span></a>' +
        '<a href="/pages/students.html" title="学生管理" style="display:flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:4px;color:#555;text-decoration:none;transition:.15s" onmouseover="this.style.background=\'rgba(0,0,0,.03)\'" onmouseout="this.style.background=\'transparent\'"><span class="material-symbols-outlined" style="font-size:19px">group</span></a>' +
        '</div>'
    } else {
      // Other pages: same compact icon nav as chat mode
      html += '<div style="padding:0 8px;margin-bottom:4px"><span style="font-family:\'JetBrains Mono\',monospace;font-size:9px;color:#999;text-transform:uppercase;letter-spacing:.5px">快捷导航</span></div>'
      html += '<div style="display:flex;justify-content:center;gap:6px;padding:8px;border-top:1px solid rgba(0,0,0,.04);margin-top:auto">' +
        '<a href="/" title="AI 教研助手" style="display:flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:4px;color:#555;text-decoration:none;transition:.15s" onmouseover="this.style.background=\'rgba(0,0,0,.03)\'" onmouseout="this.style.background=\'transparent\'"><span class="material-symbols-outlined" style="font-size:19px">psychology</span></a>' +
        '<a href="/pages/ocr.html" title="答题卡识别" style="display:flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:4px;color:#555;text-decoration:none;transition:.15s" onmouseover="this.style.background=\'rgba(0,0,0,.03)\'" onmouseout="this.style.background=\'transparent\'"><span class="material-symbols-outlined" style="font-size:19px">document_scanner</span></a>' +
        '<a href="/pages/exam-v2.html" title="考试工作台" style="display:flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:4px;color:#555;text-decoration:none;transition:.15s" onmouseover="this.style.background=\'rgba(0,0,0,.03)\'" onmouseout="this.style.background=\'transparent\'"><span class="material-symbols-outlined" style="font-size:19px">edit_note</span></a>' +
        '<a href="/pages/diagnosis.html" title="障碍诊断" style="display:flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:4px;color:#555;text-decoration:none;transition:.15s" onmouseover="this.style.background=\'rgba(0,0,0,.03)\'" onmouseout="this.style.background=\'transparent\'"><span class="material-symbols-outlined" style="font-size:19px">clinical_notes</span></a>' +
        '<a href="/pages/teacher.html" title="学情面板" style="display:flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:4px;color:#555;text-decoration:none;transition:.15s" onmouseover="this.style.background=\'rgba(0,0,0,.03)\'" onmouseout="this.style.background=\'transparent\'"><span class="material-symbols-outlined" style="font-size:19px">monitoring</span></a>' +
        '<a href="/pages/students.html" title="学生管理" style="display:flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:4px;color:#555;text-decoration:none;transition:.15s" onmouseover="this.style.background=\'rgba(0,0,0,.03)\'" onmouseout="this.style.background=\'transparent\'"><span class="material-symbols-outlined" style="font-size:19px">group</span></a>' +
        '</div>'
    }

    var sidebar = document.getElementById('sidebar-nav')
    if (sidebar) sidebar.innerHTML = html
  }

  function escHtml(s) { if (!s) return ''; return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;') }

  // ─── 用户信息渲染 ───
  function renderUser() {
    var el = document.getElementById('user-name')
    if (el) el.textContent = user.name || '教师'
    var el2 = document.getElementById('user-role')
    if (el2) el2.textContent = user.school || '智辅化学'
  }

  // ─── 辅助函数 ───
  function getUser() {
    try { return JSON.parse(sessionStorage.getItem('chemai_user')) } catch (e) { return null }
  }
  function getToken() {
    var u = getUser(); return u ? u.token : ''
  }

  // ─── 最近活动追踪 ───
  function getActivities() {
    try { return JSON.parse(sessionStorage.getItem('chemai_activities') || '[]') } catch (e) { return [] }
  }
  function trackActivity(type, summary) {
    var acts = getActivities()
    acts.unshift({ type: type, summary: summary, time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) })
    if (acts.length > 5) acts.length = 5
    sessionStorage.setItem('chemai_activities', JSON.stringify(acts))
  }
  function renderActivities() {
    var acts = getActivities()
    var container = document.getElementById('recent-activity')
    var list = document.getElementById('recent-activity-list')
    if (!container || !list) return
    if (!acts.length) { container.style.display = 'none'; return }
    container.style.display = 'block'
    var icons = { chat: 'psychology', exam: 'assignment', diagnosis: 'health_and_safety', ocr: 'document_scanner', students: 'group', plan: 'description' }
    list.innerHTML = acts.map(function (a) {
      return '<div class="flex items-center gap-2 text-xs" style="padding:4px 8px;color:rgba(255,255,255,.4)">' +
        '<span class="material-symbols-outlined text-[14px]" style="color:rgba(255,255,255,.3)">' + (icons[a.type] || 'circle') + '</span>' +
        '<span style="flex:1;color:rgba(255,255,255,.5);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + escHtmlS(a.summary) + '</span>' +
        '<span style="font-family:JetBrains Mono;color:rgba(255,255,255,.35)">' + (a.time || '') + '</span>' +
        '</div>'
    }).join('')
  }
  function escHtmlS(s) { if (!s) return ''; return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') }

  // ─── 暴露到全局 ───
  window.ChemAI = {
    user: user,
    renderSidebar: renderSidebar,
    renderUser: renderUser,
    getToken: getToken,
    getUser: getUser,
    trackActivity: trackActivity,
    logout: function () { sessionStorage.removeItem('chemai_user'); window.location.href = '/login.html' }
  }

  // ─── 页面加载时自动渲染 ───
  document.addEventListener('DOMContentLoaded', function () {
    renderUser()
    // 根据路径判断 active
    var path = window.location.pathname
    var active = 'chat'
    if (path.indexOf('ocr') >= 0) active = 'ocr'
    else if (path.indexOf('exam') >= 0) active = 'exam'
    else if (path.indexOf('diagnosis') >= 0) active = 'diagnosis'
    else if (path.indexOf('teacher') >= 0) active = 'teacher'
    else if (path.indexOf('students') >= 0) active = 'students'
    renderSidebar(active)
    renderActivities()
  })
})()

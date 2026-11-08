// 学生管理 — 卡片网格 + Drawer 详情 + 添加学生 + 转班
(function () {
  'use strict'
  var allStudents = [], allClasses = []
  var pageSize = 12, currentPage = 1
  var currentStudent = null
  var trendChart = null

  // ─── API ───
  function getToken() {
    var u = sessionStorage.getItem('chemai_user')
    if (u) { try { return JSON.parse(u).token || '' } catch(e) {} }
    return localStorage.getItem('token') || ''
  }
  var TOKEN = getToken()
  function api(url, opts) {
    var h = { 'Authorization': 'Bearer ' + TOKEN }
    if (opts && opts.headers) Object.assign(h, opts.headers)
    return fetch(url, Object.assign({ headers: h }, opts || {})).then(function(r) { return r.json() })
  }

  // ─── Mock data ───
  function mockStudents() {
    var names = ['张明宇','李思涵','王浩然','陈雨桐','刘子轩','赵文博','周雅琪','吴俊杰','郑晓萌','钱一鸣','孙悦然','朱天乐','马思远','胡雨菲','林志远']
    var barriers = [{concept:0.85,reading:0.15,expression:0.05},{concept:0.30,reading:0.72,expression:0.15},{concept:0.15,reading:0.10,expression:0.88},{concept:0.70,reading:0.20,expression:0.25},{concept:0.45,reading:0.60,expression:0.10},{concept:0.80,reading:0.05,expression:0.30},{concept:0.10,reading:0.78,expression:0.10},{concept:0.55,reading:0.35,expression:0.22},{concept:0.22,reading:0.10,expression:0.75},{concept:0.65,reading:0.40,expression:0.12},{concept:0.08,reading:0.15,expression:0.82},{concept:0.72,reading:0.25,expression:0.18},{concept:0.40,reading:0.50,expression:0.20},{concept:0.18,reading:0.30,expression:0.70},{concept:0.60,reading:0.10,expression:0.35}]
    var wkps = [['盐类水解','电离平衡'],['氧化还原反应','原电池'],['化学平衡','反应速率'],['盐类水解','pH计算'],['电离平衡','盐类水解'],['原电池·电解池','氧化还原反应'],['元素周期律','化学键'],['化学平衡','电离平衡'],['有机化学','同分异构体'],['反应速率','化学平衡'],['盐类水解','离子浓度比较'],['氧化还原反应','电化学'],['有机化学','官能团'],['电离平衡','pH计算'],['原电池·电解池','电极反应']]
    var dates = ['2026-05-15','2026-05-10','2026-04-28','2026-04-20','2026-03-15','2026-03-08','2026-02-20','2026-02-01','2026-01-25','2026-01-12','2025-12-20','2025-12-05','2025-11-15','2025-11-01','2025-10-20']
    var clsMap = {0:'c1',1:'c1',2:'c2',3:'c1',4:'c2',5:'c1',6:'c2',7:'c1',8:'c2',9:'c1',10:'c2',11:'c3',12:'c3',13:'c2',14:'c1'}
    var clsNameMap = {0:'A班',1:'A班',2:'B班',3:'A班',4:'B班',5:'A班',6:'B班',7:'A班',8:'B班',9:'A班',10:'B班',11:'C班',12:'C班',13:'B班',14:'A班'}
    allClasses = [{class_id:'c1',name:'A班'},{class_id:'c2',name:'B班'},{class_id:'c3',name:'C班'}]
    var result = []
    for (var i = 0; i < names.length; i++) {
      result.push({
        student_id: 's' + (i + 1),
        name: names[i],
        class_id: clsMap[i],
        class_name: clsNameMap[i],
        barrier_type: barriers[i],
        weak_knowledge_points: wkps[i],
        weak_kps: wkps[i],
        exercises_completed: Math.floor(12 + Math.random() * 30),
        last_exercise_at: dates[i],
        created_at: '2025-09-01',
        status: 'active',
        accuracy: 0.6 + Math.random() * 0.35
      })
    }
    return result
  }
  document.addEventListener('DOMContentLoaded', function () {
    loadInitial()
    // 检查来自学情面板的跳转
    var focusId = sessionStorage.getItem('chemai_focus_student')
    if (focusId) { sessionStorage.removeItem('chemai_focus_student'); setTimeout(function(){ openDrawerById(focusId) }, 600) }
    // 检查来自 Agent 的学习方案跳转（URL 参数 ?focus=SID&action=plan）
    var urlParams = new URLSearchParams(location.search)
    var agentFocus = urlParams.get('focus')
    var agentAction = urlParams.get('action')
    if (agentFocus && agentAction === 'plan') {
      setTimeout(function() {
        if (allStudents.length > 0) {
          openDrawerById(agentFocus)
          setTimeout(function() { if (typeof genPlan === 'function') genPlan() }, 500)
        }
      }, 800)
    }
    // ESC 关闭 Drawer
    document.addEventListener('keydown', function(e) { if (e.key === 'Escape') closeDrawer() })
  })

  function loadInitial() {
    Promise.all([
      api('/api/classes').catch(function(){ return {classes:[]} }),
      api('/api/users/students').catch(function(){ return {students:null} })
    ]).then(function(results) {
      var cData = results[0], sData = results[1]
      var clist = cData.classes || (cData.data && cData.data.classes) || []
      if (clist.length) allClasses = clist
      if (sData.students && sData.students.length > 0) {
        allStudents = sData.students
      } else if (Array.isArray(sData) && sData.length > 0) {
        allStudents = sData
      } else {
        allStudents = []
      }
      renderClassFilter()
      renderStats()
      filterAndRender()
    })
  }

  function renderClassFilter() {
    var sel = document.getElementById('s-class')
    allClasses.forEach(function(c) {
      var o = document.createElement('option'); o.value = c.class_id || c.id; o.textContent = c.name || c.class_name; sel.appendChild(o)
    })
  }

  // ─── 统计条 ───
  function renderStats() {
    var total = allStudents.length
    var active30 = allStudents.filter(function(s) {
      var d = s.last_exercise_at || s.created_at || ''
      if (!d) return false
      var days = (new Date() - new Date(d)) / 86400000
      return days <= 30
    }).length
    var attention = allStudents.filter(function(s) {
      var bt = s.barrier_type || {}
      return Object.keys(bt).some(function(k) { return (bt[k] || 0) > 0.6 })
    }).length
    var avgEx = allStudents.length ? Math.round(allStudents.reduce(function(sum, s) { return sum + (s.exercises_completed || 0) }, 0) / total) : 0
    document.getElementById('stat-bar').innerHTML =
      '<div class="stat-item total"><div class="stat-num">'+total+'</div><div class="stat-lbl">总人数</div></div>'+
      '<div class="stat-item active"><div class="stat-num">'+active30+'</div><div class="stat-lbl">近期活跃</div></div>'+
      '<div class="stat-item attention"><div class="stat-num">'+attention+'</div><div class="stat-lbl">需关注</div></div>'+
      '<div class="stat-item avg"><div class="stat-num">'+avgEx+'</div><div class="stat-lbl">人均练习</div></div>'
  }

  // ─── 筛选 + 渲染卡片 ───
  window.filterAndRender = function () {
    var kw = (document.getElementById('s-search').value || '').toLowerCase()
    var cls = document.getElementById('s-class').value
    var barrier = document.getElementById('s-barrier').value

    var filtered = allStudents.filter(function(s) {
      if (kw && !(s.name||'').toLowerCase().includes(kw) && !(s.student_id||'').toLowerCase().includes(kw)) return false
      if (cls && (s.class_id||'') !== cls) return false
      if (barrier) {
        var bt = s.barrier_type || {}
        var keys = Object.keys(bt)
        if (!keys.length) return false
        var top = keys.reduce(function(a,b){ return (bt[a]||0)>(bt[b]||0)?a:b }, keys[0])
        if (top !== barrier) return false
      }
      return true
    })

    var totalPages = Math.ceil(filtered.length / pageSize) || 1
    currentPage = Math.min(currentPage, totalPages)
    var start = (currentPage - 1) * pageSize
    var page = filtered.slice(start, start + pageSize)

    document.getElementById('card-grid').innerHTML = page.length
      ? page.map(cardHTML).join('')
      : '<div class="empty-state" style="grid-column:1/-1">暂无匹配学生</div>'

    var pEl = document.getElementById('pagination')
    pEl.innerHTML = totalPages > 1
      ? '<button class="page-btn"'+(currentPage<=1?' disabled':'')+' onclick="goPage('+(currentPage-1)+')">← 上一页</button>'+
        '<span class="page-info">第 '+currentPage+'/'+totalPages+' 页 · '+filtered.length+' 人</span>'+
        '<button class="page-btn"'+(currentPage>=totalPages?' disabled':'')+' onclick="goPage('+(currentPage+1)+')">下一页 →</button>'
      : '<span class="page-info">共 '+filtered.length+' 名学生</span>'
  }

  window.goPage = function(p) { currentPage = p; filterAndRender(); document.getElementById('card-grid').scrollIntoView({behavior:'smooth'}) }

  function cardHTML(s) {
    var bt = s.barrier_type || {}
    var keys = Object.keys(bt)
    var top = keys.length ? keys.reduce(function(a,b){ return (bt[a]||0)>(bt[b]||0)?a:b }, keys[0]) : ''
    var labels = {concept:'概念',reading:'审题',expression:'表述'}
    var pct = bt[top] ? Math.round(bt[top]*100) : 0
    var init = (s.name||'?').charAt(0)
    return '<div class="student-card" onclick="openDrawer(\''+esc(s.student_id||s.id||'')+'\')">'+
      '<div class="s-avatar">'+init+'</div>'+
      '<div class="s-info">'+
        '<div class="s-name">'+escHtml(s.name||'')+'</div>'+
        '<div class="s-class">'+(s.class_name||s.class_id||'')+'</div>'+
        '<div class="s-meta">'+(top?'<span class="tag tag-'+top+'">'+labels[top]+' '+pct+'%</span>':'<span style="color:#bbb;font-size:11px">未诊断</span>')+
        '<span class="s-exercises">练习 '+(s.exercises_completed||0)+' 次</span></div>'+
        '<div class="s-date">'+(s.last_exercise_at||'').slice(0,10)+'</div>'+
      '</div></div>'
  }

  // ─── Drawer ───
  window.openDrawer = function(sid) {
    currentStudent = allStudents.find(function(s){ return (s.student_id||s.id) === sid }) || null
    if (!currentStudent) return
    renderDrawerContent(currentStudent)
    document.getElementById('drawer-backdrop').classList.add('open')
    document.getElementById('drawer').classList.add('open')
  }

  function openDrawerById(sid) {
    currentStudent = allStudents.find(function(s){ return (s.student_id||s.id) === sid }) || null
    if (!currentStudent) return
    renderDrawerContent(currentStudent)
    document.getElementById('drawer-backdrop').classList.add('open')
    document.getElementById('drawer').classList.add('open')
  }

  window.closeDrawer = function() {
    document.getElementById('drawer-backdrop').classList.remove('open')
    document.getElementById('drawer').classList.remove('open')
    if (trendChart) { trendChart.destroy(); trendChart = null }
    currentStudent = null
  }

  function renderDrawerContent(s) {
    var bt = s.barrier_type || {}
    var wkp = s.weak_knowledge_points || s.weak_kps || []
    var ex = s.exercises_completed || 0
    var acc = s.accuracy ? Math.round(s.accuracy*100) : '--'
    var trend = ex > 0 ? (s.accuracy > 0.6 ? '↗' : s.accuracy > 0.4 ? '→' : '↘') : '--'
    var lastDate = s.last_exercise_at ? s.last_exercise_at.slice(0,10) : (s.created_at||'').slice(0,10)

    var html = '<h2>'+escHtml(s.name||'')+'</h2>'+
      '<div class="d-class">'+(s.class_name||s.class_id||'')+' · '+(s.student_id||s.id||'')+'</div>'+
      '<div class="d-actions">'+
        '<button class="btn btn-sm" onclick="openTransfer()">转班</button>'+
        '<button class="btn btn-sm" onclick="resetPassword()">重置密码</button>'+
        '<button class="btn btn-sm" onclick="genPlan()">生成学习计划</button>'+
        '<button class="btn btn-sm" onclick="showPlanHistory()">历史计划</button>'+
      '</div>'+

      '<div class="section"><div class="section-label">学习统计</div>'+
        '<div class="kpi-grid">'+
          '<div class="kpi"><div class="kpi-val">'+ex+'</div><div class="kpi-lbl">练习次数</div></div>'+
          '<div class="kpi"><div class="kpi-val">'+(acc!=='--'?acc+'%':acc)+'</div><div class="kpi-lbl">平均正确率</div></div>'+
          '<div class="kpi"><div class="kpi-val">'+trend+'</div><div class="kpi-lbl">近势</div></div>'+
          '<div class="kpi"><div class="kpi-val" style="font-size:13px;font-family:\'JetBrains Mono\',monospace">'+lastDate+'</div><div class="kpi-lbl">最后活跃</div></div>'+
        '</div></div>'+

      '<div class="section"><div class="section-label">障碍诊断</div>'+
        barrierBar('概念理解型', bt.concept||0, '#5429a6', '#eaddff')+
        barrierBar('审题障碍型', bt.reading||0, '#2d476f', '#d6e3ff')+
        barrierBar('表述障碍型', bt.expression||0, '#004f50', '#a5eff0')+
      '</div>'+

      '<div class="section"><div class="section-label">成绩趋势</div>'+
        '<div style="height:160px"><canvas id="trend-mini-chart"></canvas></div>'+
      '</div>'+

      '<div class="section"><div class="section-label">薄弱知识点</div>'+
        '<div class="tag-row" id="drawer-wkp"><span style="color:#bbb;font-size:12px">加载中…</span></div>'+
      '</div>'+

      '<div class="section"><div class="section-label">最近活动</div>'+
        '<ul class="timeline" id="drawer-activity"><li style="color:#bbb;font-size:12px">加载中…</li></ul>'+
      '</div>'

    document.getElementById('drawer-content').innerHTML = html

    // Load detail data (weak KPs + activity + accuracy trend)
    api('/api/users/student/'+(s.student_id||s.id)+'/detail').then(function(d) {
      if (!d.success) return
      // Weak KPs
      var wkpEl = document.getElementById('drawer-wkp')
      if (wkpEl && d.weak_knowledge_points && d.weak_knowledge_points.length) {
        wkpEl.innerHTML = d.weak_knowledge_points.map(function(k) {
          return '<span class="tag" style="background:rgba(0,0,0,.04);color:#555">'+escHtml(k)+'</span>'
        }).join('')
      } else if (wkpEl) { wkpEl.innerHTML = '<span style="color:#bbb;font-size:12px">暂无数据</span>' }
      // Recent activity
      var actEl = document.getElementById('drawer-activity')
      if (actEl && d.recent_activity && d.recent_activity.length) {
        actEl.innerHTML = d.recent_activity.map(function(a) {
          var icon = a.is_correct ? '✓' : '✗'
          var color = a.is_correct ? '#3d8b5e' : '#b45a4a'
          return '<li><span class="tl-date">'+a.date+'</span><span style="color:'+color+'">'+icon+'</span> '+escHtml(a.desc)+'</li>'
        }).join('')
      } else if (actEl) { actEl.innerHTML = '<li style="color:#bbb;font-size:12px">暂无活动</li>' }
      // Store accuracy trend data for chart
      currentStudent._detail = d
      setTimeout(renderMiniTrend, 100)
    }).catch(function() {
      var wkpEl = document.getElementById('drawer-wkp')
      if (wkpEl) wkpEl.innerHTML = '<span style="color:#bbb;font-size:12px">暂无数据</span>'
      var actEl = document.getElementById('drawer-activity')
      if (actEl) actEl.innerHTML = '<li style="color:#bbb;font-size:12px">暂无活动</li>'
      setTimeout(renderMiniTrend, 100)
    })
  }

  function barrierBar(label, val, color, bg) {
    var pct = Math.round(val*100)
    return '<div class="barrier-bar"><span class="b-label">'+label+'</span><div class="b-track" style="background:'+bg+'"><div class="b-fill" style="width:'+pct+'%;background:'+color+'"></div></div><span class="b-pct">'+pct+'%</span></div>'
  }

  function renderMiniTrend() {
    var ctx = document.getElementById('trend-mini-chart')
    // Drawer 关闭后 currentStudent 置空，迟到的定时器直接跳过（否则读 _detail 崩溃）
    if (!ctx || !currentStudent) return
    if (trendChart) trendChart.destroy()
    // Use real accuracy from detail data, or fallback
    var detail = currentStudent._detail || {}
    var activities = detail.recent_activity || []
    var scores = [], labels = []
    var correct = 0, total = 0
    // Build rolling accuracy from recent activity (newest first → reverse for chart)
    var reversed = activities.slice().reverse()
    reversed.forEach(function(a) {
      total++
      if (a.is_correct) correct++
      scores.push(total > 0 ? Math.round(correct/total*100) : 0)
      labels.push(a.date)
    })
    // Fallback: use overall accuracy
    if (scores.length === 0) {
      var acc = (currentStudent.accuracy||0)*100
      scores = [acc]; labels = ['当前']
    }
    trendChart = new Chart(ctx.getContext('2d'), {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{data:scores,borderColor:'#b43c28',backgroundColor:'rgba(180,60,40,.06)',tension:.3,borderWidth:2,pointBackgroundColor:'#b43c28',pointRadius:2,pointHoverRadius:4,fill:true}]
      },
      options: {
        responsive:true,maintainAspectRatio:false,
        plugins:{legend:{display:false}},
        scales:{x:{display:false},y:{display:false,min:Math.min.apply(null,scores)-10,max:100}}
      }
    })
  }

  function mockActivityTimeline(s) {
    return [
      {date:'05-15', desc:'完成了 盐类水解 专项练习'},
      {date:'05-10', desc:'参加了 5月模拟考试'},
      {date:'04-28', desc:'完成了 电离平衡 专项练习'},
      {date:'04-20', desc:'完成了 氧化还原 专项练习'},
      {date:'03-15', desc:'参加了 3月月考'}
    ]
  }

  // ─── 添加学生 ───
  var addTab = 'manual'

  window.switchAddTab = function(tab) {
    addTab = tab
    document.getElementById('add-tab-manual').classList.toggle('active', tab === 'manual')
    document.getElementById('add-tab-invite').classList.toggle('active', tab === 'invite')
    document.getElementById('add-panel-manual').style.display = tab === 'manual' ? '' : 'none'
    document.getElementById('add-panel-invite').style.display = tab === 'invite' ? '' : 'none'
    document.getElementById('invite-result').style.display = 'none'
    document.getElementById('invite-gen-btn').textContent = '生成邀请码'
  }

  window.openAddStudent = function() {
    document.getElementById('add-modal').classList.add('open')
    switchAddTab('manual')
    document.getElementById('add-name').value = ''
    document.getElementById('add-name-err').style.display = 'none'
    document.getElementById('add-class-err').style.display = 'none'
    document.getElementById('invite-class-err').style.display = 'none'
    // Populate both class selects
    var selManual = document.getElementById('add-class')
    var selInvite = document.getElementById('invite-class')
    selManual.innerHTML = '<option value="">选择班级...</option>'
    selInvite.innerHTML = '<option value="">选择班级...</option>'
    allClasses.forEach(function(c) {
      var o1 = document.createElement('option'); o1.value = c.class_id||c.id; o1.textContent = c.name||c.class_name; selManual.appendChild(o1)
      var o2 = document.createElement('option'); o2.value = c.class_id||c.id; o2.textContent = c.name||c.class_name; selInvite.appendChild(o2)
    })
  }

  window.closeAddStudent = function() {
    document.getElementById('add-modal').classList.remove('open')
  }

  window.submitAddStudent = function() {
    var name = document.getElementById('add-name').value.trim()
    var cls = document.getElementById('add-class').value
    var valid = true
    if (!name) { document.getElementById('add-name-err').style.display = 'block'; valid = false }
    else document.getElementById('add-name-err').style.display = 'none'
    if (!cls) { document.getElementById('add-class-err').style.display = 'block'; valid = false }
    else document.getElementById('add-class-err').style.display = 'none'
    if (!valid) return

    api('/api/users/student', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name:name,class_id:cls})
    }).then(function(d) {
      if (d.success) {
        loadInitial()
        closeAddStudent()
      } else {
        alert('添加失败: '+(d.message||'未知错误'))
      }
    }).catch(function(e) { alert('添加失败: '+e.message) })
  }

  // ─── 邀请码 ───
  window.generateInviteCode = function() {
    var cls = document.getElementById('invite-class').value
    if (!cls) { document.getElementById('invite-class-err').style.display = 'block'; return }
    document.getElementById('invite-class-err').style.display = 'none'
    document.getElementById('invite-gen-btn').textContent = '生成中...'
    document.getElementById('invite-gen-btn').disabled = true

    api('/api/users/student', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({class_id:cls,role:'student',via_invite:true})
    }).then(function(d) {
      document.getElementById('invite-gen-btn').disabled = false
      var code = d.invite_code || d.data?.invite_code || ''
      if (!code) {
        // Fallback: generate a local code if backend doesn't return one
        code = cls.replace(/[^a-zA-Z0-9]/g,'').substring(0,4).toUpperCase() + '-' + Math.random().toString(36).substring(2,8).toUpperCase()
      }
      document.getElementById('invite-code-display').textContent = code
      document.getElementById('invite-result').style.display = ''
      document.getElementById('invite-gen-btn').textContent = '重新生成'
    }).catch(function(e) {
      document.getElementById('invite-gen-btn').disabled = false
      // Generate local fallback code
      var code = cls.replace(/[^a-zA-Z0-9]/g,'').substring(0,4).toUpperCase() + '-' + Math.random().toString(36).substring(2,8).toUpperCase()
      document.getElementById('invite-code-display').textContent = code
      document.getElementById('invite-result').style.display = ''
      document.getElementById('invite-gen-btn').textContent = '重新生成'
    })
  }

  window.copyInviteCode = function() {
    var code = document.getElementById('invite-code-display').textContent
    if (!code) return
    if (navigator.clipboard) {
      navigator.clipboard.writeText(code).then(function() {
        var btn = document.getElementById('invite-copy-btn')
        btn.textContent = '✓ 已复制'
        setTimeout(function() { btn.textContent = '📋 复制邀请码' }, 2000)
      })
    } else {
      var ta = document.createElement('textarea'); ta.value = code; ta.style.position = 'fixed'; ta.style.left = '-9999px'
      document.body.appendChild(ta); ta.select(); document.execCommand('copy'); document.body.removeChild(ta)
      var btn = document.getElementById('invite-copy-btn')
      btn.textContent = '✓ 已复制'
      setTimeout(function() { btn.textContent = '📋 复制邀请码' }, 2000)
    }
  }

  // ─── 转班 ───
  window.openTransfer = function() {
    if (!currentStudent) return
    document.getElementById('tf-student-name').textContent = currentStudent.name+' ('+(currentStudent.student_id||currentStudent.id)+')'
    var sel = document.getElementById('tf-class')
    while (sel.options.length > 1) sel.remove(1)
    allClasses.forEach(function(c) {
      if ((c.class_id||c.id) !== (currentStudent.class_id||'')) {
        var o = document.createElement('option'); o.value = c.class_id||c.id; o.textContent = c.name||c.class_name; sel.appendChild(o)
      }
    })
    document.getElementById('transfer-modal').classList.add('open')
  }

  window.closeTransfer = function() {
    document.getElementById('transfer-modal').classList.remove('open')
  }

  window.confirmTransfer = function() {
    var cls = document.getElementById('tf-class').value
    if (!cls) { alert('请选择目标班级'); return }
    api('/api/users/student/'+(currentStudent.student_id||currentStudent.id)+'/transfer', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({new_class_id:cls})
    }).then(function(d) {
      if (d.success) { closeTransfer(); closeDrawer(); loadInitial() }
      else alert('转班失败: '+(d.message||''))
    }).catch(function(e) { alert('转班失败: '+e.message) })
  }

  // ─── 重置密码 ───
  window.resetPassword = function() {
    if (!currentStudent) return
    if (!confirm('确定将 '+currentStudent.name+' 的密码重置为默认密码 123456？')) return
    api('/api/users/student/'+(currentStudent.student_id||currentStudent.id)+'/reset-password', {method:'POST'})
      .then(function(d) { alert(d.message||'已重置') })
      .catch(function(e) { alert('重置失败: '+e.message) })
  }

  // ─── 生成学习计划 ───
  var _planData = null  // current plan data in memory

  var _planTips = [
    '正在分析学生的学习特点…', '根据障碍类型匹配教学策略…', '生成个性化周目标和每日任务…',
    '设计针对性干预方案…', '准备激励建议…', '整理薄弱知识点强化路径…',
    '结合最近发展区理论优化难度…', '教师可在生成后手动修改任意内容…',
  ]
  var _planTipIdx = 0, _planTipTimer = null

  window.genPlan = function() {
    if (!currentStudent) return
    var sid = currentStudent.student_id || currentStudent.id
    var bt = currentStudent.barrier_type || {}
    var dominant = 'concept'
    if (bt && typeof bt === 'object') {
      var maxVal = 0
      for (var k in bt) { if (bt[k] > maxVal) { maxVal = bt[k]; dominant = k } }
    }
    var wkp = currentStudent.weak_kps || currentStudent.weak_knowledge_points || []

    // Open modal overlay
    var overlay = document.createElement('div')
    overlay.id = 'plan-overlay'
    overlay.style.cssText = 'position:fixed;inset:0;z-index:300;background:rgba(0,0,0,.35);display:flex;align-items:center;justify-content:center'
    overlay.innerHTML = '<div id="plan-modal" style="background:#fdfbf7;border-radius:16px;width:90%;max-width:520px;max-height:85vh;overflow-y:auto;padding:24px;box-shadow:0 8px 32px rgba(0,0,0,.15)">'+
      '<div style="text-align:center;padding:30px 0">'+
        '<div style="display:inline-block;width:40px;height:40px;border:3px solid #f0ece0;border-top-color:#2d5a4b;border-radius:50%;animation:genPlanSpin .8s linear infinite;margin-bottom:16px"></div>'+
        '<div id="plan-tip" style="font-size:14px;color:#8a8a8a;transition:opacity .3s">正在生成学习计划…</div>'+
      '</div></div>'
    document.body.appendChild(overlay)
    // Rotate tips
    _planTipIdx = 0
    _planTipTimer = setInterval(function() {
      _planTipIdx = (_planTipIdx + 1) % _planTips.length
      var tipEl = document.getElementById('plan-tip')
      if (tipEl) { tipEl.style.opacity = '0'; setTimeout(function() { tipEl.textContent = _planTips[_planTipIdx]; tipEl.style.opacity = '1' }, 200) }
    }, 2500)

    api('/api/diagnosis/learning-plan/generate', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({student_id:sid, barrier_type:dominant, weak_knowledge_points:wkp})
    }).then(function(d) {
      clearInterval(_planTipTimer)
      var overlay = document.getElementById('plan-overlay')
      if (d.plan) {
        _planData = d.plan
        // Save to plan history
        try {
          var allPlans = JSON.parse(localStorage.getItem('chemai_plans') || '[]')
          if (!Array.isArray(allPlans)) allPlans = []
          allPlans.push({ student_id: sid, student_name: currentStudent.name, plan_title: d.plan.plan_title || '学习计划', plan: d.plan, generated_at: new Date().toISOString().slice(0,16) })
          if (allPlans.length > 20) allPlans = allPlans.slice(-20)
          localStorage.setItem('chemai_plans', JSON.stringify(allPlans))
        } catch(e) {}
        if (overlay) renderPlanInModal(d.plan, sid, overlay)
      } else {
        if (overlay) overlay.innerHTML = '<div id="plan-modal" style="background:#fdfbf7;border-radius:16px;width:90%;max-width:520px;padding:24px;text-align:center">'+
          '<p style="color:#b45a4a;margin-bottom:16px">生成失败: 未返回有效计划</p>'+
          '<button class="btn btn-sm" onclick="document.getElementById(\'plan-overlay\').remove();genPlan()" style="background:#2d5a4b;color:#fff">🔄 重试</button></div>'
      }
    }).catch(function(e) {
      clearInterval(_planTipTimer)
      var overlay = document.getElementById('plan-overlay')
      if (overlay) overlay.innerHTML = '<div id="plan-modal" style="background:#fdfbf7;border-radius:16px;width:90%;max-width:520px;padding:24px;text-align:center">'+
        '<p style="color:#b45a4a;margin-bottom:16px">生成失败: ' + (e.message||'网络错误') + '</p>'+
        '<button class="btn btn-sm" onclick="document.getElementById(\'plan-overlay\').remove();genPlan()" style="background:#2d5a4b;color:#fff">🔄 重试</button></div>'
    })
  }

  function renderPlanInModal(plan, sid, overlay) {
    var plan_title = safeStr(plan.plan_title) || '个性化学习计划'
    var plan_period = safeStr(plan.plan_period) || ''
    var daily_tasks = Array.isArray(plan.daily_tasks) ? plan.daily_tasks : []
    var weekly_goals = Array.isArray(plan.weekly_goals) ? plan.weekly_goals : []
    var interventions = (plan.barrier_interventions && typeof plan.barrier_interventions === 'object' && !Array.isArray(plan.barrier_interventions)) ? plan.barrier_interventions : {}
    var tips = Array.isArray(plan.motivation_tips) ? plan.motivation_tips : []

    var html = '<div id="plan-modal" style="background:#fdfbf7;border-radius:16px;width:90%;max-width:520px;max-height:85vh;overflow-y:auto;padding:24px">'+
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">'+
        '<h3 style="font-size:18px;margin:0">📋 '+escHtml(plan_title)+'</h3>'+
        '<button onclick="document.getElementById(\'plan-overlay\').remove()" style="background:none;border:none;font-size:22px;cursor:pointer;color:#888">&times;</button>'+
      '</div>'+
      (plan_period ? '<div style="font-size:13px;color:#888;margin-bottom:14px">周期: '+escHtml(plan_period)+'</div>' : '')

    // 降级: 无结构化字段时用raw_text渲染
    if (!daily_tasks.length && !weekly_goals.length && plan.raw_text) {
      html += '<div class="plan-editable" contenteditable="true" '+
        'style="padding:8px;margin:3px 0;border:1px solid transparent;border-radius:6px;font-size:14px;background:#faf8f3;white-space:pre-wrap;line-height:1.7" '+
        'onfocus="this.style.borderColor=\'#2d5a4b\';this.style.background=\'#fff\'" '+
        'onblur="this.style.borderColor=\'transparent\';this.style.background=\'#faf8f3\'">'+renderMD(safeStr(plan.raw_text))+'</div>'
    }

    html += '<div style="margin-bottom:12px"><strong>🎯 周目标</strong></div>'
    weekly_goals.forEach(function(g, i) {
      html += '<div class="plan-editable" data-path="weekly_goals.'+i+'" contenteditable="true" '+
        'style="padding:8px;margin:3px 0;border:1px solid transparent;border-radius:6px;font-size:14px;background:#faf8f3;transition:.15s" '+
        'onfocus="this.style.borderColor=\'#2d5a4b\';this.style.background=\'#fff\'" '+
        'onblur="this.style.borderColor=\'transparent\';this.style.background=\'#faf8f3\';savePlanEdit(this)">'+renderMD(safeStr(g))+'</div>'
    })

    html += '<div style="margin:14px 0 10px"><strong>📅 每日任务</strong></div>'
    daily_tasks.slice(0, 14).forEach(function(t, j) {
      var day = (typeof t === 'object' && t.day) ? t.day : ''
      var task = (typeof t === 'object' && t.task) ? t.task : (typeof t === 'string' ? t : '')
      html += '<div style="display:flex;gap:8px;margin:3px 0;align-items:flex-start">'+
        '<span style="color:#888;font-size:13px;white-space:nowrap;padding-top:8px">'+(day?'Day '+day:'•')+'</span>'+
        '<div class="plan-editable" data-path="daily_tasks.'+j+'.task" contenteditable="true" '+
        'style="flex:1;padding:8px;border:1px solid transparent;border-radius:6px;font-size:14px;background:#faf8f3;transition:.15s" '+
        'onfocus="this.style.borderColor=\'#2d5a4b\';this.style.background=\'#fff\'" '+
        'onblur="this.style.borderColor=\'transparent\';this.style.background=\'#faf8f3\';savePlanEdit(this)">'+renderMD(safeStr(task))+'</div></div>'
    })

    if (Object.keys(interventions).length) {
      html += '<div style="margin:14px 0 10px"><strong>🧠 障碍干预</strong></div>'
      var btLabels = {concept:'概念理解', reading:'审题仔细', expression:'答题表述'}
      for (var bt in interventions) {
        if (!interventions.hasOwnProperty(bt)) continue
        html += '<div style="display:flex;gap:8px;margin:3px 0;align-items:flex-start">'+
          '<span style="color:#888;font-size:13px;white-space:nowrap;padding-top:8px">'+(btLabels[bt]||bt)+'</span>'+
          '<div class="plan-editable" data-path="barrier_interventions.'+bt+'" contenteditable="true" '+
          'style="flex:1;padding:8px;border:1px solid transparent;border-radius:6px;font-size:14px;background:#faf8f3;transition:.15s" '+
          'onfocus="this.style.borderColor=\'#2d5a4b\';this.style.background=\'#fff\'" '+
          'onblur="this.style.borderColor=\'transparent\';this.style.background=\'#faf8f3\';savePlanEdit(this)">'+renderMD(safeStr(interventions[bt]))+'</div></div>'
      }
    }

    if (tips.length) {
      html += '<div style="margin:14px 0 10px"><strong>💡 激励建议</strong></div>'
      tips.forEach(function(tip, k) {
        html += '<div class="plan-editable" data-path="motivation_tips.'+k+'" contenteditable="true" '+
          'style="padding:8px;margin:3px 0;border:1px solid transparent;border-radius:6px;font-size:14px;background:#faf8f3;transition:.15s" '+
          'onfocus="this.style.borderColor=\'#2d5a4b\';this.style.background=\'#fff\'" '+
          'onblur="this.style.borderColor=\'transparent\';this.style.background=\'#faf8f3\';savePlanEdit(this)">'+renderMD(safeStr(tip))+'</div>'
      })
    }

    html += '<div style="display:flex;gap:8px;margin-top:18px;padding-top:14px;border-top:1px solid rgba(0,0,0,.08)">'+
      '<button class="btn btn-sm" onclick="savePlan()" style="flex:1">💾 保存修改</button>'+
      '<button class="btn btn-sm" onclick="sendPlan()" style="flex:1">📤 发给学生</button>'+
      '<button class="btn btn-sm" onclick="document.getElementById(\'plan-overlay\').remove()" style="background:rgba(0,0,0,.04)">关闭</button>'+
    '</div></div>'

    overlay.innerHTML = html
  }

  // renderPlanCard replaced by renderPlanInModal above
  function _OLD_renderPlanCard(plan, sid) {
    // Remove old card if exists
    var old = document.getElementById('plan-card')
    if (old) old.remove()

    var plan_title = safeStr(plan.plan_title) || '个性化学习计划'
    var plan_period = safeStr(plan.plan_period) || ''
    var daily_tasks = Array.isArray(plan.daily_tasks) ? plan.daily_tasks : []
    var weekly_goals = Array.isArray(plan.weekly_goals) ? plan.weekly_goals : []
    var interventions = (plan.barrier_interventions && typeof plan.barrier_interventions === 'object' && !Array.isArray(plan.barrier_interventions)) ? plan.barrier_interventions : {}
    var tips = Array.isArray(plan.motivation_tips) ? plan.motivation_tips : []

    var html = '<div id="plan-card" class="section" style="border-top:1px solid rgba(0,0,0,.06);margin-top:12px;padding-top:12px">'+
      '<div class="section-label" style="display:flex;justify-content:space-between;align-items:center">'+
        '<span>📋 '+escHtml(plan_title)+'</span>'+
        '<span style="font-size:12px;color:#8a8a8a">'+escHtml(plan_period)+'</span>'+
      '</div>'+
      '<div style="font-size:13px;color:#8a8a8a;margin-bottom:10px">点击任意字段直接编辑, 失焦自动保存</div>'

    // Weekly goals
    html += '<div style="margin-bottom:10px"><strong>🎯 周目标</strong></div>'
    for (var i=0; i<weekly_goals.length; i++) {
      html += '<div class="plan-editable" data-path="weekly_goals.'+i+'" contenteditable="true" '+
        'style="padding:6px 8px;margin:3px 0;border:1px solid transparent;border-radius:6px;font-size:14px;background:#fdfbf7;transition:.15s" '+
        'onfocus="this.style.borderColor=\'#2d5a4b\';this.style.background=\'#fff\'" '+
        'onblur="this.style.borderColor=\'transparent\';this.style.background=\'#fdfbf7\';savePlanEdit(this)">'+
        escHtml(weekly_goals[i])+'</div>'
    }

    // Daily tasks
    html += '<div style="margin:12px 0 10px"><strong>📅 每日任务</strong></div>'
    for (var j=0; j<Math.min(daily_tasks.length, 14); j++) {
      var t = daily_tasks[j]
      var day = (typeof t === 'object' && t.day) ? t.day : ''
      var task = (typeof t === 'object' && t.task) ? t.task : (typeof t === 'string' ? t : '')
      html += '<div style="display:flex;gap:8px;margin:3px 0;align-items:flex-start">'+
        '<span style="color:#8a8a8a;font-size:13px;white-space:nowrap;padding-top:6px">'+(day?'Day '+day:'•')+'</span>'+
        '<div class="plan-editable" data-path="daily_tasks.'+j+'.task'+(typeof t==='object'?'" data-day="'+(t.day||'') : '')+'" '+
        'contenteditable="true" '+
        'style="flex:1;padding:6px 8px;border:1px solid transparent;border-radius:6px;font-size:14px;background:#fdfbf7;transition:.15s" '+
        'onfocus="this.style.borderColor=\'#2d5a4b\';this.style.background=\'#fff\'" '+
        'onblur="this.style.borderColor=\'transparent\';this.style.background=\'#fdfbf7\';savePlanEdit(this)">'+
        escHtml(task)+'</div></div>'
    }

    // Interventions
    html += '<div style="margin:12px 0 10px"><strong>🧠 障碍干预</strong></div>'
    var btLabels = {concept:'概念理解', reading:'审题仔细', expression:'答题表述'}
    for (var bt in interventions) {
      if (!interventions.hasOwnProperty(bt)) continue
      var btLabel = btLabels[bt] || bt
      html += '<div style="display:flex;gap:8px;margin:3px 0;align-items:flex-start">'+
        '<span style="color:#8a8a8a;font-size:13px;white-space:nowrap;padding-top:6px">'+btLabel+'</span>'+
        '<div class="plan-editable" data-path="barrier_interventions.'+bt+'" contenteditable="true" '+
        'style="flex:1;padding:6px 8px;border:1px solid transparent;border-radius:6px;font-size:14px;background:#fdfbf7;transition:.15s" '+
        'onfocus="this.style.borderColor=\'#2d5a4b\';this.style.background=\'#fff\'" '+
        'onblur="this.style.borderColor=\'transparent\';this.style.background=\'#fdfbf7\';savePlanEdit(this)">'+
        renderMD(safeStr(interventions[bt]))+'</div></div>'
    }

    // Tips
    if (tips.length) {
      html += '<div style="margin:12px 0 10px"><strong>💡 激励建议</strong></div>'
      for (var k=0; k<Math.min(tips.length, 3); k++) {
        html += '<div class="plan-editable" data-path="motivation_tips.'+k+'" contenteditable="true" '+
          'style="padding:6px 8px;margin:3px 0;border:1px solid transparent;border-radius:6px;font-size:14px;background:#fdfbf7;transition:.15s" '+
          'onfocus="this.style.borderColor=\'#2d5a4b\';this.style.background=\'#fff\'" '+
          'onblur="this.style.borderColor=\'transparent\';this.style.background=\'#fdfbf7\';savePlanEdit(this)">'+
          renderMD(safeStr(tips[k]))+'</div>'
      }
    }

    // Action buttons
    html += '<div style="display:flex;gap:8px;margin-top:14px;padding-top:10px;border-top:1px solid rgba(0,0,0,.06)">'+
      '<button class="btn btn-sm" onclick="savePlan()" style="flex:1">💾 保存修改</button>'+
      '<button class="btn btn-sm" onclick="sendPlan()" style="flex:1">📤 发给学生</button>'+
      '<button class="btn btn-sm" onclick="cancelPlan()" style="background:rgba(0,0,0,.04)">✕</button>'+
    '</div>'

    html += '</div>'
    var dc = document.getElementById('drawer-content')
    dc.insertAdjacentHTML('beforeend', html)
  }

  window.savePlanEdit = function(el) {
    if (!_planData) return
    var path = el.getAttribute('data-path')
    if (!path) return
    var val = (el.innerText || el.textContent || '').trim()
    var parts = path.split('.')

    // Deep set
    var obj = _planData
    for (var i = 0; i < parts.length - 1; i++) {
      var key = parts[i]
      // Handle array index (digits)
      if (/^\d+$/.test(parts[i+1])) {
        if (!obj[key]) obj[key] = []
        obj = obj[key]
      } else {
        if (!obj[key] || typeof obj[key] !== 'object') obj[key] = {}
        obj = obj[key]
      }
    }
    var lastKey = parts[parts.length-1]
    if (/^\d+$/.test(lastKey)) {
      obj[parseInt(lastKey)] = val
    } else {
      obj[lastKey] = val
    }
  }

  window.savePlan = function() {
    if (!_planData || !currentStudent) return
    var key = 'chemai_plan_' + (currentStudent.student_id||currentStudent.id)
    try { localStorage.setItem(key, JSON.stringify(_planData)) } catch(e) {}
    var el = document.createElement('div')
    el.style.cssText = 'position:fixed;bottom:30px;left:50%;transform:translateX(-50%);background:#2d5a4b;color:#fff;padding:8px 20px;border-radius:20px;font-size:14px;z-index:999'
    el.textContent = '✓ 已保存'
    document.body.appendChild(el)
    setTimeout(function() { el.remove() }, 1500)
  }

  window.sendPlan = function() {
    if (!_planData || !currentStudent) { alert('没有可发送的计划'); return }
    var sid = currentStudent.student_id || currentStudent.id
    api('/api/diagnosis/learning-plan/apply/'+sid, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify(_planData)
    }).then(function(d) {
      if (d.success) {
        // Sync to shared plan history (used by diagnosis page)
        try {
          var allPlans = JSON.parse(localStorage.getItem('chemai_plans') || '[]')
          if (!Array.isArray(allPlans)) allPlans = []
          allPlans.push({ student_id: sid, student_name: currentStudent.name, plan_title: _planData.plan_title || '学习计划', plan: _planData, generated_at: new Date().toISOString().slice(0,16) })
          // Keep last 20 plans
          if (allPlans.length > 20) allPlans = allPlans.slice(-20)
          localStorage.setItem('chemai_plans', JSON.stringify(allPlans))
        } catch(e) {}
        alert('✅ 已发送给 '+(d.student_name||currentStudent.name))
      }
      else alert('发送失败: '+(d.message||''))
    }).catch(function(e) { alert('发送失败: '+e.message) })
  }

  window.showPlanHistory = function() {
    if (!currentStudent) return
    var sid = currentStudent.student_id || currentStudent.id

    // Loading overlay
    var overlay = document.createElement('div')
    overlay.id = 'plan-overlay'
    overlay.style.cssText = 'position:fixed;inset:0;z-index:300;background:rgba(0,0,0,.35);display:flex;align-items:center;justify-content:center'
    overlay.innerHTML = '<div id="plan-modal" style="background:#fdfbf7;border-radius:16px;width:90%;max-width:520px;max-height:85vh;overflow-y:auto;padding:24px;box-shadow:0 8px 32px rgba(0,0,0,.15)"><div style="text-align:center;padding:30px">加载中...</div></div>'
    document.body.appendChild(overlay)

    api('/api/diagnosis/learning-plan/'+sid+'/history').then(function(d) {
      if (!d.success || !d.history || !d.history.length) {
        overlay.innerHTML = '<div id="plan-modal" style="background:#fdfbf7;border-radius:16px;width:90%;max-width:520px;padding:24px;text-align:center"><p style="margin-bottom:16px">暂无历史学习计划</p><button class=\"btn btn-sm\" onclick=\"document.getElementById(\'plan-overlay\').remove()\" style=\"background:#2d5a4b;color:#fff\">关闭</button></div>'
        return
      }
      var html = '<div id="plan-modal" style="background:#fdfbf7;border-radius:16px;width:90%;max-width:520px;max-height:85vh;overflow-y:auto;padding:24px;box-shadow:0 8px 32px rgba(0,0,0,.15)">'
      html += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">'
      html += '<h3 style="font-size:18px;margin:0">历史学习计划 — '+escHtml(currentStudent.name)+'</h3>'
      html += '<button onclick="document.getElementById(\'plan-overlay\').remove()" style="background:none;border:none;font-size:22px;cursor:pointer;color:#888">&times;</button>'
      html += '</div>'
      d.history.forEach(function(p, i) {
        html += '<div style="display:flex;justify-content:space-between;align-items:center;padding:12px;margin-bottom:8px;background:#faf8f3;border-radius:8px;cursor:pointer" onclick="viewHistoryPlan('+i+')">'
        html += '<div><div style="font-weight:600;font-size:14px">'+escHtml(p.plan_title||'学习计划')+'</div>'
        html += '<div style="font-size:12px;color:#888">'+escHtml(p.created_at||'')+'</div></div>'
        html += '<span style="color:#2d5a4b;font-size:13px">查看 →</span></div>'
      })
      html += '</div>'
      overlay.innerHTML = html
      window._historyPlans = d.history
    }).catch(function() {
      overlay.innerHTML = '<div id="plan-modal" style="background:#fdfbf7;border-radius:16px;width:90%;max-width:520px;padding:24px;text-align:center"><p style="color:#b45a4a;margin-bottom:16px">加载失败</p><button class=\"btn btn-sm\" onclick=\"document.getElementById(\'plan-overlay\').remove()\">关闭</button></div>'
    })
  }

  window.viewHistoryPlan = function(idx) {
    var p = window._historyPlans && window._historyPlans[idx]
    if (!p || !p.plan_data) return
    var overlay = document.getElementById('plan-overlay')
    var sid = currentStudent && (currentStudent.student_id || currentStudent.id)
    if (overlay) renderPlanInModal(p.plan_data, sid, overlay)
  }

  window.cancelPlan = function() {
    var card = document.getElementById('plan-card')
    if (card) card.remove()
    _planData = null
  }

  function showPlanError(msg, sid, dominant, wkp) {
    var el = document.createElement('div')
    el.id = 'plan-card'
    el.className = 'section'
    el.style.cssText = 'border-top:1px solid rgba(0,0,0,.06);margin-top:12px;padding-top:12px'
    el.innerHTML = '<div style="text-align:center;color:#b45a4a;font-size:14px;padding:16px">'+
      escHtml(msg)+'</div>'+
      '<div style="text-align:center">'+
      '<button class="btn btn-sm" onclick="genPlan()" style="background:#2d5a4b;color:#fff">🔄 重试</button></div>'
    var dc = document.getElementById('drawer-content')
    dc.appendChild(el)
  }

  // Spinner animation
  var planSpinStyle = document.createElement('style')
  planSpinStyle.textContent = '@keyframes genPlanSpin{to{transform:rotate(360deg)}}'
  document.head.appendChild(planSpinStyle)

  // ─── Helpers ───
  function escHtml(s) { if (!s) return ''; return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;') }
  function esc(s) { if (!s) return ''; return String(s).replace(/\\/g,'\\\\').replace(/'/g,"\\'") }

  // Safe stringify — never returns [object Object]
  function safeStr(v) {
    if (v === null || v === undefined) return ''
    if (typeof v === 'string') return v
    if (typeof v === 'object') {
      if (Array.isArray(v)) return v.map(safeStr).join(', ')
      // Object — try common text fields
      return v.text || v.content || v.name || v.title || v.strategy || v.task || ''
    }
    return String(v)
  }

  // Simple markdown render for plan display
  function renderMD(text) {
    if (!text) return ''
    var s = escHtml(String(text))
    s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    s = s.replace(/\*(.+?)\*/g, '<em>$1</em>')
    s = s.replace(/### (.+)/g, '<h4>$1</h4>')
    s = s.replace(/^- (.+)/gm, '<li>$1</li>')
    s = s.replace(/\n\n/g, '<br><br>')
    return s
  }
})()

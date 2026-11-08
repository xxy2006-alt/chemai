// 障碍诊断 — 班级概览 + 学生详情 + 学习计划管理
(function () {
  'use strict'
  var currentDiagnosis = null  // 当前诊断结果
  var currentExamId = null
  var currentClassId = null
  var savedPlans = {}  // localStorage keyed by student_id

  document.addEventListener('DOMContentLoaded', function () {
    loadPlans()
    loadClasses()

    // Agent page driver bridge
    var bridge = window.__chemai_bridge
    if (bridge) {
      // Actions
      if (bridge.actions) {
        bridge.actions.forEach(function (act) {
          if (act.action === 'selectStudent') {
            var sid = act.payload
            if (sid) setTimeout(function () { window.toggleStudentDetail(sid) }, 300)
          }
          if (act.action === 'selectClass') {
            var cls = act.payload
            if (cls) {
              var sel = document.getElementById('diag-class')
              if (sel) { sel.value = cls; sel.dispatchEvent(new Event('change')) }
            }
          }
          if (act.action === 'showPlan') {
            setTimeout(function () { window.togglePlanPanel() }, 500)
          }
        })
      }
      // Populate data
      if (bridge.populates) {
        bridge.populates.forEach(function (pop) {
          if (pop.target === 'diagnosis' && pop.data) {
            currentDiagnosis = pop.data
            renderOverview(pop.data)
            if (pop.data.students) renderStudentList(pop.data)
          }
        })
      }
      window.__chemai_bridge = null
    }

    document.getElementById('diag-class').addEventListener('change', function () {
      var cls = this.value; if (!cls) return
      fetch('/api/exam/list/' + cls).then(function (r) { return r.json() }).then(function (d) {
        var sel = document.getElementById('diag-exam'), list = d.exams || []
        sel.innerHTML = '<option value="">选择考试...</option>'
        list.forEach(function (e) { var o = document.createElement('option'); o.value = e.record_id; o.textContent = e.name; sel.appendChild(o) })
      }).catch(function () {})
    })
  })

  function loadClasses(cb) {
    fetch('/api/classes').then(function (r) { return r.json() }).then(function (d) {
      var sel = document.getElementById('diag-class'), list = d.classes || []
      if (sel.options.length <= 1) {
        list.forEach(function (c) { var o = document.createElement('option'); o.value = c.class_id; o.textContent = c.name; sel.appendChild(o) })
      }
      if (cb) cb()
    })
  }

  // ═══════════════════════════════════════════════
  // 5.1 + 5.2: 诊断执行 → 班级概览 + 学生列表
  // ═══════════════════════════════════════════════
  window.runDiagnosis = function () {
    var cls = document.getElementById('diag-class').value
    var exam = document.getElementById('diag-exam').value
    if (!cls) { alert('请选择班级'); return }
    if (!exam) { alert('请选择考试'); return }
    currentClassId = cls; currentExamId = exam

    var el = document.getElementById('diag-result')
    el.innerHTML = '<div class="empty-state"><div class="progress-bar" style="width:200px"><div class="progress-fill pulse" style="width:60%"></div></div><p class="mt-2" style="color:#43474e">诊断中...</p></div>'

    fetch('/api/diagnosis/barrier/' + cls + '/' + exam)
      .then(function (r) { return r.json() })
      .then(function (d) {
        currentDiagnosis = d
        renderOverview(d)
        renderStudentList(d)
      })
      .catch(function (e) { el.innerHTML = '<div class="card" style="border-color:#C53030"><p>诊断失败: ' + e.message + '</p></div>' })
  }

  // ─── 5.1: 班级概览 CSS 柱状图 ───
  function renderOverview(d) {
    var dist = d.class_barrier_distribution || {}
    var concept = dist.concept || 0
    var reading = dist.reading || 0
    var expression = dist.expression || 0
    var total = Math.max(concept + reading + expression, 1)
    var students = d.students || []
    var avgMastery = d.avg_mastery || 0

    var html = '<div class="card mb-6"><h3 class="text-lg font-bold mb-4" style="font-family:Manrope">班级障碍分布</h3>'

    // Bar chart
    var maxVal = Math.max(concept, reading, expression, 1)
    html += '<div class="bar-chart">' +
      barCol('概念理解型', concept, '#290068', maxVal) +
      barCol('审题障碍型', reading, '#002045', maxVal) +
      barCol('表述障碍型', expression, '#13696a', maxVal) +
      '</div>'

    // Summary stats
    html += '<div class="flex gap-4 mt-4 flex-wrap">' +
      '<div class="flex-1 text-center card" style="min-width:100px"><p class="text-2xl font-bold" style="color:#002045;font-family:Manrope">' + students.length + '</p><p class="text-xs" style="color:#43474e">诊断学生</p></div>' +
      '<div class="flex-1 text-center card" style="min-width:100px"><p class="text-2xl font-bold" style="color:#2F855A;font-family:Manrope">' + (avgMastery * 100).toFixed(0) + '%</p><p class="text-xs" style="color:#43474e">班级平均掌握度</p></div>' +
      '<div class="flex-1 text-center card" style="min-width:100px"><p class="text-2xl font-bold" style="color:#C53030;font-family:Manrope">' + (concept + reading + expression) + '</p><p class="text-xs" style="color:#43474e">需关注学生合计</p></div>' +
      '</div></div>'

    document.getElementById('diag-result').innerHTML = html + '<div id="student-list-section"><div class="empty-state"><p>渲染学生列表中...</p></div></div>'

    // Chart.js doughnut
    var chartDiv = document.getElementById('diag-charts')
    if (chartDiv && typeof Chart !== 'undefined') {
      chartDiv.style.display = ''
      var ctx = document.getElementById('barrier-doughnut')
      if (ctx && !ctx._chart) {
        ctx._chart = new Chart(ctx, {
          type: 'doughnut',
          data: {
            labels: ['概念理解型', '审题障碍型', '表述障碍型'],
            datasets: [{ data: [concept, reading, expression], backgroundColor: ['#b43c28', '#d4956b', '#13696a'], borderWidth: 0 }]
          },
          options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
        })
      }
      document.getElementById('chart-summary').textContent = '共诊断 ' + students.length + ' 名学生。' +
        (concept >= reading && concept >= expression ? '概念理解型障碍占主导，建议加强基础概念教学。' :
         reading >= expression ? '审题障碍型占主导，建议增加题干分析训练。' :
         '表述障碍型占主导，建议强化规范化表达练习。')
    }
  }

  function barCol(label, val, color, maxVal) {
    var h = Math.max(Math.round(val / maxVal * 120), 4)
    return '<div class="bar-col"><div class="bar-value" style="color:' + color + '">' + val + '</div><div class="bar-outer"><div class="bar-inner" style="height:' + h + 'px;background:' + color + '"></div></div><div class="bar-label">' + label + '</div></div>'
  }

  // ─── 5.2: 学生列表（按严重度排序 + 搜索 + 筛选） ───
  function renderStudentList(d) {
    var students = (d.students || []).slice()
    // Sort: those with actual errors first
    students.sort(function (a, b) {
      var aScore = (a.barrier_type && a.barrier_type[a.dominant_barrier]) || 0
      var bScore = (b.barrier_type && b.barrier_type[b.dominant_barrier]) || 0
      return bScore - aScore
    })

    var html = '<h3 class="text-lg font-bold mb-3" style="font-family:Manrope">需关注学生 <span class="text-sm" style="color:#74777f">(' + students.length + '人)</span></h3>'

    // Search + filter
    html += '<div class="flex gap-3 mb-4 flex-wrap"><input id="diag-search" class="input-field" placeholder="搜索学生姓名..." style="width:200px" oninput="filterStudents()">' +
      '<span class="tab-filter active" onclick="filterByBarrier(\'all\',this)" id="f-all">全部</span>' +
      '<span class="tab-filter" onclick="filterByBarrier(\'concept\',this)" id="f-concept">概念理解型</span>' +
      '<span class="tab-filter" onclick="filterByBarrier(\'reading\',this)" id="f-reading">审题障碍型</span>' +
      '<span class="tab-filter" onclick="filterByBarrier(\'expression\',this)" id="f-expression">表述障碍型</span>' +
      '</div>'

    html += '<div id="student-rows">' + students.map(function (s, i) { return studentRowHtml(s, i) }).join('') + '</div>'

    // Store for filtering
    window.__allStudents = students
    window.__currentFilter = 'all'

    var section = document.getElementById('student-list-section')
    if (section) section.innerHTML = html
  }

  function studentRowHtml(s, i) {
    var bt = s.barrier_type || {}
    var dominant = s.dominant_barrier || 'concept'
    var dominantPct = bt[dominant] || 0
    var severity = dominantPct >= 0.6 ? 'high' : dominantPct >= 0.4 ? 'medium' : 'low'
    var severityCls = dominantPct >= 0.6 ? 'severity-dot high' : dominantPct >= 0.4 ? 'severity-dot medium' : 'severity-dot low'
    var barrierName = { concept: '概念理解', reading: '审题障碍', expression: '表述障碍' }[dominant] || dominant
    var wkpCount = (s.weak_knowledge_points || []).length

    return '<div class="student-row" id="srow-' + i + '" onclick="toggleStudentDetail(\'' + esc(s.student_id) + '\',' + i + ')" data-barrier="' + dominant + '">' +
      '<span class="' + severityCls + '"></span>' +
      '<div class="flex-1"><span class="font-medium">' + escHtml(s.student_name) + '</span>' +
      '<span class="tag ml-2 tag-' + dominant + '">' + barrierName + ' ' + Math.round(dominantPct * 100) + '%</span></div>' +
      '<span class="text-sm" style="color:#43474e">' + wkpCount + ' 弱知识点</span>' +
      '<span class="material-symbols-outlined text-[20px]" style="color:#74777f">expand_more</span>' +
      '</div><div class="accordion-body" id="sdetail-' + i + '"></div>'
  }

  // ─── 过滤 ───
  window.filterStudents = function () {
    var kw = (document.getElementById('diag-search').value || '').toLowerCase()
    var barrier = window.__currentFilter || 'all'
    var rows = document.querySelectorAll('#student-rows .student-row')
    rows.forEach(function (r) {
      var name = (r.querySelector('.font-medium') || {}).textContent || ''
      var b = r.getAttribute('data-barrier')
      var visible = (!kw || name.toLowerCase().includes(kw)) && (barrier === 'all' || b === barrier)
      r.style.display = visible ? 'flex' : 'none'
    })
  }

  window.filterByBarrier = function (b, btn) {
    window.__currentFilter = b
    document.querySelectorAll('.tab-filter').forEach(function (t) { t.classList.remove('active') })
    if (btn) btn.classList.add('active')
    filterStudents()
  }

  // ═══════════════════════════════════════════════
  // 5.3: 学生详情展开
  // ═══════════════════════════════════════════════
  window.toggleStudentDetail = function (sid, idx) {
    var body = document.getElementById('sdetail-' + idx)
    var row = document.getElementById('srow-' + idx)

    // Toggle selected style
    document.querySelectorAll('.student-row.selected').forEach(function (r) { r.classList.remove('selected') })
    row.classList.add('selected')

    if (body.classList.contains('open')) {
      body.classList.remove('open')
      return
    }

    // Close all
    document.querySelectorAll('.accordion-body.open').forEach(function (b) { b.classList.remove('open') })

    body.classList.add('open')
    body.innerHTML = '<div class="progress-bar" style="width:200px"><div class="progress-fill pulse" style="width:60%"></div></div><p class="text-sm mt-2" style="color:#43474e">加载详情...</p>'

    // Fetch detail
    fetch('/api/diagnosis/plan/' + sid)
      .then(function (r) { return r.json() })
      .then(function (d) {
        if (!d.success) { body.innerHTML = '<p class="text-sm" style="color:#C53030">加载失败</p>'; return }
        var data = d.data || {}
        var bt = data.barrier_type || {}
        var dominant = data.dominant_barrier || 'concept'
        var wkp = data.weak_knowledge_points || []
        var intervention = data.recommended_intervention || ''

        // Barrier distribution bars
        var barriers = [
          { key: 'concept', label: '概念理解型', color: '#290068', val: bt.concept || 0 },
          { key: 'reading', label: '审题障碍型', color: '#002045', val: bt.reading || 0 },
          { key: 'expression', label: '表述障碍型', color: '#13696a', val: bt.expression || 0 }
        ]

        var html = '<div class="grid grid-cols-2 gap-4 mb-4">'
        // Column 1: Barrier confidence
        html += '<div><h4 class="font-bold text-sm mb-2" style="font-family:Manrope">障碍置信度分布</h4>'
        barriers.forEach(function (b) {
          html += '<div class="flex items-center gap-2 mb-2"><span class="text-xs" style="width:80px;color:' + b.color + '">' + b.label + '</span><div class="progress-bar flex-1"><div class="progress-fill" style="width:' + Math.round(b.val * 100) + '%;background:' + b.color + '"></div></div><span class="text-xs" style="font-family:JetBrains Mono;min-width:32px">' + Math.round(b.val * 100) + '%</span></div>'
        })
        html += '</div>'

        // Column 2: Weak KPs + Intervention
        html += '<div><h4 class="font-bold text-sm mb-2" style="font-family:Manrope">薄弱知识点</h4>'
        html += wkp.length ? '<div class="flex flex-wrap gap-1">' + wkp.map(function (k) { return '<span class="tag tag-concept">' + escHtml(k) + '</span>' }).join('') + '</div>' : '<p class="text-sm" style="color:#74777f">暂无数据</p>'
        html += '<h4 class="font-bold text-sm mt-3 mb-1" style="font-family:Manrope">干预建议</h4><p class="text-sm" style="color:#43474e">' + escHtml(intervention) + '</p>'
        html += '</div></div>'

        // Actions
        var hasPlan = !!savedPlans[sid]
        html += '<div class="flex gap-2 flex-wrap"><button class="btn-teal btn-sm" onclick="genPlan(\'' + esc(sid) + '\',\'' + esc(data.student_name) + '\')"><span class="material-symbols-outlined text-[16px]">psychology</span> 生成学习计划</button>'
        if (hasPlan) {
          html += '<button class="btn-primary btn-sm" onclick="viewPlan(\'' + esc(sid) + '\')"><span class="material-symbols-outlined text-[16px]">visibility</span> 查看计划</button>'
        }
        html += '</div>'

        body.innerHTML = html
      })
      .catch(function (e) { body.innerHTML = '<p class="text-sm" style="color:#C53030">加载失败: ' + e.message + '</p>' })
  }

  // ═══════════════════════════════════════════════
  // 5.4: 学习计划生成
  // ═══════════════════════════════════════════════
  window.genPlan = function (sid, sname) {
    // Show generating progress in the student detail or a notification
    var genHtml = '<div class="card" style="border:1px solid #13696a"><h4 class="font-bold mb-2" style="font-family:Manrope">AI 正在生成 「' + escHtml(sname) + '」 的学习计划...</h4><div class="progress-bar" style="width:300px"><div class="progress-fill pulse" style="width:40%"></div></div><p class="text-sm mt-2" style="color:#43474e">正在分析薄弱知识点，生成定制化学习路径...</p></div>'

    // Append below the current detail
    var details = document.querySelectorAll('.accordion-body.open')
    if (details.length > 0) {
      details[0].insertAdjacentHTML('beforeend', genHtml)
      // Scroll to bottom
      details[0].scrollTop = details[0].scrollHeight
    }

    // Call the generate endpoint
    fetch('/api/diagnosis/learning-plan/generate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ student_id: sid, barrier_type: 'concept', weak_knowledge_points: [] })
    })
      .then(function (r) { return r.json() })
      .then(function (d) {
        // Save plan
        savedPlans[sid] = { student_name: sname, plan: d.plan || {}, generated_at: d.generated_at || new Date().toISOString() }
        persistPlans()

        // Replace the progress indicator with actual plan
        var planHtml = renderPlanContent(sid, sname, d.plan || {})
        var details = document.querySelectorAll('.accordion-body.open')
        if (details.length > 0) {
          // Remove last children (the progress card)
          var cards = details[0].querySelectorAll('.card')
          if (cards.length > 0) {
            var lastCard = cards[cards.length - 1]
            if (lastCard.textContent.includes('正在生成') || lastCard.textContent.includes('正在分析')) {
              lastCard.remove()
            }
          }
          details[0].insertAdjacentHTML('beforeend', planHtml)
        }
      })
      .catch(function (e) {
        var details = document.querySelectorAll('.accordion-body.open')
        if (details.length > 0) {
          details[0].insertAdjacentHTML('beforeend', '<p class="text-sm mt-2" style="color:#C53030">生成失败: ' + e.message + '</p>')
        }
      })
  }

  function renderPlanContent(sid, sname, plan) {
    var title = plan.plan_title || '个性化学习计划'
    var period = plan.plan_period || '2周'
    var tasks = plan.daily_tasks || []
    var weeks = plan.weekly_goals || []
    var barriers = plan.barrier_interventions || []
    var motivation = plan.motivation_tips || []
    var parentMsg = plan.parent_communication_suggestion || ''

    var html = '<div class="card mb-3 plan-card concept mt-3" id="plan-' + esc(sid) + '"><div class="flex justify-between items-center"><h4 class="font-bold" style="font-family:Manrope">' + escHtml(title) + '</h4><span class="text-xs" style="color:#43474e">周期: ' + escHtml(period) + '</span></div>'

    // Barrier interventions
    if (barriers.length) {
      html += '<div class="mt-3"><h5 class="text-sm font-bold mb-1">障碍干预策略</h5>'
      barriers.forEach(function (b) {
        html += '<div class="plan-day-row"><span class="day-tag">' + escHtml(b.barrier || '') + '</span><div><p class="text-sm">' + escHtml(b.strategy || '') + '</p><p class="text-xs" style="color:#43474e">' + escHtml(b.practice_tips || '') + '</p></div></div>'
      })
      html += '</div>'
    }

    // Daily tasks
    if (tasks.length) {
      html += '<div class="mt-3"><h5 class="text-sm font-bold mb-1">每日任务</h5>'
      tasks.forEach(function (t) {
        html += '<div class="plan-day-row"><span class="day-tag">' + escHtml(t.day || '') + '</span><div><p class="text-sm">' + escHtml(t.content || '') + '</p><p class="text-xs" style="color:#43474e">' + escHtml(t.duration || '') + ' · ' + escHtml(t.resource_type || '') + '</p></div></div>'
      })
      html += '</div>'
    }

    // Weekly goals
    if (weeks.length) {
      html += '<div class="mt-3"><h5 class="text-sm font-bold mb-1">每周目标</h5>'
      weeks.forEach(function (w) {
        html += '<div class="plan-day-row"><span class="day-tag">' + escHtml(w.week || '') + '</span><div><p class="text-sm">里程碑: ' + escHtml(w.milestone || '') + '</p></div></div>'
      })
      html += '</div>'
    }

    // Motivation
    if (motivation.length) {
      html += '<div class="mt-2 flex gap-2 flex-wrap">' + motivation.map(function (m) { return '<span class="tag" style="background:#e0f2f1;color:#004f50">' + escHtml(String(m)) + '</span>' }).join('') + '</div>'
    }

    // Actions: send to parent + apply
    html += '<div class="flex gap-2 mt-3 flex-wrap"><button class="btn-teal btn-sm" onclick="sendPlanToParent(\'' + esc(sid) + '\')"><span class="material-symbols-outlined text-[16px]">send</span> 发给家长</button><button class="btn-primary btn-sm" onclick="applyPlan(\'' + esc(sid) + '\')"><span class="material-symbols-outlined text-[16px]">check_circle</span> 应用计划</button><button class="btn-icon" onclick="deletePlan(\'' + esc(sid) + '\')" title="删除计划"><span class="material-symbols-outlined text-[18px]" style="color:#C53030">delete</span></button></div>'

    html += '</div>'
    return html
  }

  // ═══════════════════════════════════════════════
  // 5.6: 发送给家长 + 应用计划
  // ═══════════════════════════════════════════════
  window.sendPlanToParent = function (sid) {
    fetch('/api/diagnosis/learning-plan/send-to-parent/' + sid, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) })
      .then(function (r) { return r.json() })
      .then(function (d) {
        if (d.success) { alert('已发送给 ' + d.sent_count + ' 位家长') }
        else { alert('发送失败: ' + d.message) }
      })
      .catch(function (e) { alert('发送失败: ' + e.message) })
  }

  window.applyPlan = function (sid) {
    var plan = savedPlans[sid]
    fetch('/api/diagnosis/learning-plan/apply/' + sid, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(plan ? plan.plan : {}) })
      .then(function (r) { return r.json() })
      .then(function (d) {
        if (d.success) { alert('学习计划已应用!') } else { alert('应用失败') }
      })
      .catch(function (e) { alert('应用失败: ' + e.message) })
  }

  window.deletePlan = function (sid) {
    if (!confirm('确定删除该学习计划？')) return
    delete savedPlans[sid]
    persistPlans()
    var planEl = document.getElementById('plan-' + sid)
    if (planEl) planEl.remove()
  }

  // ═══════════════════════════════════════════════
  // 5.5: 已生成计划管理
  // ═══════════════════════════════════════════════
  window.togglePlanPanel = function () {
    var panel = document.getElementById('plan-panel')
    if (panel.style.display === 'block') { panel.style.display = 'none'; return }
    panel.style.display = 'block'
    renderPlanList()
  }

  function renderPlanList() {
    var el = document.getElementById('plan-list')
    var ids = Object.keys(savedPlans)
    if (!ids.length) { el.innerHTML = '<div class="empty-state"><span class="material-symbols-outlined text-3xl" style="color:#c4c6cf">description</span><p>暂无已生成的学习计划</p></div>'; return }

    el.innerHTML = ids.map(function (sid) {
      var p = savedPlans[sid]
      return '<div class="card card-accent plan-card concept mb-2 flex justify-between items-center"><div><p class="font-bold">' + escHtml(p.student_name || sid) + '</p><p class="text-xs" style="color:#43474e">' + (p.generated_at || '') + '</p></div><div class="flex gap-2"><button class="btn-teal btn-sm" onclick="viewPlan(\'' + esc(sid) + '\')">查看</button><button class="btn-icon" onclick="deletePlan(\'' + esc(sid) + '\')"><span class="material-symbols-outlined text-[18px]" style="color:#C53030">delete</span></button></div></div>'
    }).join('')
  }

  window.viewPlan = function (sid) {
    var p = savedPlans[sid]
    if (!p) { alert('计划不存在'); return }

    // Find the accordion body and show the plan
    var body = document.querySelector('.accordion-body.open')
    if (!body) {
      // Open in plan panel
      var panel = document.getElementById('plan-panel')
      panel.style.display = 'block'
      document.getElementById('plan-list').innerHTML = renderPlanContent(sid, p.student_name, p.plan || {}) +
        '<button class="btn-secondary btn-sm mt-2" onclick="togglePlanPanel()">关闭</button>'
      return
    }
    body.insertAdjacentHTML('beforeend', renderPlanContent(sid, p.student_name, p.plan || {}))
  }

  // ═══════════════════════════════════════════════
  // Helpers
  // ═══════════════════════════════════════════════
  function loadPlans() {
    try {
      savedPlans = JSON.parse(localStorage.getItem('chemai_plans') || '{}')
    } catch (e) { savedPlans = {} }
  }
  function persistPlans() {
    localStorage.setItem('chemai_plans', JSON.stringify(savedPlans))
  }
  function escHtml(s) {
    if (!s) return ''
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
  }
  function esc(s) {
    if (!s) return ''
    return String(s).replace(/\\/g, '\\\\').replace(/'/g, "\\'")
  }
})()

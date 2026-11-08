/**
 * ChemAI Agent Tool Renderers
 * 将 SSE tool_result JSON 渲染为富 HTML 组件
 */
(function () {
  'use strict'

  // ─── Helpers ───
  function esc(s) { if (!s) return ''; return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;') }

  // ─── 题目卡片列表 ───
  function renderQuestionCards(data) {
    var qs = data.questions || (Array.isArray(data) ? data : [])
    if (!qs.length) return '<p style="color:#74777f">暂无题目</p>'
    return qs.map(function(q, i) {
      var status = q.overall_status || 'passed'
      var auditLabel = {passed:'✓ 通过',warning:'⚠ 需确认',blocked:'✗ 拦截'}[status] || status
      var opts = ''
      if (q.options) {
        var arr = typeof q.options === 'string' ? q.options.split(',') : q.options
        opts = '<div style="font-size:12px;color:#3d3d56;margin-top:4px;font-family:JetBrains Mono">' + arr.map(function(o){return esc(o.trim())}).join(' &nbsp; ') + '</div>'
      }
      var tags = (q.knowledge_points || []).map(function(k){return '<span class="tag tag-medium">'+esc(k)+'</span>'}).join('')
      var diffTag = q.difficulty ? '<span class="tag tag-'+q.difficulty+'">'+q.difficulty+'</span>' : ''
      return '<div class="card card-accent qcard-enter" style="animation-delay:'+(i*.05).toFixed(2)+'s;margin-bottom:6px">'+
        '<span class="audit-badge '+status+'">'+auditLabel+'</span>'+
        '<p style="font-weight:600;font-size:13px">#'+(i+1)+' '+esc(q.content)+'</p>'+opts+
        '<div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap;align-items:center">'+
        '<span class="tag" style="background:#e0f2f1;color:#004f50">答案: '+esc(q.answer||'')+'</span>'+diffTag+'</div>'+
        (q.analysis?'<p style="font-size:12px;color:#3d3d56;margin-top:4px">'+esc(q.analysis)+'</p>':'')+
        '<div style="margin-top:4px">'+tags+'</div></div>'
    }).join('')
  }

  // ─── 障碍诊断柱状图 + 学生列表 ───
  function renderBarrierOverview(data) {
    var dist = data.class_barrier_distribution || {}
    var concept = dist.concept || 0, reading = dist.reading || 0, expression = dist.expression || 0
    var maxVal = Math.max(concept, reading, expression, 1)
    var students = data.students || []
    var avgMastery = data.avg_mastery || 0
    var bars = [
      {label:'概念理解',val:concept,color:'#290068'},
      {label:'审题障碍',val:reading,color:'#002045'},
      {label:'表述障碍',val:expression,color:'#13696a'}
    ]
    var html = '<div style="display:flex;align-items:end;gap:20px;height:140px;padding:8px 0">'
    bars.forEach(function(b){
      var h = Math.max(Math.round(b.val/maxVal*100), 4)
      html += '<div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:4px">'+
        '<span style="font-weight:700;font-size:16px;font-family:Manrope;color:'+b.color+'">'+b.val+'</span>'+
        '<div style="flex:1;width:100%;max-width:60px;background:#e4e2de;border-radius:6px 6px 0 0;position:relative;overflow:hidden">'+
        '<div style="position:absolute;bottom:0;width:100%;height:'+h+'%;background:'+b.color+';border-radius:6px 6px 0 0;transition:height .5s cubic-bezier(.34,1.56,.64,1)"></div></div>'+
        '<span style="font-size:11px;color:#3d3d56;font-family:JetBrains Mono">'+b.label+'</span></div>'
    })
    html += '</div>'
    html += '<div style="display:flex;gap:10px;margin-top:12px">'+
      '<div class="card" style="flex:1;text-align:center"><span style="font-size:20px;font-weight:700;font-family:Manrope">'+(avgMastery*100).toFixed(0)+'%</span><p style="font-size:11px;color:#74777f">掌握度</p></div>'+
      '<div class="card" style="flex:1;text-align:center"><span style="font-size:20px;font-weight:700;font-family:Manrope">'+students.length+'</span><p style="font-size:11px;color:#74777f">诊断学生</p></div></div>'

    // Top 5 students
    if (students.length) {
      var sorted = students.slice().sort(function(a,b){return (b.barrier_type&&b.barrier_type[b.dominant_barrier]||0)-(a.barrier_type&&a.barrier_type[a.dominant_barrier]||0)})
      html += '<div style="margin-top:12px"><span style="font-size:12px;font-weight:600;font-family:Manrope">需关注学生</span>'
      sorted.slice(0, 5).forEach(function(s){
        var dom = s.dominant_barrier || ''
        var names = {concept:'概念',reading:'审题',expression:'表述'}
        html += '<div style="display:flex;align-items:center;gap:8px;padding:6px 10px;margin-top:4px;border:1px solid rgba(0,0,0,.06);border-radius:6px;font-size:13px">'+
          '<span style="font-weight:500">'+esc(s.student_name)+'</span>'+
          '<span class="tag tag-'+dom+'">'+((names[dom]||dom)+' '+Math.round((s.barrier_type&&s.barrier_type[dom]||0)*100)+'%')+'</span>'+
          '<span style="font-size:11px;color:#74777f">'+(s.weak_knowledge_points||[]).length+' 弱知识点</span></div>'
      })
      html += '</div>'
    }
    return html
  }

  // ─── 学习计划 ───
  function renderLearningPlan(data) {
    // 兼容两种数据格式: {plan_text, plan_data} 来自 generate_learning_plan, {plan} 来自旧版
    var plan = data.plan_data || data.plan || data || {}
    var studentName = data.student_name || ''
    var title = plan.plan_title || '个性化学习计划'
    var period = plan.plan_period || ''
    var tasks = plan.daily_tasks || []
    var weeks = plan.weekly_goals || []
    var barriers = plan.barrier_interventions || {}
    var tips = plan.motivation_tips || []

    var html = '<div style="border-left:4px solid #2c6e49;padding:12px 16px;background:#f8fcf9;border-radius:6px;margin-bottom:8px">'+
      '<div style="font-weight:700;font-size:15px;color:#2c6e49">'+esc(title)+'</div>'
    if (studentName) html += '<div style="font-size:12px;color:#888;margin-top:2px">学生: '+esc(studentName)+(period?' · 周期: '+esc(period):'')+'</div>'

    // 周目标
    if (weeks.length) {
      html += '<div style="margin-top:10px"><span style="font-size:12px;font-weight:600;color:#555">🎯 周目标</span>'
      weeks.forEach(function(w){
        var goal = typeof w === 'string' ? w : (w.milestone || w.goal || w.text || '')
        var wk = w.week || w.label || ''
        html += '<div style="padding:3px 8px;margin-top:2px;font-size:12px;color:#444">'+(wk?'<b>'+esc(wk)+'</b>: ':'')+esc(goal)+'</div>'
      })
      html += '</div>'
    }

    // 每日任务
    if (tasks.length) {
      html += '<div style="margin-top:8px"><span style="font-size:12px;font-weight:600;color:#555">📅 每日任务</span>'
      tasks.slice(0,14).forEach(function(t){
        var day = t.day || ''
        var task = t.task || t.content || (typeof t === 'string' ? t : '')
        html += '<div style="display:flex;gap:8px;padding:3px 8px;margin-top:2px;font-size:12px;color:#444"><span style="font-family:JetBrains Mono;font-size:11px;color:#2c6e49;min-width:50px">'+esc(day)+'</span><span>'+esc(task)+'</span></div>'
      })
      html += '</div>'
    }

    // 障碍干预 (兼容数组和字典)
    if (!Array.isArray(barriers) && typeof barriers === 'object' && Object.keys(barriers).length) {
      html += '<div style="margin-top:8px"><span style="font-size:12px;font-weight:600;color:#555">🧠 障碍干预</span>'
      var btLabels = {concept:'概念理解', reading:'审题仔细', expression:'答题表述'}
      Object.keys(barriers).forEach(function(bt){
        html += '<div style="display:flex;gap:8px;padding:3px 8px;margin-top:2px;font-size:12px;color:#444"><span style="font-family:JetBrains Mono;font-size:11px;color:#d97706;min-width:60px">'+esc(btLabels[bt]||bt)+'</span><span>'+esc(barriers[bt])+'</span></div>'
      })
      html += '</div>'
    } else if (Array.isArray(barriers) && barriers.length) {
      html += '<div style="margin-top:8px"><span style="font-size:12px;font-weight:600;color:#555">🧠 干预策略</span>'
      barriers.forEach(function(b){
        html += '<div style="padding:3px 8px;margin-top:2px;font-size:12px;color:#444"><span style="color:#d97706">'+esc(b.barrier||'')+'</span>: '+esc(b.strategy||'')+'</div>'
      })
      html += '</div>'
    }

    if (tips.length) {
      html += '<div style="margin-top:6px;display:flex;gap:4px;flex-wrap:wrap">'+tips.map(function(m){var t=typeof m==='string'?m:(m.tip||m.text||'');return '<span class="tag" style="background:#e0f2f1;color:#004f50;font-size:11px;padding:2px 8px;border-radius:10px">'+esc(t)+'</span>'}).join('')+'</div>'
    }
    html += '</div>'
    return html
  }

  // ─── 考试结果统计 ───
  function renderExamStats(data) {
    var students = data.students || []
    var html = '<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px">'+
      '<div class="card" style="flex:1;min-width:80px;text-align:center"><span style="font-size:20px;font-weight:700;font-family:Manrope;color:#13696a">'+(data.total_students||0)+'</span><p style="font-size:11px;color:#74777f">学生总数</p></div>'+
      '<div class="card" style="flex:1;min-width:80px;text-align:center"><span style="font-size:20px;font-weight:700;font-family:Manrope">'+(data.completed_count||0)+'</span><p style="font-size:11px;color:#74777f">已完成</p></div>'+
      '<div class="card" style="flex:1;min-width:80px;text-align:center"><span style="font-size:20px;font-weight:700;font-family:Manrope;color:#2F855A">'+(data.total_questions||0)+'</span><p style="font-size:11px;color:#74777f">题目数</p></div>'+
      '<div class="card" style="flex:1;min-width:80px;text-align:center"><span style="font-size:20px;font-weight:700;font-family:Manrope;color:#C53030">'+((data.class_avg_accuracy||0)*100).toFixed(1)+'%</span><p style="font-size:11px;color:#74777f">均分</p></div></div>'
    if (students.length) {
      html += '<table class="data-table"><thead><tr><th>#</th><th>学生</th><th>答题</th><th>正确</th><th>正确率</th><th>得分</th></tr></thead><tbody>'
      students.forEach(function(s,i){
        var accColor = s.accuracy>=0.8?'#2F855A':s.accuracy>=0.6?'#002045':'#C53030'
        html += '<tr><td>'+(i+1)+'</td><td>'+esc(s.student_name)+'</td><td>'+s.answered+'/'+data.total_questions+'</td><td>'+s.correct+'</td><td style="color:'+accColor+';font-weight:600">'+(s.accuracy*100).toFixed(1)+'%</td><td>'+s.score.toFixed(1)+'</td></tr>'
      })
      html += '</tbody></table>'
    }
    return html
  }

  // ─── OCR 结果表 ───
  function renderOcrTable(data) {
    var results = data.results || (Array.isArray(data) ? data : [])
    if (!results.length) return '<p style="color:#74777f">无识别结果</p>'
    var qNums = [], seen = {}
    results.forEach(function(r){
      Object.keys(r.answers||{}).forEach(function(k){ if(!seen[k]){seen[k]=true;qNums.push(k)} })
    })
    qNums.sort()
    var html = '<table class="data-table" style="font-size:12px"><thead><tr><th>学号</th><th>姓名</th>'
    qNums.forEach(function(q){html+='<th>'+q+'</th>'})
    html += '</tr></thead><tbody>'
    results.forEach(function(r){
      html += '<tr><td style="font-family:JetBrains Mono;font-size:11px">'+esc(r.student_id)+'</td><td>'+esc(r.student_name||'')+'</td>'
      qNums.forEach(function(q){
        var a = (r.answers||{})[q]||{}
        var conf = a.confidence || 0
        var cCls = conf>=0.85?'color:#2F855A':conf>=0.6?'color:#e6a817':'color:#C53030'
        html += '<td><span>'+esc(a.answer||'--')+'</span><div style="font-size:10px;'+cCls+'">'+Math.round(conf*100)+'%</div></td>'
      })
      html += '</tr>'
    })
    html += '</tbody></table>'
    return html
  }

  // ─── JSON fallback ───
  function renderJson(data) {
    return '<pre style="font-size:11px;font-family:JetBrains Mono;white-space:pre-wrap;max-height:300px;overflow-y:auto;color:#3d3d56">' + esc(JSON.stringify(data, null, 2)) + '</pre>'
  }

  // ─── Renderer dispatch ───
  // ─── 搜索结果显示 ───
  function renderSearchResults(data) {
    var qs = data.questions || (Array.isArray(data) ? data : [])
    var total = data.total || qs.length
    if (!qs.length) return '<div class="card" style="padding:12px 16px;font-size:13px;color:#74777f">题库中暂无匹配结果</div>'
    return '<div style="font-size:12px;color:#74777f;margin-bottom:6px">找到 ' + total + ' 道真题</div>' + qs.slice(0, 5).map(function(q, i) {
      return '<div class="card card-accent" style="padding:10px 14px;margin-bottom:4px;font-size:13px">' +
        '<span style="font-weight:600">' + (q.source||'') + ' · ' + (q.year||'') + '</span>' +
        '<p style="margin:4px 0">' + esc((q.content||'').substring(0, 150)) + '</p>' +
        '<span class="tag" style="background:#e0f2f1;color:#004f50;font-size:11px">答案: ' + esc(q.answer||'') + '</span>' +
        '</div>'
    }).join('') + (qs.length > 5 ? '<div style="font-size:12px;color:#74777f;text-align:center">...还有 '+(qs.length-5)+' 题</div>' : '')
  }

  // ─── 联网搜索结果摘要 ───
  function renderWebSearchResult(data) {
    var result = data.result || data.content || ''
    if (!result) return '<div class="card" style="padding:12px 16px;font-size:13px;color:#74777f">搜索完成，未获取到相关内容</div>'
    if (data.error) return '<div class="card" style="padding:12px 16px;font-size:13px;color:#C53030">搜索异常: ' + esc(data.error) + '</div>'
    return '<details class="card" style="padding:10px 14px;font-size:13px;cursor:pointer"><summary style="font-weight:500;color:#004f50">已获取搜索结果 (' + esc(data.query||'') + ')</summary><div style="margin-top:8px;max-height:200px;overflow-y:auto;white-space:pre-wrap;font-size:12px;color:#3d3d56">' + (result || '').substring(0, 2000) + '</div></details>'
  }

  // ─── 答案解析（chemistry_tutor）───
  function renderTutorAnswer(data) {
    var answer = data.answer || ''
    if (!answer) return '<div class="card" style="padding:12px 16px;font-size:13px;color:#74777f">暂无回复</div>'
    return '<div class="card" style="padding:12px 16px;font-size:13px;line-height:1.7">' +
      esc(answer).replace(/\n/g, '<br>') +
      (data.model ? '<div style="margin-top:6px;font-size:10px;color:#999">模型: ' + esc(data.model) + '</div>' : '') +
      '</div>'
  }

  // ─── 实验报告（simulate_experiment）───
  function renderExperiment(data) {
    var html = ''
    if (data.experiment_name) html += '<h3 style="margin:0 0 8px;font-size:15px;color:#290068">' + esc(data.experiment_name) + '</h3>'
    if (data.objectives && data.objectives.length) {
      html += '<p style="font-size:12px;font-weight:600;margin:6px 0 2px">实验目的</p><ul style="margin:0;padding-left:18px;font-size:12px">'
      data.objectives.forEach(function(o) { html += '<li>' + esc(o) + '</li>' })
      html += '</ul>'
    }
    if (data.equipment && data.equipment.length) {
      html += '<p style="font-size:12px;font-weight:600;margin:6px 0 2px">仪器与药品</p>'
      html += '<div style="display:flex;gap:4px;flex-wrap:wrap">' + data.equipment.map(function(e){return '<span class="tag tag-medium">'+esc(e)+'</span>'}).join('') + '</div>'
    }
    if (data.steps && data.steps.length) {
      html += '<p style="font-size:12px;font-weight:600;margin:6px 0 2px">实验步骤</p><ol style="margin:0;padding-left:18px;font-size:12px">'
      data.steps.forEach(function(s) { html += '<li>' + esc(s) + '</li>' })
      html += '</ol>'
    }
    if (data.expected_phenomena && data.expected_phenomena.length) {
      html += '<p style="font-size:12px;font-weight:600;margin:6px 0 2px">预期现象</p><ul style="margin:0;padding-left:18px;font-size:12px">'
      data.expected_phenomena.forEach(function(p) { html += '<li>' + esc(p) + '</li>' })
      html += '</ul>'
    }
    if (data.equations && data.equations.length) {
      html += '<p style="font-size:12px;font-weight:600;margin:6px 0 2px">化学方程式</p><ul style="margin:0;padding-left:18px;font-size:12px;font-family:JetBrains Mono">'
      data.equations.forEach(function(e) { html += '<li>' + esc(e) + '</li>' })
      html += '</ul>'
    }
    if (data.safety && data.safety.length) {
      html += '<div style="margin-top:6px;padding:6px 10px;background:#fff3cd;border-radius:4px;font-size:12px">'
      html += '<span style="font-weight:600;color:#856404">安全提醒</span><ul style="margin:2px 0 0;padding-left:18px">'
      data.safety.forEach(function(s) { html += '<li style="color:#856404">' + esc(s) + '</li>' })
      html += '</ul></div>'
    }
    if (data.exam_tips && data.exam_tips.length) {
      html += '<p style="font-size:12px;font-weight:600;margin:6px 0 2px">高考考点</p><ul style="margin:0;padding-left:18px;font-size:12px;color:#004f50">'
      data.exam_tips.forEach(function(t) { html += '<li>' + esc(t) + '</li>' })
      html += '</ul>'
    }
    if (data.error) return '<div class="card" style="padding:12px 16px;font-size:13px;color:#C53030">' + esc(data.error) + '</div>'
    if (!html) return '<pre style="font-size:11px;font-family:JetBrains Mono;white-space:pre-wrap;max-height:300px;overflow-y:auto">' + esc(JSON.stringify(data, null, 2)) + '</pre>'
    return '<div class="card" style="padding:12px 14px;font-size:13px">' + html + '</div>'
  }

  // ─── 方程式配平结果（balance_equation）───
  function renderBalanceResult(data) {
    var status = data.overall_status || 'unknown'
    var statusColors = {passed:'#2c6e49', warning:'#e6a817', blocked:'#C53030', error:'#C53030'}
    var statusLabels = {passed:'✓ 配平正确', warning:'⚠ 需确认', blocked:'✗ 配平错误', error:'✗ 解析失败'}
    var color = statusColors[status] || '#74777f'
    var label = statusLabels[status] || status

    var html = '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">' +
      '<span style="font-weight:700;font-size:14px;color:' + color + '">' + label + '</span></div>'

    if (data.equation) html += '<p style="font-size:12px;color:#74777f">方程式: <code>' + esc(data.equation) + '</code></p>'

    if (data.balance && data.balance.length) {
      html += '<table class="data-table" style="font-size:12px;margin-top:8px"><thead><tr><th>元素</th><th>左侧原子数</th><th>右侧原子数</th><th>状态</th></tr></thead><tbody>'
      data.balance.forEach(function(b) {
        var balanced = b.left_count === b.right_count
        html += '<tr><td>' + esc(b.element) + '</td><td>' + b.left_count + '</td><td>' + b.right_count + '</td>' +
          '<td style="color:' + (balanced ? '#2c6e49' : '#C53030') + '">' + (balanced ? '✓' : '✗ 差' + Math.abs(b.left_count - b.right_count)) + '</td></tr>'
      })
      html += '</tbody></table>'
    }

    if (data.coefficients) {
      html += '<p style="font-size:12px;margin-top:8px"><span style="font-weight:600">系数: </span><code>' + esc(JSON.stringify(data.coefficients)) + '</code></p>'
    }

    if (data.error) return '<div class="card" style="padding:12px 16px;font-size:13px;color:#C53030">' + esc(data.error) + '</div>'
    return '<div class="card" style="padding:12px 14px;font-size:13px">' + html + '</div>'
  }

  // ─── 周报（weekly_report）───
  function renderWeeklyReport(data) {
    if (data.error) return '<div class="card" style="padding:12px 16px;font-size:13px;color:#C53030">' + esc(data.error) + '</div>'
    var html = ''
    if (data.student_name) html += '<h3 style="margin:0 0 4px;font-size:15px;color:#290068">' + esc(data.student_name) + ' 的学习周报</h3>'
    if (data.exam_count !== undefined) html += '<p style="font-size:12px;color:#74777f;margin:0 0 8px">本周参加 ' + data.exam_count + ' 次练习</p>'
    if (data.report) html += '<div style="font-size:13px;line-height:1.7;white-space:pre-wrap">' + esc(data.report) + '</div>'
    return '<div class="card" style="padding:12px 14px">' + html + '</div>'
  }

  // ─── 试卷导入结果（import_exam_paper）───
  function renderImportResult(data) {
    if (data.error) return '<div class="card" style="padding:12px 16px;font-size:13px;color:#C53030">' + esc(data.error) + '</div>'
    var html = '<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:8px">' +
      '<div class="card" style="flex:1;min-width:70px;text-align:center"><span style="font-size:18px;font-weight:700;font-family:Manrope">' + (data.extracted || 0) + '</span><p style="font-size:11px;color:#74777f">提取题目</p></div>' +
      '<div class="card" style="flex:1;min-width:70px;text-align:center"><span style="font-size:18px;font-weight:700;font-family:Manrope;color:#2c6e49">' + (data.passed_audit || 0) + '</span><p style="font-size:11px;color:#74777f">审核通过</p></div>' +
      '<div class="card" style="flex:1;min-width:70px;text-align:center"><span style="font-size:18px;font-weight:700;font-family:Manrope;color:#004f50">' + (data.saved || 0) + '</span><p style="font-size:11px;color:#74777f">已入库</p></div></div>'
    if (data.mineru_used !== undefined) html += '<p style="font-size:11px;color:#74777f">MinerU: ' + (data.mineru_used ? '✓' : '✗ 未启用') + '</p>'
    if (data.needs_review) html += '<p style="font-size:12px;color:#e6a817;margin-top:4px">⚠ ' + data.needs_review + ' 题需人工复核</p>'
    return '<div class="card" style="padding:12px 14px;font-size:13px">' + html + '</div>'
  }

  // ─── 自适应练习布置结果（assign_adaptive_practice）───
  function renderAssignResult(data) {
    if (data.error) return '<div class="card" style="padding:12px 16px;font-size:13px;color:#C53030">' + esc(data.error) + '</div>'
    var html = '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">' +
      '<span style="font-weight:700;font-size:14px;color:#2c6e49">已为 ' + (data.assigned_count || 0) + ' 名学生布置练习</span></div>'
    if (data.assigned && data.assigned.length) {
      html += '<table class="data-table" style="font-size:12px"><thead><tr><th>学生</th><th>难度(ZPD)</th><th>题数</th><th>障碍类型</th></tr></thead><tbody>'
      data.assigned.forEach(function(a) {
        html += '<tr><td>' + esc(a.student_name) + '</td><td>' + esc(a.zpd_difficulty || '') + '</td><td>' + (a.question_count || 0) + '</td><td>' + esc(a.barrier || '') + '</td></tr>'
      })
      html += '</tbody></table>'
    }
    return '<div class="card" style="padding:12px 14px;font-size:13px">' + html + '</div>'
  }

  window.ChemRenderers = {
    // ── Actual tool names (from agent/tools.py) ──
    search_exam_bank:       renderSearchResults,
    web_search:             renderWebSearchResult,
    generate_questions:     renderQuestionCards,
    diagnose_barrier:       renderBarrierOverview,
    chemistry_tutor:        renderTutorAnswer,
    simulate_experiment:    renderExperiment,
    balance_equation:       renderBalanceResult,
    weekly_report:          renderWeeklyReport,
    import_exam_paper:      renderImportResult,
    assign_adaptive_practice: renderAssignResult,
    // ── Legacy compatibility (old naming convention) ──
    exam_generate:          renderQuestionCards,
    exam_audit:             renderQuestionCards,
    exam_search_historical: renderSearchResults,
    exam_results:           renderExamStats,
    diagnosis_barrier:      renderBarrierOverview,
    diagnosis_barrier_class:renderBarrierOverview,
    diagnosis_plan_generate:renderLearningPlan,
    diagnosis_plan:         renderLearningPlan,
    generate_learning_plan: renderLearningPlan,
    parser_ocr:             renderOcrTable,
    ocr_result:             renderOcrTable,
  }

  window.ChemRender = function(toolName, data) {
    var fn = window.ChemRenderers[toolName]
    if (fn) return fn(data)
    return renderJson(data)
  }
})()

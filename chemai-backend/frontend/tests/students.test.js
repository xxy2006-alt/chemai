// students.js — 学生管理卡片网格 / 统计 / Drawer / 分页 / 筛选 / 邀请码 / 学习计划测试
// IIFE 在 DOMContentLoaded 时 loadInitial() 拉取班级与学生，故 import 后手动 dispatch；
// fetch stub 路由班级/学生/详情/生成计划等接口；Chart/canvas/clipboard/scrollIntoView 打桩。
import { describe, it, expect, beforeEach } from 'vitest'

const { students, fetchCalls, alerts, clipCalls, planData } = vi.hoisted(() => {
  // ─── DOM 节点 ───
  const mk = (tag, id) => { const el = document.createElement(tag); el.id = id; return el }
  const nodes = {
    sSearch: mk('input', 's-search'),
    sClass: mk('select', 's-class'),
    sBarrier: mk('select', 's-barrier'),
    cardGrid: mk('div', 'card-grid'),
    pagination: mk('div', 'pagination'),
    statBar: mk('div', 'stat-bar'),
    drawerBackdrop: mk('div', 'drawer-backdrop'),
    drawer: mk('div', 'drawer'),
    drawerContent: mk('div', 'drawer-content'),
    tfName: mk('div', 'tf-student-name'),
    tfClass: mk('select', 'tf-class'),
    transferModal: mk('div', 'transfer-modal'),
    addModal: mk('div', 'add-modal'),
    addTabManual: mk('div', 'add-tab-manual'),
    addTabInvite: mk('div', 'add-tab-invite'),
    addPanelManual: mk('div', 'add-panel-manual'),
    addPanelInvite: mk('div', 'add-panel-invite'),
    addName: mk('input', 'add-name'),
    addNameErr: mk('div', 'add-name-err'),
    addClass: mk('select', 'add-class'),
    addClassErr: mk('div', 'add-class-err'),
    inviteClass: mk('select', 'invite-class'),
    inviteClassErr: mk('div', 'invite-class-err'),
    inviteGenBtn: mk('button', 'invite-gen-btn'),
    inviteCodeDisplay: mk('div', 'invite-code-display'),
    inviteResult: mk('div', 'invite-result'),
    inviteCopyBtn: mk('button', 'invite-copy-btn'),
  }
  Object.values(nodes).forEach((el) => document.body.appendChild(el))
  // 静态 HTML 里 #s-barrier 预置了障碍选项；jsdom 空 select 设 value 无效
  ;['concept', 'reading', 'expression'].forEach((v) => {
    const o = document.createElement('option'); o.value = v; o.textContent = v
    nodes.sBarrier.appendChild(o)
  })

  // ─── 登录态 / 环境打桩 ───
  sessionStorage.setItem('chemai_user', JSON.stringify({ name: '海老师', token: 'tok-123', school: '市第一中学' }))
  const alerts = []
  globalThis.alert = (m) => alerts.push(m)
  globalThis.confirm = () => true
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = function () {}
  if (typeof HTMLCanvasElement !== 'undefined') HTMLCanvasElement.prototype.getContext = function () { return {} }
  globalThis.Chart = class { destroy() {} }
  const clipCalls = []
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText: (c) => { clipCalls.push(c); return Promise.resolve() } }, configurable: true,
  })

  // ─── 学生数据：13 人，c1 10 人 + c2 3 人；3 人障碍 > 0.6；1 人近期活跃 ───
  const today = new Date().toISOString().slice(0, 10)
  const names = ['张明宇', '<script>alert(1)</script>', '王浩然', '陈雨桐', '刘子轩', '赵文博', '周雅琪', '吴俊杰', '郑晓萌', '钱一鸣', '孙悦然', '朱天乐', '马思远']
  const classIds = ['c1', 'c2', 'c1', 'c2', 'c1', 'c2', 'c1', 'c1', 'c1', 'c1', 'c1', 'c1', 'c1']
  const barriers = [
    { concept: 0.85, reading: 0.15, expression: 0.05 }, // s1 concept 主导
    { concept: 0.1, reading: 0.2, expression: 0.7 },    // s2 expression
    { concept: 0.2, reading: 0.5, expression: 0.3 },    // s3 reading
    { concept: 0.7, reading: 0.2, expression: 0.1 },    // s4 concept 主导
    // s5-s13 默认 expression 0.4（无 >0.6）
  ]
  const students = []
  for (let i = 0; i < 13; i++) {
    students.push({
      student_id: 's' + (i + 1),
      name: names[i],
      class_id: classIds[i],
      class_name: classIds[i] === 'c1' ? 'A班' : 'B班',
      barrier_type: barriers[i] || { concept: 0.3, reading: 0.3, expression: 0.4 },
      weak_knowledge_points: ['盐类水解'],
      exercises_completed: 10,
      last_exercise_at: i === 0 ? today : '2026-01-01',
      accuracy: 0.75,
    })
  }

  // ─── fetch 路由 ───
  const fetchCalls = []
  const planData = {
    plan_title: '化学基础强化', plan_period: '2周',
    weekly_goals: ['理解盐类水解原理', '掌握电离平衡'],
    daily_tasks: [{ day: 1, task: '复习盐类水解' }, { day: 2, task: '做10道电离题' }],
    barrier_interventions: { concept: '用流程图讲解' },
    motivation_tips: ['先易后难'],
  }
  const studentDetail = {
    success: true,
    weak_knowledge_points: ['盐类水解', '电离平衡'],
    recent_activity: [
      { date: '05-10', desc: '完成盐类水解专项', is_correct: true },
      { date: '05-08', desc: '月考', is_correct: false },
    ],
  }
  globalThis.fetch = (url, opts) => {
    const u = String(url); const o = opts || {}
    fetchCalls.push({ url: u, opts: o })
    let data
    if (u.indexOf('/api/classes') >= 0) data = { classes: [{ class_id: 'c1', name: 'A班' }, { class_id: 'c2', name: 'B班' }] }
    else if (u.indexOf('/api/users/students') >= 0) data = { students }
    else if (u.indexOf('/api/users/student/') >= 0 && u.indexOf('/detail') >= 0) data = studentDetail
    else if (u.indexOf('/api/users/student') >= 0 && (o.method === 'POST' || o.method === 'PUT')) {
      if (u.indexOf('/transfer') >= 0) data = { success: true }
      else if (u.indexOf('/reset-password') >= 0) data = { message: '已重置' }
      else data = { success: true, invite_code: 'CHEM-123' }
    }
    else if (u.indexOf('/api/diagnosis/learning-plan/generate') >= 0) data = { plan: planData }
    else data = { classes: [] }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(data) })
  }

  return { students, fetchCalls, alerts, clipCalls, planData }
})

await import('../legacy/teacher/js/students.js')
// 手动触发 DOMContentLoaded，执行 loadInitial()（IIFE 在 readyState=complete 时不再自动触发）
document.dispatchEvent(new Event('DOMContentLoaded'))

const flush = () => new Promise((r) => setTimeout(r, 0))
const cards = () => document.querySelectorAll('#card-grid .student-card').length

beforeEach(() => {
  alerts.length = 0
  clipCalls.length = 0
  localStorage.removeItem('chemai_plans')
  localStorage.removeItem('chemai_plan_s1')
  document.getElementById('s-search').value = ''
  document.getElementById('s-class').value = ''
  document.getElementById('s-barrier').value = ''
  document.getElementById('add-name').value = ''
  document.getElementById('add-class').value = ''
  window.closeDrawer()      // 清掉上一个测试遗留的 Drawer 状态
  window.goPage(1)          // 重置 currentPage 并回到第 1 页
})

describe('loadInitial 统计条 + 班级筛选', () => {
  it('渲染总人数 / 近期活跃 / 需关注 / 人均练习', async () => {
    await flush()
    const num = (sel) => document.querySelector('#stat-bar ' + sel + ' .stat-num').textContent
    expect(num('.stat-item.total')).toBe('13')
    expect(num('.stat-item.active')).toBe('1')     // 仅 s1 近 30 天活跃
    expect(num('.stat-item.attention')).toBe('3')  // s1/s2/s4 障碍 > 0.6
    expect(num('.stat-item.avg')).toBe('10')       // 130 次 / 13 人
  })

  it('班级筛选下拉填入选项', async () => {
    await flush()
    const sel = document.getElementById('s-class')
    const vals = Array.from(sel.options).map((o) => o.value)
    expect(vals).toContain('c1')
    expect(vals).toContain('c2')
  })
})

describe('filterAndRender 卡片网格', () => {
  it('默认渲染全部 13 张卡（第一页 12 张 + 分页信息）', async () => {
    await flush()
    window.filterAndRender()
    expect(cards()).toBe(12)
    expect(document.getElementById('pagination').textContent).toContain('第 1/2 页 · 13 人')
  })

  it('按关键词搜索过滤', async () => {
    await flush()
    document.getElementById('s-search').value = '张明宇'
    window.filterAndRender()
    expect(cards()).toBe(1)
  })

  it('按班级过滤', async () => {
    await flush()
    document.getElementById('s-class').value = 'c2'
    window.filterAndRender()
    expect(cards()).toBe(3) // s2/s4/s6
  })

  it('按主导障碍过滤', async () => {
    await flush()
    document.getElementById('s-barrier').value = 'reading'
    window.filterAndRender()
    expect(cards()).toBe(1)
  })

  it('无匹配时显示空态', async () => {
    await flush()
    document.getElementById('s-search').value = '不存在的学生'
    window.filterAndRender()
    expect(cards()).toBe(0)
    expect(document.getElementById('card-grid').textContent).toContain('暂无匹配学生')
  })

  it('分页：goPage(2) 显示第 2 页 1 人', async () => {
    await flush()
    window.filterAndRender()
    window.goPage(2)
    expect(cards()).toBe(1)
    expect(document.getElementById('pagination').textContent).toContain('第 2/2 页 · 13 人')
  })

  it('XSS：学生姓名转义，且卡片有障碍标签', async () => {
    await flush()
    window.filterAndRender()
    const html = document.getElementById('card-grid').innerHTML
    expect(html).not.toContain('<script>alert')
    expect(html).toContain('&lt;script&gt;')
    expect(html).toContain('概念 85%')  // s1 概念主导
  })
})

describe('openDrawer / closeDrawer', () => {
  it('打开 Drawer 渲染学生详情并加载弱知识点/活动', async () => {
    await flush()
    window.openDrawer('s1')
    expect(document.getElementById('drawer-backdrop').classList.contains('open')).toBe(true)
    const html = document.getElementById('drawer-content').innerHTML
    expect(html).toContain('张明宇')
    expect(html).toContain('概念理解型')
    expect(html).toContain('练习次数')
    await flush()
    expect(document.getElementById('drawer-wkp').textContent).toContain('盐类水解')
    expect(document.getElementById('drawer-activity').textContent).toContain('完成盐类水解专项')
  })

  it('未知学生 ID 不打开 Drawer', async () => {
    await flush()
    window.openDrawer('nope')
    expect(document.getElementById('drawer-backdrop').classList.contains('open')).toBe(false)
  })

  it('Drawer 内姓名做 XSS 转义', async () => {
    await flush()
    window.openDrawer('s2')
    const html = document.getElementById('drawer-content').innerHTML
    expect(html).not.toContain('<script>alert')
    expect(html).toContain('&lt;script&gt;')
  })

  it('closeDrawer 关闭并清空状态', async () => {
    await flush()
    window.openDrawer('s1')
    await flush()
    window.closeDrawer()
    expect(document.getElementById('drawer').classList.contains('open')).toBe(false)
    expect(document.getElementById('drawer-backdrop').classList.contains('open')).toBe(false)
  })
})

describe('genPlan 生成学习计划', () => {
  it('渲染计划弹窗并写入 localStorage 历史', async () => {
    await flush()
    window.openDrawer('s1')
    window.genPlan()
    await flush()
    const overlay = document.getElementById('plan-overlay')
    expect(overlay).not.toBeNull()
    const html = overlay.innerHTML
    expect(html).toContain('化学基础强化')
    expect(html).toContain('周目标')
    expect(html).toContain('每日任务')
    expect(html).toContain('障碍干预')
    expect(html).toContain('激励建议')
    expect(html).toContain('复习盐类水解')
    const plans = JSON.parse(localStorage.getItem('chemai_plans'))
    expect(plans.length).toBe(1)
    expect(plans[0].student_id).toBe('s1')
  })

  it('savePlanEdit 深路径写入 + savePlan 持久化', async () => {
    await flush()
    window.openDrawer('s1')
    window.genPlan()
    await flush()
    const el = document.createElement('div')
    el.setAttribute('data-path', 'weekly_goals.0')
    el.textContent = '攻克水解平衡'
    window.savePlanEdit(el)
    window.savePlan()
    const saved = JSON.parse(localStorage.getItem('chemai_plan_s1'))
    expect(saved.weekly_goals[0]).toBe('攻克水解平衡')
  })
})

describe('添加学生 / 邀请码', () => {
  it('submitAddStudent 空姓名/班级校验', async () => {
    await flush()
    const before = fetchCalls.filter((c) => c.opts.method === 'POST').length
    window.submitAddStudent()
    expect(document.getElementById('add-name-err').style.display).toBe('block')
    expect(document.getElementById('add-class-err').style.display).toBe('block')
    const after = fetchCalls.filter((c) => c.opts.method === 'POST').length
    expect(after).toBe(before) // 未发请求
  })

  it('submitAddStudent 有效提交 POST 并关闭弹窗', async () => {
    await flush()
    window.openAddStudent()
    expect(document.getElementById('add-modal').classList.contains('open')).toBe(true)
    document.getElementById('add-name').value = '李雷'
    document.getElementById('add-class').value = 'c1'
    window.submitAddStudent()
    await flush()
    expect(document.getElementById('add-modal').classList.contains('open')).toBe(false)
    const post = fetchCalls.find((c) => c.url.indexOf('/api/users/student') >= 0 && c.opts.method === 'POST' && c.url.indexOf('/transfer') < 0)
    expect(post).toBeTruthy()
  })

  it('generateInviteCode 显示后端邀请码', async () => {
    await flush()
    document.getElementById('invite-class').value = 'c1'
    window.generateInviteCode()
    await flush()
    expect(document.getElementById('invite-code-display').textContent).toBe('CHEM-123')
    expect(document.getElementById('invite-result').style.display).toBe('')
    expect(document.getElementById('invite-gen-btn').textContent).toBe('重新生成')
  })

  it('后端未返回邀请码时生成本地兜底码', async () => {
    await flush()
    const orig = globalThis.fetch
    globalThis.fetch = (url, opts) => {
      if (String(url).indexOf('/api/users/student') >= 0 && (opts && opts.method === 'POST') && String(url).indexOf('/transfer') < 0) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) })
      }
      return orig(url, opts)
    }
    document.getElementById('invite-class').value = 'c1'
    window.generateInviteCode()
    await flush()
    const code = document.getElementById('invite-code-display').textContent
    expect(code).toMatch(/^C1-[A-Z0-9]{6}$/)
    globalThis.fetch = orig
  })

  it('copyInviteCode 写入剪贴板', async () => {
    await flush()
    document.getElementById('invite-class').value = 'c1'
    window.generateInviteCode()
    await flush()
    window.copyInviteCode()
    await flush()
    expect(clipCalls).toContain('CHEM-123')
    expect(document.getElementById('invite-copy-btn').textContent).toBe('✓ 已复制')
  })
})

describe('转班 / 重置密码', () => {
  it('openTransfer 排除当前班级，confirmTransfer 成功关闭', async () => {
    await flush()
    window.openDrawer('s1')
    window.openTransfer()
    expect(document.getElementById('tf-student-name').textContent).toContain('张明宇')
    const opts = Array.from(document.getElementById('tf-class').options).map((o) => o.value)
    expect(opts).toEqual(['c2']) // s1 在 c1，只剩 c2
    window.confirmTransfer()
    await flush()
    expect(document.getElementById('transfer-modal').classList.contains('open')).toBe(false)
    expect(document.getElementById('drawer').classList.contains('open')).toBe(false)
  })

  it('resetPassword 确认后调用重置接口并提示', async () => {
    await flush()
    window.openDrawer('s1')
    window.resetPassword()
    await flush()
    expect(fetchCalls.some((c) => c.url.indexOf('/reset-password') >= 0 && c.opts.method === 'POST')).toBe(true)
    expect(alerts).toContain('已重置')
  })
})

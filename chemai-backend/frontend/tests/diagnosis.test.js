// diagnosis.js — window.runDiagnosis 障碍诊断测试
// stub fetch 返回诊断数据，断言班级概览统计与学生列表（排序/障碍标签/严重度/XSS）。
import { describe, it, expect } from 'vitest'

vi.hoisted(() => {
  const diagData = {
    class_barrier_distribution: { concept: 5, reading: 3, expression: 2 },
    avg_mastery: 0.72,
    students: [
      { student_id: 's1', student_name: '甲', dominant_barrier: 'concept', barrier_type: { concept: 0.85, reading: 0.1, expression: 0.05 }, weak_knowledge_points: ['盐类水解'] },
      { student_id: 's2', student_name: '<script>alert(1)</script>', dominant_barrier: 'expression', barrier_type: { concept: 0.1, reading: 0.2, expression: 0.7 }, weak_knowledge_points: [] },
      { student_id: 's3', student_name: '丙', dominant_barrier: 'reading', barrier_type: { concept: 0.2, reading: 0.5, expression: 0.3 }, weak_knowledge_points: ['审题', '读图'] }
    ]
  }
  globalThis.fetch = (url) => {
    if (String(url).indexOf('/api/diagnosis/barrier/') >= 0) return Promise.resolve({ ok: true, json: () => Promise.resolve(diagData) })
    return Promise.resolve({ ok: true, json: () => Promise.resolve({ classes: [] }) })
  }
  const cls = document.createElement('input')
  cls.id = 'diag-class'; cls.value = 'c1'
  const exam = document.createElement('input')
  exam.id = 'diag-exam'; exam.value = 'e1'
  const result = document.createElement('div')
  result.id = 'diag-result'
  document.body.append(cls, exam, result)
  globalThis.alert = () => {}
})

await import('../legacy/teacher/js/diagnosis.js')

const flush = () => new Promise((r) => setTimeout(r, 0))

describe('runDiagnosis 班级概览', () => {
  it('渲染诊断学生数 / 平均掌握度 / 需关注合计', async () => {
    await window.runDiagnosis()
    await flush()
    const html = document.getElementById('diag-result').innerHTML
    expect(html).toContain('3')      // 诊断学生
    expect(html).toContain('72%')    // 平均掌握度
    expect(html).toContain('10')     // 需关注合计 = 5+3+2
  })
})

describe('runDiagnosis 学生列表', () => {
  it('按主导障碍严重度降序排列', async () => {
    await window.runDiagnosis()
    await flush()
    const section = document.getElementById('student-list-section').innerHTML
    // s1 concept 0.85 > s2 expression 0.7 > s3 reading 0.5
    const idx1 = section.indexOf('概念理解 85%')
    const idx2 = section.indexOf('表述障碍 70%')
    const idx3 = section.indexOf('审题障碍 50%')
    expect(idx1).toBeGreaterThan(-1)
    expect(idx2).toBeGreaterThan(-1)
    expect(idx3).toBeGreaterThan(-1)
    expect(idx1).toBeLessThan(idx2)
    expect(idx2).toBeLessThan(idx3)
  })

  it('严重度映射 dot 类 + 弱知识点计数', async () => {
    await window.runDiagnosis()
    await flush()
    const section = document.getElementById('student-list-section').innerHTML
    expect(section).toContain('severity-dot high')   // 0.85 / 0.7 ≥ 0.6
    expect(section).toContain('severity-dot medium') // 0.5 ∈ [0.4,0.6)
    expect(section).toContain('1 弱知识点')
    expect(section).toContain('2 弱知识点')
  })

  it('XSS 转义学生姓名', async () => {
    await window.runDiagnosis()
    await flush()
    const section = document.getElementById('student-list-section').innerHTML
    expect(section).not.toContain('<script>alert')
    expect(section).toContain('&lt;script&gt;')
  })
})

describe('filterStudents 搜索过滤', () => {
  it('按关键词过滤行显示', async () => {
    await window.runDiagnosis()
    await flush()
    const search = document.getElementById('diag-search')
    search.value = '丙'
    window.filterStudents()
    const rows = document.querySelectorAll('#student-rows .student-row')
    expect(rows.length).toBe(3)
    // 只有「丙」的行可见
    const visible = Array.from(rows).filter((r) => r.style.display !== 'none')
    expect(visible.length).toBe(1)
    expect(visible[0].textContent).toContain('丙')
  })

  it('filterByBarrier 按障碍类型过滤', async () => {
    await window.runDiagnosis()
    await flush()
    window.filterByBarrier('concept')
    const rows = document.querySelectorAll('#student-rows .student-row')
    const visible = Array.from(rows).filter((r) => r.style.display !== 'none')
    expect(visible.length).toBe(1)
    expect(visible[0].getAttribute('data-barrier')).toBe('concept')
  })
})

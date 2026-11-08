// ocr.js — window.handleFiles 批量识别流程测试
// stub fetch 返回识别结果，断言 renderResults 输出的列并集 / 置信度 / XSS 转义。
import { describe, it, expect } from 'vitest'

vi.hoisted(() => {
  const calls = []
  const route = (url) => {
    if (url.indexOf('/api/ocr/recognize') >= 0) {
      return { success: true, results: [
        { student_id: 'S1', student_name: '甲', answers: { '1': 'A', '3': 'C' } },
        { student_id: 'S2', student_name: '乙', answers: { '2': 'B' } }
      ] }
    }
    if (url.indexOf('/api/ocr/confirm') >= 0) return { success: true }
    return { classes: [] }
  }
  globalThis.fetch = (url, opts) => {
    calls.push({ url, opts })
    return Promise.resolve({ ok: true, json: () => Promise.resolve(route(String(url))) })
  }
  // 建 ocr.js 需要的 DOM 节点
  const cls = document.createElement('input')
  cls.id = 'ocr-class'; cls.value = 'c1'
  const progress = document.createElement('div')
  progress.id = 'ocr-progress'
  const results = document.createElement('div')
  results.id = 'ocr-results'
  document.body.append(cls, progress, results)
  globalThis.alert = () => {}
  void calls
})

await import('../legacy/teacher/js/ocr.js')

const flush = () => new Promise((r) => setTimeout(r, 0))

describe('handleFiles 批量识别', () => {
  it('识别完成渲染列并集与行', async () => {
    await window.handleFiles([{ name: 'a.png' }, { name: 'b.png' }])
    await flush()
    const html = document.getElementById('ocr-results').innerHTML
    expect(html).toContain('<th>1</th>')
    expect(html).toContain('<th>2</th>')
    expect(html).toContain('<th>3</th>')
    expect(html).toContain('S1')
    expect(html).toContain('S2')
    expect(html).toContain('甲')
    expect(html).toContain('乙')
  })

  it('XSS 转义学生姓名', async () => {
    // 覆写 fetch 返回含 <script> 的姓名
    const orig = globalThis.fetch
    globalThis.fetch = () => Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, results: [
      { student_id: 'S9', student_name: '<script>alert(1)</script>', answers: { '1': 'A' } }
    ] }) })
    await window.handleFiles([{ name: 'x.png' }])
    await flush()
    const html = document.getElementById('ocr-results').innerHTML
    expect(html).not.toContain('<script>alert')
    expect(html).toContain('&lt;script&gt;')
    globalThis.fetch = orig
  })

  it('置信度映射颜色（高 ≥85% 绿）', async () => {
    // 固定 Math.random → confidence 恒定，可断言具体百分比
    vi.spyOn(Math, 'random').mockReturnValue(0.9)  // 0.65 + 0.27 = 0.92
    await window.handleFiles([{ name: 'a.png' }])
    await flush()
    const html = document.getElementById('ocr-results').innerHTML
    expect(html).toContain('92%')
    expect(html).toContain('conf-high')
    vi.restoreAllMocks()
  })

  it('无识别结果时显示提示', async () => {
    const orig = globalThis.fetch
    globalThis.fetch = () => Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, results: [] }) })
    await window.handleFiles([{ name: 'x.png' }])
    await flush()
    expect(document.getElementById('ocr-results').innerHTML).toContain('无识别结果')
    globalThis.fetch = orig
  })
})

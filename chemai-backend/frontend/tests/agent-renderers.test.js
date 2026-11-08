// agent-renderers.js — window.ChemRender(toolName, data) 测试
// 将 SSE tool_result JSON 渲染为富 HTML 组件，纯函数无 DOM 依赖
import { describe, it, expect } from 'vitest'
import '../legacy/teacher/js/agent-renderers.js'

const render = (tool, data) => window.ChemRender(tool, data)
const renderers = () => window.ChemRenderers

describe('ChemRender 分发', () => {
  it('注册实际工具渲染器', () => {
    const r = renderers()
    expect(typeof r.generate_questions).toBe('function')
    expect(typeof r.diagnose_barrier).toBe('function')
    expect(typeof r.balance_equation).toBe('function')
    expect(typeof r.parser_ocr).toBe('function')
    expect(typeof r.import_exam_paper).toBe('function')
  })

  it('未知工具回退 JSON 渲染', () => {
    const out = render('no_such_tool', { foo: 1 })
    expect(out).toContain('<pre')
    // esc() 会把引号转义为 &quot;，所以只断言键与值
    expect(out).toContain('foo')
    expect(out).toContain(': 1')
  })
})

describe('出题卡片 renderQuestionCards', () => {
  it('空数据返回暂无题目', () => {
    expect(render('generate_questions', {})).toContain('暂无题目')
    expect(render('generate_questions', { questions: [] })).toContain('暂无题目')
  })

  it('渲染题目序号、答案、难度标签', () => {
    const out = render('generate_questions', { questions: [
      { content: '下列属于混合物的是？', answer: 'B', difficulty: 'medium', overall_status: 'passed' }
    ] })
    expect(out).toContain('#1')
    expect(out).toContain('下列属于混合物的是？')
    expect(out).toContain('答案: B')
    expect(out).toContain('tag-medium')
    expect(out).toContain('✓ 通过')
  })

  it('options 兼容字符串与数组', () => {
    const out = render('generate_questions', {
      questions: [{ content: 'q', options: 'A.甲,B.乙', overall_status: 'passed' }]
    })
    expect(out).toContain('A.甲')
    expect(out).toContain('B.乙')
    const out2 = render('generate_questions', {
      questions: [{ content: 'q', options: ['A.甲', 'B.乙'] }]
    })
    expect(out2).toContain('A.甲')
  })

  it('XSS 转义题目内容与知识点', () => {
    const out = render('generate_questions', {
      questions: [{ content: '<img src=x onerror=alert(1)>', knowledge_points: ['<script>'] }]
    })
    expect(out).not.toContain('<img src=x')
    expect(out).toContain('&lt;img')
    expect(out).toContain('&lt;script&gt;')
  })
})

describe('搜索结果 renderSearchResults', () => {
  it('空结果提示', () => {
    expect(render('search_exam_bank', {})).toContain('题库中暂无匹配结果')
  })

  it('最多渲染 5 题并提示剩余', () => {
    const qs = Array.from({ length: 7 }, (_, i) => ({ content: `题${i}`, answer: 'A', source: '真题', year: '2024' }))
    const out = render('search_exam_bank', { questions: qs, total: 7 })
    expect(out).toContain('找到 7 道真题')
    expect(out.match(/题\d/g).length).toBe(5)
    expect(out).toContain('还有 2 题')
  })

  it('内容截断到 150 字符', () => {
    const long = 'x'.repeat(300)
    const out = render('search_exam_bank', { questions: [{ content: long }] })
    expect(out).not.toContain('x'.repeat(200))
  })
})

describe('OCR 结果表 renderOcrTable', () => {
  it('空结果提示', () => {
    expect(render('parser_ocr', {})).toContain('无识别结果')
  })

  it('列取全部学生答案键的并集并排序', () => {
    const out = render('parser_ocr', { results: [
      { student_id: 'S1', student_name: '甲', answers: { '3': { answer: 'C', confidence: 0.9 }, '1': { answer: 'A', confidence: 0.95 } } },
      { student_id: 'S2', student_name: '乙', answers: { '2': { answer: 'B', confidence: 0.5 } } }
    ] })
    expect(out).toContain('<th>1</th>')
    expect(out).toContain('<th>2</th>')
    expect(out).toContain('<th>3</th>')
    expect(out).toContain('S1')
    expect(out).toContain('S2')
    expect(out).toContain('95%')
    expect(out).toContain('50%')
  })

  it('置信度映射颜色（>=0.85 绿 / >=0.6 黄 / 其余红）', () => {
    const out = render('ocr_result', { results: [
      { student_id: 'S1', answers: { '1': { answer: 'A', confidence: 0.9 }, '2': { answer: 'B', confidence: 0.7 }, '3': { answer: 'C', confidence: 0.4 } } }
    ] })
    expect(out).toContain('color:#2F855A')
    expect(out).toContain('color:#e6a817')
    expect(out).toContain('color:#C53030')
  })
})

describe('配平 renderBalanceResult', () => {
  it('状态标签与颜色', () => {
    const ok = render('balance_equation', { overall_status: 'passed', equation: 'H2+O2=2H2O' })
    expect(ok).toContain('✓ 配平正确')
    expect(ok).toContain('color:#2c6e49')
    const blocked = render('balance_equation', { overall_status: 'blocked' })
    expect(blocked).toContain('✗ 配平错误')
  })

  it('error 时返回错误卡', () => {
    const err = render('balance_equation', { overall_status: 'error', error: '无法解析' })
    expect(err).toContain('无法解析')
    expect(err).toContain('color:#C53030')
  })

  it('左右原子数不平衡标出差值', () => {
    const out = render('balance_equation', {
      overall_status: 'warning',
      balance: [
        { element: 'H', left_count: 2, right_count: 2 },
        { element: 'O', left_count: 2, right_count: 1 }
      ]
    })
    expect(out).toContain('H')
    expect(out).toContain('O')
    expect(out).toContain('✗ 差1')
  })
})

describe('化学导师 renderTutorAnswer', () => {
  it('换行转 <br> 并保留模型名', () => {
    const out = render('chemistry_tutor', { answer: '第一行\n第二行', model: 'deepseek' })
    expect(out).toContain('第一行<br>第二行')
    expect(out).toContain('deepseek')
  })

  it('转义危险内容', () => {
    const out = render('chemistry_tutor', { answer: '<script>alert(1)</script>' })
    expect(out).not.toContain('<script>alert')
    expect(out).toContain('&lt;script&gt;')
  })

  it('空答案提示', () => {
    expect(render('chemistry_tutor', {})).toContain('暂无回复')
  })
})

describe('实验报告 renderExperiment', () => {
  it('渲染各区块', () => {
    const out = render('simulate_experiment', {
      experiment_name: '电解水',
      objectives: ['验证水的组成'],
      equipment: ['烧杯', '导线'],
      steps: ['接通电源'],
      expected_phenomena: ['产生气泡'],
      equations: ['2H2O = 2H2 + O2'],
      safety: ['防止短路']
    })
    expect(out).toContain('电解水')
    expect(out).toContain('实验目的')
    expect(out).toContain('验证水的组成')
    expect(out).toContain('烧杯')
    expect(out).toContain('实验步骤')
    expect(out).toContain('2H2O')
    expect(out).toContain('安全提醒')
  })

  it('错误时返回红色错误卡', () => {
    const out = render('simulate_experiment', { error: '模拟失败' })
    expect(out).toContain('color:#C53030')
    expect(out).toContain('模拟失败')
  })

  it('空数据回退 JSON', () => {
    expect(render('simulate_experiment', {})).toContain('<pre')
  })
})

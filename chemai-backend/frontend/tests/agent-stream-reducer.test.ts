/* agent-stream-reducer.test.ts — Agent 对话 SSE 流 → 消息状态回归测试（evals）
 * 事件形状与后端 agent/langgraph_sse_v2.py 实际输出对齐：
 *   tool_call    {type, name, tool, args}
 *   tool_result  {type, name, tool, success, result: "<JSON 字符串>"}
 *   component    {type, component, params}
 *   phase        {type, phase, message?}
 * 覆盖三个用户反馈问题的回归：
 *   ① tool_result.result 为 JSON 字符串 → 卡片必须解析出数据
 *   ② component 事件 → 追加内联面板，不得跳页
 *   ③ phase → 进入状态（由气泡渲染，见 chat-bubble.test.tsx）
 */
import { describe, expect, it, vi } from 'vitest'
import { createStreamState, reduceAgentEvent, seedNewTurn, updateApprovalStatus } from '../src/lib/agent-stream-reducer'
import type { StreamState } from '../src/lib/agent-stream-reducer'

let n = 0
const newId = () => `id${n++}`
const ctx = { newId }

/* 与后端 v2 适配器一致的构造器 */
const toolCall = (name: string, args: unknown = {}) => ({
  type: 'tool_call' as const,
  name,
  tool: name.split('_')[0],
  args,
})
const toolResult = (name: string, result: string, success = true) => ({
  type: 'tool_result' as const,
  name,
  tool: name.split('_')[0],
  success,
  result,
})

describe('问题①回归：tool_result JSON 字符串必须解析为卡片数据', () => {
  it('generate_questions 的 result 字符串 → 卡片 done 且 data 含 questions', () => {
    let s: StreamState = createStreamState()
    s = reduceAgentEvent(s, toolCall('generate_questions', { quantity: 2 }), ctx)
    s = reduceAgentEvent(
      s,
      toolResult(
        'generate_questions',
        JSON.stringify({ questions: [{ content: '配平：Fe2O3 + CO', answer: '3CO', overall_status: 'passed' }] }),
      ),
      ctx,
    )
    const card = s.items.find((it) => it.kind === 'tool')
    expect(card).toBeDefined()
    if (card?.kind === 'tool') {
      expect(card.card.status).toBe('done')
      expect(card.card.data).toEqual(expect.objectContaining({ questions: expect.any(Array) }))
      const qs = (card.card.data as { questions: { content: string }[] }).questions
      expect(qs[0].content).toContain('Fe2O3')
    }
  })

  it('tool_call 先追加「执行中」卡片（点击可展开前不可见内容）', () => {
    let s = createStreamState()
    s = reduceAgentEvent(s, toolCall('balance_equation'), ctx)
    const card = s.items.find((it) => it.kind === 'tool')
    if (card?.kind === 'tool') {
      expect(card.card.status).toBe('running')
      expect(card.card.data).toBeUndefined()
    }
  })

  it('tool_error → 卡片标记失败', () => {
    let s = createStreamState()
    s = reduceAgentEvent(s, toolCall('web_search'), ctx)
    s = reduceAgentEvent(
      s,
      { type: 'tool_error', name: 'web_search', message: '网络不可用' },
      ctx,
    )
    const card = s.items.find((it) => it.kind === 'tool')
    if (card?.kind === 'tool') {
      expect(card.card.status).toBe('error')
    }
  })

  it('route_to_* 内部路由工具不显示卡片', () => {
    let s = createStreamState()
    s = reduceAgentEvent(s, toolCall('route_to_student'), ctx)
    expect(s.items).toHaveLength(0)
  })

  it('非法 JSON 的 result 兜底为 {raw}', () => {
    let s = createStreamState()
    s = reduceAgentEvent(s, toolCall('web_search'), ctx)
    s = reduceAgentEvent(s, toolResult('web_search', '纯文本结果'), ctx)
    const card = s.items.find((it) => it.kind === 'tool')
    if (card?.kind === 'tool') {
      expect(card.card.status).toBe('done')
      expect(card.card.data).toEqual(expect.objectContaining({ raw: '纯文本结果' }))
    }
  })

  it('旧协议 data 对象仍兼容', () => {
    let s = createStreamState()
    s = reduceAgentEvent(s, toolCall('diagnose_barrier'), ctx)
    s = reduceAgentEvent(
      s,
      { type: 'tool_result', name: 'diagnose_barrier', success: true, data: { students: [] } },
      ctx,
    )
    const card = s.items.find((it) => it.kind === 'tool')
    if (card?.kind === 'tool') {
      expect(card.card.data).toEqual({ students: [] })
    }
  })
})

describe('问题②回归：component 事件内联面板，禁止跳页', () => {
  it('exam-workbench → 追加 panel 消息项，onNavigate 不被调用', () => {
    const onNavigate = vi.fn()
    let s = createStreamState()
    s = reduceAgentEvent(
      s,
      { type: 'component', component: 'exam-workbench', params: { difficulty: 'medium', knowledge_points: ['氧化还原'] } },
      { newId, onNavigate },
    )
    const panel = s.items.find((it) => it.kind === 'panel')
    expect(panel).toBeDefined()
    if (panel?.kind === 'panel') {
      expect(panel.component).toBe('exam-workbench')
      expect(panel.params.difficulty).toBe('medium')
      expect(panel.params.knowledge_points).toEqual(['氧化还原'])
    }
    expect(onNavigate).not.toHaveBeenCalled()
  })

  it('diagnosis / learning_plan / student-list 同样内联', () => {
    for (const component of ['diagnosis', 'learning_plan', 'student-list']) {
      let s = createStreamState()
      s = reduceAgentEvent(s, { type: 'component', component, params: {} }, ctx)
      const panel = s.items.find((it) => it.kind === 'panel')
      expect(panel).toBeDefined()
      if (panel?.kind === 'panel') expect(panel.component).toBe(component)
    }
  })

  it('S2 面板去重：同一 component 再次到达 → 替换而非追加', () => {
    let s = createStreamState()
    s = reduceAgentEvent(
      s,
      { type: 'component', component: 'diagnosis', params: { student: 'v1' } },
      ctx,
    )
    const firstId = s.items.find((it) => it.kind === 'panel')?.id
    s = reduceAgentEvent(
      s,
      { type: 'component', component: 'diagnosis', params: { student: 'v2' } },
      ctx,
    )
    const panels = s.items.filter((it) => it.kind === 'panel')
    expect(panels).toHaveLength(1)
    if (panels[0]?.kind === 'panel') {
      expect(panels[0].params.student).toBe('v2') // 新参数生效
      expect(panels[0].id).not.toBe(firstId) // 触发重渲染
    }
  })

  it('S2 面板去重：不同 component 互不影响', () => {
    let s = createStreamState()
    s = reduceAgentEvent(s, { type: 'component', component: 'diagnosis', params: {} }, ctx)
    s = reduceAgentEvent(s, { type: 'component', component: 'learning_plan', params: {} }, ctx)
    expect(s.items.filter((it) => it.kind === 'panel')).toHaveLength(2)
  })

  it('DSH 式思考行：工具调用前有文本的 AI 气泡折叠为 think', () => {
    let s = createStreamState()
    s = reduceAgentEvent(s, { type: 'text', content: '我来诊断张浩宇的学习障碍。' }, ctx)
    const aiItem = s.items.find((it) => it.kind === 'ai')
    expect(aiItem).toBeDefined()
    s = reduceAgentEvent(s, { type: 'tool_call', name: 'diagnose_barrier', args: {} }, ctx)
    const think = s.items.find((it) => it.kind === 'think')
    expect(think).toBeDefined()
    if (think?.kind === 'think') expect(think.text).toContain('我来诊断')
    expect(s.items.filter((it) => it.kind === 'ai')).toHaveLength(0)
  })

  it('DSH 式思考行：无文本直开工具时，空占位气泡被移除（白块不复现）', () => {
    let s = createStreamState()
    // 模拟 seedNewTurn 的空 AI 占位
    s = { ...s, items: [{ id: 'ai-placeholder', kind: 'ai', text: '', streaming: true }], aiId: 'ai-placeholder' }
    s = reduceAgentEvent(s, { type: 'tool_call', name: 'read', args: {} }, ctx)
    expect(s.items.find((it) => it.kind === 'ai')).toBeUndefined()
    expect(s.aiId).toBeNull()
    expect(s.items.some((it) => it.kind === 'tool' && it.card.tool === 'read')).toBe(true)
  })

  it('思考行折叠后，后续文本必须创建新的 AI 气泡（2026-08：多步骤任务最终总结被吞回归）', () => {
    // 用户场景：resume/多步骤中 LLM 先输出思考文本 → 调工具 → 折叠为 think →
    // 工具完成后 LLM 输出最终总结。aiId 若不清空，总结文本会尝试追加到
    // 已变成 think 的旧气泡（kind 不匹配）→ 整段回复静默丢失。
    let s = createStreamState()
    s = reduceAgentEvent(s, { type: 'text', content: '学习计划已成功发送给李世睿。现在执行第6步。' }, ctx)
    s = reduceAgentEvent(s, { type: 'tool_call', name: 'send_report_to_parent', args: {} }, ctx)
    // 思考行已折叠，且 aiId 必须失效
    expect(s.items.find((it) => it.kind === 'think')).toBeDefined()
    expect(s.aiId).toBeNull()
    // 工具完成后 LLM 输出最终总结 → 必须创建新 AI 气泡并完整显示
    s = reduceAgentEvent(s, { type: 'text', content: '全部任务已完成：诊断→出题→方案→已发送学生并同步家长。' }, ctx)
    const ais = s.items.filter((it) => it.kind === 'ai')
    expect(ais).toHaveLength(1)
    if (ais[0]?.kind === 'ai') {
      expect(ais[0].text).toBe('全部任务已完成：诊断→出题→方案→已发送学生并同步家长。')
    }
    // 分片继续追加到新气泡
    s = reduceAgentEvent(s, { type: 'text', content: '（补充说明）' }, ctx)
    const ais2 = s.items.filter((it) => it.kind === 'ai')
    expect(ais2).toHaveLength(1)
    if (ais2[0]?.kind === 'ai') {
      expect(ais2[0].text).toContain('（补充说明）')
    }
  })

  it('确定性审批重放：无挂起项的合成 tool_result 补一张结果卡（批准后不断链）', () => {
    let s = createStreamState()
    // 原始 read 卡已消费（toolPending 已清空）
    s = reduceAgentEvent(s, { type: 'tool_call', name: 'read', args: {} }, ctx)
    s = reduceAgentEvent(
      s,
      { type: 'tool_result', name: 'read', success: true, result: '{"content": "文件内容", "path": "x.txt"}' },
      ctx,
    )
    s = reduceAgentEvent(
      s,
      { type: 'tool_result', name: 'read', success: true, result: '{"content": "重放内容", "path": "x.txt"}' },
      ctx,
    )
    const readCards = s.items.filter((it) => it.kind === 'tool' && it.card.tool === 'read')
    expect(readCards).toHaveLength(2) // 原卡 + 重放结果卡
    const late = readCards[1]
    if (late?.kind === 'tool' && late.card.data && typeof late.card.data === 'object') {
      expect((late.card.data as { content?: string }).content).toBe('重放内容')
    } else {
      throw new Error('late card data missing')
    }
  })

  it('显式 navigate 事件仍触发跳转（与内联面板区分）', () => {
    const onNavigate = vi.fn()
    let s = createStreamState()
    s = reduceAgentEvent(s, { type: 'navigate', page: 'students' }, { newId, onNavigate })
    expect(onNavigate).toHaveBeenCalledWith('/students', {})
    expect(s.items.filter((it) => it.kind === 'panel')).toHaveLength(0)
  })

  it('navigate 事件携带 params（focus/action）→ 透传给跳转回调（旧版行为恢复）', () => {
    const onNavigate = vi.fn()
    let s = createStreamState()
    s = reduceAgentEvent(
      s,
      { type: 'navigate', page: 'students', params: { focus: '202610201', action: 'plan' } },
      { newId, onNavigate },
    )
    expect(onNavigate).toHaveBeenCalledWith('/students', { focus: '202610201', action: 'plan' })
  })
})

describe('问题③回归：phase 进入状态（气泡内展示）', () => {
  it('phase 更新 state.phase 文案', () => {
    let s = createStreamState()
    s = reduceAgentEvent(s, { type: 'phase', phase: 'thinking' }, ctx)
    expect(s.phase).toBe('分析中…')
    s = reduceAgentEvent(s, { type: 'phase', phase: 'executing' }, ctx)
    expect(s.phase).toBe('执行中…')
  })

  it('phase 映射 thinking-orbs 动画状态：thinking→breathing / executing→working / reply→composing', () => {
    let s = createStreamState()
    expect(s.orb).toBe('')
    s = reduceAgentEvent(s, { type: 'phase', phase: 'thinking' }, ctx)
    expect(s.orb).toBe('breathing')
    s = reduceAgentEvent(s, { type: 'phase', phase: 'executing' }, ctx)
    expect(s.orb).toBe('working')
    s = reduceAgentEvent(s, { type: 'phase', phase: 'reply' }, ctx)
    expect(s.orb).toBe('composing')
    // 等待审批：停动画（审批卡是交互 UI）
    s = reduceAgentEvent(s, { type: 'phase', phase: 'awaiting_approval', message: '确认' }, ctx)
    expect(s.orb).toBe('')
  })

  it('tool_call / step 执行阶段 → working 动画', () => {
    let s = createStreamState()
    s = reduceAgentEvent(s, toolCall('generate_questions', { quantity: 2 }), ctx)
    expect(s.orb).toBe('working')
    s = reduceAgentEvent(s, { type: 'step', skill: 'diagnose_barrier', current: 1 }, ctx)
    expect(s.orb).toBe('working')
  })

  it('web_search / search_exam_bank 专用「搜索中…」+ searching 动画', () => {
    let s = createStreamState()
    s = reduceAgentEvent(s, toolCall('web_search', { query: '2024 高考化学真题' }), ctx)
    expect(s.phase).toBe('搜索中…')
    expect(s.orb).toBe('searching')
    s = reduceAgentEvent(s, toolCall('search_exam_bank', { keyword: '物质的量' }), ctx)
    expect(s.phase).toBe('搜索中…')
    expect(s.orb).toBe('searching')
  })

  it('seedNewTurn 发送后初始为 breathing（配合「分析中…」）', () => {
    const { state } = seedNewTurn([], '你好', newId)
    expect(state.orb).toBe('breathing')
  })

  it('gate_open → 追加审批卡（ADR-0015 阶段 4 类型化事件）', () => {
    let s = createStreamState()
    s = reduceAgentEvent(s, { type: 'gate_open', gate_id: 'g-tool-delete_bank-aa', message: '将删除整个题库' } as never, ctx)
    const approval = s.items.find((it) => it.kind === 'approval')
    expect(approval).toBeDefined()
    if (approval?.kind === 'approval') {
      expect(approval.approval.status).toBe('pending')
      expect(approval.approval.text).toContain('删除')
    }
  })

  it('同 gate_open 重复（重连重放）→ 卡不重复（按 gate_id 去重）', () => {
    let s = createStreamState()
    s = reduceAgentEvent(s, { type: 'gate_open', gate_id: 'g-tool-a-1', message: '即将为李世睿布置练习' } as never, ctx)
    s = reduceAgentEvent(s, { type: 'gate_open', gate_id: 'g-tool-a-1', message: '即将为李世睿布置练习' } as never, ctx)
    s = reduceAgentEvent(s, { type: 'gate_open', gate_id: 'g-tool-a-1', message: '即将为李世睿布置练习' } as never, ctx)
    expect(s.items.filter((it) => it.kind === 'approval')).toHaveLength(1)
  })

  it('审批卡确认后新的一次确认仍可追加（pending 去重不误伤新请求）', () => {
    let s = createStreamState()
    s = reduceAgentEvent(s, { type: 'gate_open', gate_id: 'g-tool-a-1', message: 'm1' } as never, ctx)
    const a1 = s.items.find((it) => it.kind === 'approval')
    if (a1?.kind === 'approval') {
      a1.approval.status = 'approved'
    }
    s = reduceAgentEvent(s, { type: 'gate_open', gate_id: 'g-tool-b-2', message: '新的确认' } as never, ctx)
    expect(s.items.filter((it) => it.kind === 'approval')).toHaveLength(2)
  })

  it('updateApprovalStatus：批准/取消同步到状态（防 SSE onDone 覆盖回 pending）', () => {
    let s = createStreamState()
    s = reduceAgentEvent(s, { type: 'gate_open', gate_id: 'g-tool-a-1', message: '即将为李世睿布置练习' } as never, ctx)
    // 批准路径
    const items = updateApprovalStatus(s.items, 'approved')
    const card = items.find((it) => it.kind === 'approval')
    expect(card && card.kind === 'approval' && card.approval.status).toBe('approved')
    // 放弃路径（从原始 pending 状态独立测试）
    const items2 = updateApprovalStatus(s.items, 'abandoned')
    const card2 = items2.find((it) => it.kind === 'approval')
    expect(card2 && card2.kind === 'approval' && card2.approval.status).toBe('abandoned')
  })

  it('step 事件 → 「第 N 步：工具名」状态', () => {
    let s = createStreamState()
    s = reduceAgentEvent(s, { type: 'step', skill: 'search_exam_bank', current: 2 }, ctx)
    expect(s.phase).toContain('第 2 步')
    expect(s.phase).toContain('搜索真题')
  })

  it('tool_call 推进状态行：执行中：<工具中文名>（v2 后端不发 executing phase，工具阶段不得停在「分析中…」）', () => {
    let s = createStreamState()
    s = reduceAgentEvent(s, { type: 'phase', phase: 'thinking' }, ctx)
    expect(s.phase).toBe('分析中…')
    s = reduceAgentEvent(s, toolCall('diagnose_barrier', { student_id: 's1' }), ctx)
    expect(s.phase).toBe('执行中：障碍诊断')
    // 未映射工具名 → 原样显示工具名
    s = reduceAgentEvent(s, toolCall('read', { path: '/x' }), ctx)
    expect(s.phase).toBe('执行中：read')
  })
})

describe('问题④回归：发送新消息时旧对话不得丢失（seedNewTurn）', () => {
  it('种子状态保留旧消息，首个 SSE 事件到达后旧消息仍在', () => {
    // 模拟已有两轮对话的消息列表
    const prevItems = [
      { id: 'old1', kind: 'user' as const, text: '第一轮问题' },
      { id: 'old2', kind: 'ai' as const, text: '第一轮回答' },
      { id: 'old3', kind: 'user' as const, text: '第二轮问题' },
      { id: 'old4', kind: 'ai' as const, text: '第二轮回答' },
    ]
    let n = 100
    const newId = () => `n${n++}`
    const { state, items } = seedNewTurn(prevItems, '第三轮问题', newId)
    expect(items).toHaveLength(6) // 4 旧 + 用户 + AI
    expect(items[4]).toEqual({ id: 'n100', kind: 'user', text: '第三轮问题' })
    expect(items[5]).toEqual({ id: 'n101', kind: 'ai', text: '', streaming: true })

    // 首个 SSE 事件（phase）到达：reducer 必须基于种子状态，旧消息保留
    const next = reduceAgentEvent(state, { type: 'phase', phase: 'thinking' }, { newId })
    expect(next.items).toHaveLength(6)
    expect(next.items[0]).toEqual(prevItems[0])
    expect(next.items[3]).toEqual(prevItems[3])

    // text 事件累积到新 AI 消息，旧消息仍完整
    const next2 = reduceAgentEvent(next, { type: 'text', content: '第三轮回答' }, { newId })
    const texts = next2.items.map((it) => (it.kind === 'user' ? `U:${it.text}` : it.kind === 'ai' ? `A:${it.text}` : ''))
    expect(texts).toEqual([
      'U:第一轮问题',
      'A:第一轮回答',
      'U:第二轮问题',
      'A:第二轮回答',
      'U:第三轮问题',
      'A:第三轮回答',
    ])
  })

  it('组件事件（内联面板）追加后旧消息仍保留', () => {
    const prevItems = [{ id: 'old1', kind: 'user' as const, text: '旧问题' }]
    let n = 0
    const newId = () => `n${n++}`
    const { state } = seedNewTurn(prevItems, '新问题', newId)
    const next = reduceAgentEvent(
      state,
      { type: 'component', component: 'exam-workbench', params: {} },
      { newId },
    )
    expect(next.items.some((it) => it.kind === 'user' && it.text === '旧问题')).toBe(true)
    expect(next.items.some((it) => it.kind === 'panel')).toBe(true)
    expect(next.items).toHaveLength(4) // 旧 + 用户 + AI + 面板
  })
})

describe('问题⑤回归：exam_images 题目附图事件必须挂到搜索卡片（agent 找真题不丢图）', () => {
  it('tool_result 之后到达的 exam_images → 追加到 search_exam_bank 卡片 data.images', () => {
    let s: StreamState = createStreamState()
    s = reduceAgentEvent(s, toolCall('search_exam_bank', { keyword: '有机' }), ctx)
    s = reduceAgentEvent(
      s,
      toolResult(
        'search_exam_bank',
        JSON.stringify({
          text: '**第1题**  🏫 本地题库 · 2020 全国卷 第T2题\n> 题目内容',
          images: [{ q_index: 0, title: '第1题 · 题目附图', urls: ['/static/figures/x.png'] }],
        }),
      ),
      ctx,
    )
    s = reduceAgentEvent(
      s,
      {
        type: 'exam_images',
        q_index: 1,
        title: '第2题 · 题目附图',
        urls: ['/static/figures/01_全国卷/2020/figures/page_02.png'],
      },
      ctx,
    )
    const card = s.items.find((it) => it.kind === 'tool')
    expect(card).toBeDefined()
    if (card?.kind === 'tool') {
      expect(card.card.status).toBe('done')
      const data = card.card.data as { text: string; images: { q_index: number; title: string; urls: string[] }[] }
      expect(data.text).toContain('第1题')
      // tool_result 自带 1 条附图，exam_images 事件追加 1 条
      expect(data.images).toHaveLength(2)
      expect(data.images[1].q_index).toBe(1)
      expect(data.images[1].urls[0]).toContain('page_02.png')
    }
  })

  it('没有搜索卡片时 exam_images 事件安全忽略（不崩溃）', () => {
    let s = createStreamState()
    s = reduceAgentEvent(s, { type: 'exam_images', q_index: 0, urls: ['/static/figures/x.png'] }, ctx)
    expect(s.items).toHaveLength(0)
  })

  it('exam_images 不触发跳页', () => {
    const onNavigate = vi.fn()
    let s = createStreamState()
    s = reduceAgentEvent(
      s,
      { type: 'exam_images', q_index: 0, urls: ['/static/figures/x.png'] },
      { newId, onNavigate },
    )
    expect(onNavigate).not.toHaveBeenCalled()
  })
})

describe('文本流', () => {
  it('text 分片累积到同一条 AI 消息', () => {
    let s = createStreamState()
    s = reduceAgentEvent(s, { type: 'text', content: '你好' }, ctx)
    s = reduceAgentEvent(s, { type: 'text', content: '，老师' }, ctx)
    const ai = s.items.find((it) => it.kind === 'ai')
    expect(ai).toBeDefined()
    if (ai?.kind === 'ai') {
      expect(ai.text).toBe('你好，老师')
      expect(ai.streaming).toBe(true)
    }
    expect(s.aiId).not.toBeNull()
  })

  it('error 事件 → 追加系统提示', () => {
    let s = createStreamState()
    s = reduceAgentEvent(s, { type: 'error', message: '服务不可用', recoverable: true }, ctx)
    const sys = s.items.find((it) => it.kind === 'system')
    expect(sys).toBeDefined()
    if (sys?.kind === 'system') expect(sys.text).toContain('服务不可用')
  })
})

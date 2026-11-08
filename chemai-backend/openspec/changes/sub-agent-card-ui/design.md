## Context

当前子 Agent 的输出通过 `last_result_text` → `finalize()` → 一次性文本 chunk 流到前端。这导致：1）LLM 废话直接出现在对话框；2）Markdown/纯文本重复输出；3）无视觉隔离。参考 Claude Code、Cursor、ChatGPT 的设计——子 Agent 活动放在折叠卡片中，标题栏显示状态+耗时，时间线展示工具调用，结果默认收起。

## Goals / Non-Goals

**Goals:**
- 子 Agent 输出通过可折叠卡片渲染，不直接出现在对话框正文
- 卡片显示：子 Agent 名称、状态指示器、耗时、工具调用时间线
- 卡片默认折叠（只显示标题栏），用户可展开查看结果
- SSE 事件协议清晰：`subagent_start` / `subagent_end`
- 活动时间线实时更新（工具调用逐条追加）

**Non-Goals:**
- 不改子 Agent 内部逻辑（ReAct、prompt、GuardState 全保留）
- 不实现双面板布局（保持单对话框）
- 不引入新的前端框架/依赖

## Decisions

### D1: 卡片 HTML 结构

```
┌─────────────────────────────────────┐
│ ▶ 辅导专家 · ✓ 完成 · 1工具 · 5s   │  ← 标题栏，始终可见
├─────────────────────────────────────┤
│ > 调用 balance_equation             │  ← 时间线（子Agent的工具调用）
├─────────────────────────────────────┤
│ ◆ 结果 (点击展开)                   │  ← 结果区，默认折叠
│   Cu + 2H₂SO₄ → CuSO₄ + SO₂ + 2H₂O │
└─────────────────────────────────────┘
```

### D2: SSE 事件定义

`subagent_start` 在 `feed()` 的 `on_chain_start` 中 emit，`subagent_tool` 在 `feed()` 中 emit，
`subagent_end` 在 `finalize()` 中 emit（此时 elapsed/tool_count 已知，result 从 state 读取）。

```json
// 子Agent启动时 (feed)
{"type": "subagent_start", "agent": "tutor_expert", "started_at": 1719200000.0}

// 子Agent内部工具调用 (feed)
{"type": "subagent_tool", "agent": "tutor_expert", "phase": "start", "name": "balance_equation"}
{"type": "subagent_tool", "agent": "tutor_expert", "phase": "end", "name": "balance_equation", "success": true}

// 子Agent完成时 (finalize)
{"type": "subagent_end", "agent": "tutor_expert", "elapsed": 5.2, "tool_count": 1, "result": "Cu + 2H₂SO₄ → ...", "error": null}
```

**数据流**: `feed()` 在 `on_chain_start` 时记录 `_sub_agent_start` 和 `_active_sub_agent`，
在 `on_chain_end` 时计算 elapsed 存为实例变量，在 `on_tool_start/end` 时 emit `subagent_tool` 并计 tool_count。
`finalize()` 收到 `last_result_text` 后，结合已存的 elapsed/tool_count/agent 组装 `subagent_end`。

### D3: 前端卡片状态机

```
idle → subagent_start → card 显示 (running)
    → subagent_tool (start) → 时间线追加 "调用 X..."
    → subagent_tool (end) → 时间线更新 "✓ X 完成"
    → subagent_end → 状态变为 done，填入 result，全部折叠
```

### D4: Result 不流式，卡片不阻塞对话流

子Agent 的结果在 `subagent_end` 中一次性携带，不流式分块。原因：1）卡片默认折叠，流式无意义；2）简化实现。卡片插入位置：当前活动消息之后、后续对话之前。

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| Result 不流式 → 长结果等待时间长（5-10s 无输出）| 标题栏 + 时间线在子Agent执行期间实时更新，用户能看到进度 |
| 卡片 UI 与现有 agent.js 结构冲突 | 新增独立 `addSubAgentCard()` 函数，不修改现有 addToolCard/addText 逻辑 |
| 子Agent 失败时卡片无内容 | subagent_end 包含 error 字段（子Agent异常时 result 为 `{"error": true, "result": "..."}`），卡片标题栏显示红色错误状态 |
| Resume 端点创建新 adapter 丢失子Agent状态 | 已知前置问题，本 change 不修复。Resume 时子Agent 不在执行中（interrupt 发生在 request_approval 之前），实际不受影响 |
| 子Agent 结果不纳入 message_history | 子Agent 结果不追加到 `full_reply`/`message_history`。这是有意的——子Agent 输出是中间产物，对话上下文只需要 coordinator 的最终响应。多轮对话通过 state 的 shared_context 保持连续性 |

## Context

参考 Open WebUI、多个 LangGraph 社区项目的实践：用 `<think>` / `</think>` SSE 标记分离工具执行过程和最终答案。工具调用在可折叠面板里，用户不看就不展开。最终答案流式输出到对话框。

## Goals / Non-Goals

**Goals:**
- 工具/子Agent 过程包在 `<think>...</think>` 内，前端渲染为可折叠面板
- 最终答案通过 `text` 事件流式输出到对话框（每 8 字符一块）
- 对话区域干净：只有最终答案，没有工具调用泄漏

**Non-Goals:**
- 不改子 Agent 内部 ReAct 逻辑
- 不新增/删除 SSE 事件类型
- 不引入新前端依赖

## Decisions

### D1: `<think>` 标记作为独立 SSE 行

```python
yield "data: <think>\n\n"   # 面板开始
# ... 工具事件全在这中间 ...
yield "data: </think>\n\n"  # 面板结束
```

不是 JSON 包裹的 `type: "think"`，而是纯文本 `data: <think>`。与 Open WebUI 协议兼容。

### D2: 前端处理 `<think>` 标记

SSE reader 的 line 处理中，检测 `payload === '<think>'` 和 `payload === '</think>'`：
- `<think>` → 创建可折叠面板 DOM，后续 `tool_call`/`subagent_*` 事件渲染到面板内
- `</think>` → 关闭面板（折叠到摘要行），后续 `text` 事件渲染到对话框
- 不匹配标记时：在面板内则渲染到面板，否则按现有逻辑处理

### D3: 事件路由

```
data: {"type":"phase","phase":"thinking"}    → 状态栏"分析中..."
data: <think>                                 → 创建折叠面板
data: {"type":"tool_call","name":"route_to_tutor_expert"}   → 面板内工具卡片
data: {"type":"tool_result","name":"route_to_tutor_expert"} → 面板内完成
data: {"type":"subagent_start","agent":"tutor_expert"}      → 面板内时间线
data: {"type":"subagent_tool","phase":"start","name":"..."} → 面板内时间线
data: {"type":"subagent_tool","phase":"end","name":"..."}   → 面板内时间线
data: {"type":"subagent_end","agent":"tutor_expert","elapsed":5} → 面板内完成
data: </think>                                → 折叠面板
data: {"type":"text","content":"Cu"}          → 流式到对话框
data: {"type":"text","content":" + 2"}        → 流式到对话框
...
data: {"type":"done"}
data: [DONE]
```

### D4: 后端改动

`langgraph_sse.py` 的 `feed()` 中，子Agent `on_chain_start` 时 emit `data: <think>`。`on_chain_end`（depth→0）时 emit `data: </think>`。

`finalize()` 恢复 `result_text` 流式分块输出为 `text` 事件。保留 `subagent_end` 事件在 think 块内。

### D5: 前端改动

删除 `addSubAgentCard()` 函数和 `subAgentCards` 变量。新增 `_inThink` 状态标志和 think 面板 DOM 引用。新增 `addThinkPanel()` / `closeThinkPanel()` 函数。

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| `<think>` 与正常 SSE JSON 行冲突 | 前端检测 `payload === '<think>'` 优先于 `JSON.parse` |
| 工具卡片在面板内样式不同 | 复用现有 `.tool-card` CSS，面板内嵌套渲染 |
| finalize 的 text 流式仍需等子Agent完成 | 子Agent 执行的 delay 不可避免，但用户看到工具时间线在推进 |

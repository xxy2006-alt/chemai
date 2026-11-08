# Spec: Agent SSE Adapter

## ADDED Requirements

### Requirement: SSE 事件映射
系统 SHALL 将 LangGraph `astream_events(version="v2")` 输出映射为 ChemAI SSE 事件格式，与现有 `SSEAdapter` 输出完全兼容。

#### Scenario: phase:thinking 发送
- **GIVEN** SSE 流开始
- **WHEN** 在 `astream_events()` 开始前
- **THEN** 发送 `{"type": "phase", "phase": "thinking"}`
- **AND** 此事件由 channel 层 (langgraph_channel.py) 发送，非 adapter 发送

#### Scenario: text 事件映射
- **GIVEN** astream event `{"event": "on_chat_model_stream", "data": {"chunk": AIMessageChunk(content="氧化还原")}}`
- **WHEN** adapter.feed(event)
- **THEN** 返回 `["{\"type\": \"phase\", \"phase\": \"reply\"}", "{\"type\": \"text\", \"content\": \"氧化还原\"}"]`
- **AND** `phase: reply` 仅在首次 text 时发送 (状态机: `_phase` 从 "thinking" 切换为 "reply")
- **AND** 后续 text 只发 `{"type": "text", "content": ...}`

#### Scenario: tool_call 事件映射
- **GIVEN** astream event `{"event": "on_tool_start", "name": "generate_questions", "data": {"input": {"knowledge_points": "电化学", "quantity": 5}}}`
- **WHEN** adapter.feed(event)
- **THEN** 返回 SSE 包含:
  - `"type": "tool_call"`
  - `"name": "generate_questions"`
  - `"tool": "generate"` (tool 名称 `_` 前缀, 由 `_tool_category()` 提取)
  - `"args": {"knowledge_points": "电化学", "quantity": 5}` (raw dict pass-through, 由 `_serialize_args()` 处理)

#### Scenario: tool_result 事件映射
- **GIVEN** astream event `{"event": "on_tool_end", "name": "generate_questions", "data": {"output": "{\"total\": 5, \"questions\": [...]}"}}`
- **WHEN** adapter.feed(event)
- **THEN** 返回 SSE 包含:
  - `"type": "tool_result"`
  - `"name": "generate_questions"`
  - `"tool": "generate"`
  - `"success": true` (output JSON 不含 "error" key 时)
  - `"result": <原始 output 字符串, 截断至 8000 字符>`
- **AND** 收集到 `self._tool_results` 列表供 `finalize()` 提取 `_route`

#### Scenario: tool_result 失败映射
- **GIVEN** astream event on_tool_end, output = `'{"error": "学生不存在"}'`
- **WHEN** adapter.feed(event)
- **THEN** `"success": false`

### Requirement: request_approval 特殊处理
系统 SHALL 将 `request_approval` tool 的调用转换为 `phase:awaiting_approval` 事件，不发送 tool_call/tool_result。

#### Scenario: request_approval 拦截
- **GIVEN** astream event `{"event": "on_tool_start", "name": "request_approval", ...}`
- **WHEN** adapter.feed(event)
- **THEN** 不发送 `tool_call` SSE 事件
- **AND** 发送 `{"type": "phase", "phase": "awaiting_approval", "message": "<approval message>"}`
- **AND** message 从 `event["data"]["input"]["message"]` 提取

#### Scenario: request_approval tool_result 拦截
- **GIVEN** astream event `{"event": "on_tool_end", "name": "request_approval", ...}`
- **WHEN** adapter.feed(event)
- **THEN** 不发送 `tool_result` SSE 事件

### Requirement: _route 提取与剥离
系统 SHALL 从 tool 结果中提取 `_route` 字段用于导航事件，并将其从 LLM 上下文中剥离。

#### Scenario: _route 收集
- **GIVEN** tool_result 包含 `{"total": 5, "_route": {"navigate": true, "page": "exam-v2", ...}}`
- **WHEN** adapter.feed(on_tool_end) 处理该结果
- **THEN** `self._tool_results` 中包含 `{"tool_name": "generate_questions", "result": {"total": 5, "_route": {...}}}`
- **AND** SSE `tool_result.result` 字段仍包含完整 JSON (含 _route) — 前端需要 _route
- **AND** _route 在传给 LLM 的 ToolMessage 中被剥离 (由 execute_tools node 处理)

#### Scenario: finalize 发送导航事件
- **GIVEN** `self._tool_results` 中有 1 个 result 包含 `_route.navigate=True, page="exam-v2"`
- **WHEN** 调用 `adapter.finalize()`
- **THEN** 返回序列:
  1. `{"type": "navigate", "page": "exam-v2", "params": {}}`
  2. `{"type": "populate", "target": "questions", "data": {...}}` (如果 _route.populate 存在)
  3. `{"type": "action", "action": "openTab", "payload": "generate"}` (遍历 _route.actions)
  4. `{"type": "done"}`
  5. `"[DONE]"` sentinel

#### Scenario: 多个 tool 只有第一个触发导航
- **GIVEN** tool_results 中 tool_A._route.navigate=True, tool_B._route.navigate=True
- **WHEN** adapter.finalize()
- **THEN** 只发送 tool_A 的导航事件
- **AND** tool_B 的导航被忽略

### Requirement: SSE 事件字段完整性
系统 SHALL 保证所有 SSE 事件类型的必需字段与现有格式完全一致。

#### Scenario: 逐事件类型字段检查
- **GIVEN** 预定义的 SSE 事件类型规范
- **WHEN** 逐类型检查
- **THEN** phase: {type, phase}
- **AND** text: {type, content}
- **AND** tool_call: {type, name, tool, args}
- **AND** tool_result: {type, name, tool, success, result}
- **AND** navigate: {type, page, params}
- **AND** populate: {type, target, data}
- **AND** action: {type, action, payload}
- **AND** done: {type}

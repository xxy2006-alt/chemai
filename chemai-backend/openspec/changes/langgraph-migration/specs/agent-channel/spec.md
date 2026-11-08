# Spec: Agent Channel (FastAPI Endpoints)

## ADDED Requirements

### Requirement: 流式端点
系统 SHALL 提供 `POST /api/agent/chat/langgraph/stream` SSE 流式端点，复用 ChatRequest 模型。

#### Scenario: 正常 chat 请求
- **GIVEN** ChatRequest(persona="tutor", message="出3道电化学选择题", conversation_id="c123")
- **WHEN** POST /api/agent/chat/langgraph/stream
- **THEN** 返回 text/event-stream
- **AND** SSE 事件序列: phase:thinking → tool_call → tool_result → phase:reply → text* → navigate? → done → [DONE]
- **AND** HTTP 状态码 200

#### Scenario: 正常 navigate 请求 (不进 agent)
- **GIVEN** ChatRequest(persona="tutor", message="打开考试工作台")
- **WHEN** 分类器返回 type="navigate", page="exam-v2"
- **THEN** 不创建 agent 实例
- **AND** 直接发送 `{"type": "navigate", "page": "exam-v2", "params": {}}`
- **AND** 发送 done → [DONE]
- **AND** 不发送 tool_call/tool_result/text

#### Scenario: 分类器超时回退
- **GIVEN** 分类器调用超时 (>5s)
- **WHEN** 端点捕获 asyncio.TimeoutError
- **THEN** 以 tool_names=None (全量 tool) 创建 agent
- **AND** 正常执行 agent loop
- **AND** 不返回错误

#### Scenario: Agent 执行异常
- **GIVEN** agent.astream_events() 抛出未预期的 Exception
- **WHEN** 端点捕获异常
- **THEN** 发送 `{"error": "<error message>"}`
- **AND** 发送 done → [DONE]
- **AND** HTTP 状态码 200 (SSE 内联错误, 非 HTTP 错误)

### Requirement: 非流式端点
系统 SHALL 提供 `POST /api/agent/chat/langgraph` 非流式端点。

#### Scenario: 正常非流式请求
- **GIVEN** ChatRequest(persona="tutor", message="什么是氧化还原")
- **WHEN** POST /api/agent/chat/langgraph
- **THEN** 返回 JSON: `{"content": "...", "navigate": {...}|null, "populate": [...], "actions": [...]}`
- **AND** content 为 agent 最终文本回复

### Requirement: Interrupt 检测与恢复
系统 SHALL 在流式端点中检测 GraphInterrupt 并返回等待状态；通过 resume 端点恢复执行。

#### Scenario: Interrupt 检测 (异常路径)
- **GIVEN** agent 的执行中调用了 interrupt()
- **WHEN** `async for event in agent.astream_events(...)` 抛出 GraphInterrupt
- **THEN** 捕获 GraphInterrupt
- **AND** 发送 `{"type": "phase", "phase": "awaiting_approval", "message": "..."}`
- **AND** 返回 (不发送 done)
- **AND** graph 状态保存在 MemorySaver 中, 可通过 resume 恢复

#### Scenario: Interrupt 检测 (状态检查路径)
- **GIVEN** astream_events() 正常结束 (未抛异常)
- **WHEN** 调用 `agent.get_state(config)` 检查
- **THEN** 如果 `state.next` 指示等待中断: 发送 phase:awaiting_approval
- **AND** 如果 `state.next` 为空: 正常完成, 调用 adapter.finalize()

#### Scenario: Resume 端点
- **GIVEN** conversation_id="c123" 在 interrupt 等待中
- **WHEN** POST /api/agent/chat/langgraph/resume `{"conversation_id": "c123", "user_response": "approved"}`
- **THEN** 使用同一 agent graph 实例调用 `agent.ainvoke(Command(resume="approved"), config)`
- **AND** 返回流式 SSE (从 interrupt 点继续)
- **AND** 执行完成后调用 adapter.finalize() 发送 route 事件

#### Scenario: Resume 时用户输入为空
- **GIVEN** user_response=""
- **WHEN** resume 端点收到空输入
- **THEN** 以 `Command(resume="")` 继续
- **AND** agent 自行判断如何继续 (空输入 = "继续但没给具体指示")

### Requirement: 会话管理
系统 SHALL 复用 `conversation_id` 作为 LangGraph `thread_id`。

#### Scenario: 新会话
- **GIVEN** conversation_id="c_new", 无现有 session
- **WHEN** 首次请求
- **THEN** 创建 thread_id="c_new" 的 LangGraph state
- **AND** agent.ainvoke() 的 config 为 `{"configurable": {"thread_id": "c_new"}}`

#### Scenario: 同会话后续请求
- **GIVEN** conversation_id="c_new" 已存在 state
- **WHEN** 第二次请求 (同 conversation_id)
- **THEN** agent 从 checkpoint 加载历史消息
- **AND** 新消息追加到现有对话上下文

#### Scenario: 重置会话
- **GIVEN** conversation_id="c_new"
- **WHEN** POST /api/agent/chat/langgraph/reset?conversation_id=c_new
- **THEN** 删除该 thread 的 checkpoint

### Requirement: 旧端点 兼容
系统 SHALL 保留 pydantic-ai 旧端点不变。

#### Scenario: 旧端点仍可工作
- **GIVEN** 新 LangGraph 端点已上线
- **WHEN** POST /api/agent/chat/stream (旧端点)
- **THEN** 使用 pydantic-ai Agent 正常处理
- **AND** SSE 事件格式不变

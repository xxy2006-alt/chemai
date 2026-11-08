## Spec: Agent 性能优化

### 直接回复路径
- 跳过 Think 阶段的非流式 LLM 调用
- 直接使用 chat_stream 流式输出
- 目标：首 token < 1s

### 工具调用路径
- Think 阶段立即发送 tool_call SSE 事件
- 工具执行完成后发送 tool_result 事件
- Reply 阶段流式输出
- 目标：ToolCard 出现 < 1s

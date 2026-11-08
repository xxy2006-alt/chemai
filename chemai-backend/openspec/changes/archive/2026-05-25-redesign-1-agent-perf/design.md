## Design: Agent 性能优化

### 当前问题
run_stream() 在工具调用时做两次 LLM 调用（Think + Reply），中间无用户可见反馈。直接回复也用非流式 Think。

### 优化方案
1. 直接回复：跳过非流式 Think，直接 chat_stream
2. 工具调用：Think → 立即发 tool_call 事件 → 执行 → tool_result → Reply 流式输出

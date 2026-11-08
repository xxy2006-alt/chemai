## Why

AI 对话回复慢。`core.py` 的 `run_stream()` 在工具调用时做了两次 LLM 调用（Think + Reply），中间没有任何用户可见反馈。无工具场景也走了非流式 Think 调用。

## What Changes

- `agent/core.py` — Think 阶段立即发 tool_call 事件，执行工具后发 tool_result，最后流式回复
- `agent/core.py` — 直接回复场景去掉非流式 Think，直接用 chat_stream
- `frontend/js/agent.js` — 添加 typing indicator 动画（三点跳动）
- 前端消息气泡渲染第一个 token 的时间从 ~3s 降到 ~1s

## Tasks

- [ ] 1.1 优化 run_stream() 直接回复路径（不调非流式 Think）
- [ ] 1.2 优化 run_stream() 工具调用路径（Think→立即发 tool_call→执行→tool_result→Reply）
- [ ] 1.3 前端添加 typing indicator 动画（CSS animation）
- [ ] 1.4 验证：简单问题 < 2s 出第一个字，工具调用 < 1s 出 ToolCard

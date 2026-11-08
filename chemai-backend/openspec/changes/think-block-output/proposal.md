## Why

参考业界标准（Open WebUI、ChatGPT、LangGraph 社区项目），工具执行过程和最终答案应该用 `<think>` 标记分离。当前子Agent的输出（text/卡片）直接怼到对话框，导致LLM废话泄露、重复输出、无流式效果。采用 `<think>` 块后：工具调用过程在可折叠面板里，最终答案流式输出到对话框正文。

## What Changes

- **SSE 新增标记**: `data: <think>` 和 `data: </think>`，包裹工具/子Agent执行过程
- **事件重组**: `tool_call`/`tool_result`/`subagent_start`/`subagent_tool`/`subagent_end` 全部在 `<think>` 块内
- **文本恢复流式**: `</think>` 之后，`last_result_text` 通过 `text` 事件流式输出到对话框
- **前端**: 收到 `data: <think>` 创建折叠面板，`data: </think>` 关闭，面板内仅显示工具时间线
- **移除**: `addSubAgentCard()`、`subAgentCards` 追踪、卡片 CSS/HTML
- **保留**: `subagent_start`/`subagent_tool`/`subagent_end` 事件类型（面板内渲染用）

## Capabilities

### New Capabilities
- `think-block`: `<think>`/`</think>` SSE 标记 + 前端折叠面板

### Modified Capabilities
- `sse-adapter`: finalize() 恢复 text 流式，不 emit subagent_end（改在 think 块内）
- `sub-agent-card`: 删除，替换为 think-block 面板


## Impact

- `agent/langgraph_sse.py` — feed() emit `<think>`/`</think>`，finalize() 恢复 text 流式（~30 行）
- `frontend/js/agent.js` — 删除 addSubAgentCard、subAgentCards，新增 think 面板逻辑（~40 行）
- `frontend/index.html` — 删除 sub-agent 卡片 CSS，版本号 v=10→v=11
- `agent/langgraph_agent.py` — 不改
- `agent/channel/langgraph_channel.py` — 不改

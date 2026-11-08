## Why

当前子 Agent 的输出直接以文本形式流到对话框，导致：1）子 Agent 的 LLM 废话（"好的我来检查"）直接暴露给用户；2）无格式的结果和 Markdown 结果重复出现；3）无计时器。参考 Claude Code 的面板模式——子 Agent 活动显示在可折叠卡片中，过程可见、结果折叠。

## What Changes

- **新增 SSE 事件**: `subagent_start`（含 agent_name、started_at）和 `subagent_end`（含 agent_name、elapsed、tool_count、result 文本），替代当前的 `phase: processing` + `last_result_text` 直出
- **前端新增 `addSubAgentCard()`**: 渲染可折叠卡片（标题栏 + 活动时间线 + 默认折叠的结果区），替代当前裸 text 渲染
- **移除**: SSE adapter 中 `processing`/`processing_done` phase 逻辑、`last_result_text` 文本 emit
- **移除**: `langgraph_agent.py` 中 `last_result_text` state 字段
- 子 Agent 保持 ReAct 不变（不改 prompt、不改工具调用逻辑）

## Capabilities

### New Capabilities
- `sub-agent-card`: 前端可折叠子 Agent 卡片组件
- `sse-sub-agent-events`: SSE 协议新增 subagent_start / subagent_end 事件

### Modified Capabilities
- `sse-adapter`: 移除 processing phase 和 result_text 直出，改为 emit subagent_start/end


## Impact

- `agent/langgraph_sse.py` — feed() 改 emit subagent_start/end，finalize() 移除 text emit（~20 行）
- `agent/langgraph_agent.py` — 移除 `last_result_text` state 字段（~5 行）
- `agent/channel/langgraph_channel.py` — finalize 不再传 result_text（~5 行）
- `frontend/js/agent.js` — 新增 addSubAgentCard()，移除 processing 相位处理（~80 行）
- `frontend/index.html` — 版本号 v=7→v=8

## Why

首页目前是空白 SPA 占位，Agent 能力被藏在 `HermesThinking.js` 组件中，只能在教师模块内部触发。需要把 Agent 聊天提升为主界面——像纸鸢 AI 那样，打开就是对话。

## What Changes

### 后端
- `agent/core.py` — `run_stream()` 输出结构化 SSE 事件（phase/text/tool_call/tool_result/done）
- `agent/channel/fastapi_sse.py` — 保持兼容，不做改动

### 前端
- 新建 `src/components/AgentChat.js` — 主聊天组件（消息流 + ToolResultCard + SuggestionChips + AgentStatusBar）
- 新建 `src/styles/agent.css` — Agent 界面样式
- 新建 `src/modules/agent/index.js` — Agent 初始化 + SSE 连接 + 事件分发
- 修改 `index_new.html` — 首页改为 Agent 聊天布局
- 修改 `src/main.js` — `initAgentPage()` 作为默认首页
- 侧边栏保留功能入口（题库、学情、考试管理、学生管理）

## Capabilities

### New Capabilities
- `agent-ui`: Agent 聊天主界面，SSE 流式渲染，ToolResultCard，SuggestionChips，AgentStatusBar
- `sse-events`: 结构化 SSE 事件协议（7 种事件类型）

### Modified Capabilities
- `home-page`: 首页从空白占位变为 Agent 聊天界面

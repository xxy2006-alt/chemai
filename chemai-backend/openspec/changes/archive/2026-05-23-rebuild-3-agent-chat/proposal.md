## Why

首页 = AI 教研助手。教师登录后的默认页面，按原型 `ai/code.html` 精确还原。

## What Changes

- 新建 `frontend/index.html` — 侧边栏(240px Oxford Blue) + 聊天区(AI气泡+快捷提问+输入框)
- 新建 `frontend/js/agent.js` — SSE 连接 + 事件处理 + 消息管理
- 连接 `POST /api/agent/chat/stream`，支持 6 种 SSE 事件类型

## Capabilities

### New Capabilities
- `agent-chat-ui`: AI 教研助手界面，流式对话 + 工具卡片 + 状态栏

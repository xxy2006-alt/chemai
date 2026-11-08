## 1. 后端 SSE 事件扩展

- [ ] 1.1 修改 `agent/core.py` — `run_stream()` 输出结构化 SSE 事件（phase/text/tool_call/tool_result/tool_error/done）
- [ ] 1.2 修改 `agent/channel/fastapi_sse.py` — 保持兼容，不做破坏性改动
- [ ] 1.3 验证：curl 测试 SSE 流，确认事件格式正确

## 2. Agent 聊天组件

- [ ] 2.1 新建 `src/components/AgentChat.js` — 消息渲染（Markdown → HTML + rAF 动画）+ SuggestionChips + ToolResultCard + AgentStatusBar
- [ ] 2.2 新建 `src/styles/agent.css` — 聊天界面样式（消息气泡、输入区、状态栏）
- [ ] 2.3 新建 `src/modules/agent/index.js` — SSE 连接 + 事件分发 + 消息管理
- [ ] 2.4 验证：浏览器打开首页，发送消息，确认流式渲染正常

## 3. 首页改造

- [ ] 3.1 修改 `index_new.html` — 替换 `<div id="app">` 为 Agent 布局（侧边栏 + 聊天区 + 输入区）
- [ ] 3.2 修改 `src/main.js` — 添加 `initAgentPage()`，role=teacher 时默认进入 Agent 界面
- [ ] 3.3 验证：登录后直接看到 Agent 聊天界面

## 4. 集成验证

- [ ] 4.1 验证 SuggestionChips 点击发送
- [ ] 4.2 验证 ToolResultCard 展开/收起
- [ ] 4.3 验证 AgentStatusBar 阶段切换
- [ ] 4.4 验证侧边栏导航到题库/学情/考试管理

## Why

首页 AI 教研助手需要完美体验：流式对话 + typing indicator + ToolCard + 快捷提问 + 最近活动。替换当前的简陋实现。

## What Changes

- 重写 `frontend/index.html` — 侧边栏 + 聊天区 + 快捷提问 + 最近活动
- 重写 `frontend/js/agent.js` — 完整 SSE 事件处理 + 动画 + 错误恢复
- 侧边栏移除 topbar（与 sidebar 重复）

## Tasks

- [ ] 2.1 设计侧边栏（Oxford Blue, 5个导航项, 用户区, 退出）
- [ ] 2.2 设计聊天区（AI 气泡 glassmorphism, 用户气泡 Oxford Blue, 角标样式）
- [ ] 2.3 实现 typing indicator（三点跳动动画）
- [ ] 2.4 实现 ToolCard（可折叠，左侧色带，JetBrains Mono）
- [ ] 2.5 实现快捷提问栏（6个 pill 按钮）
- [ ] 2.6 实现最近活动卡片（读取 sessionStorage 最近操作）
- [ ] 2.7 实现 AgentStatusBar（底部浮动条：阶段+工具名+耗时）
- [ ] 2.8 验证：发送消息 → typing → ToolCard → 流式回复 → 完成

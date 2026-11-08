## Context

后端 ChemAgent 已就绪，前端 `hermes.js` 已对接。需要将 Agent 聊天提升为主界面，替代当前空白首页。参考纸鸢 AI 的 SSE 事件驱动 UI 模式。

## Goals / Non-Goals

**Goals:**
- 首页 = Agent 聊天 + SuggestionChips + ToolResultCard + AgentStatusBar
- SSE 事件流结构化（7 种事件类型）
- 侧边栏保留功能入口
- 对话历史存储在 sessionStorage

**Non-Goals:**
- 不做多会话管理（单会话）
- 不做 IndexedDB 持久化
- 不引入 React/Vue 框架
- 不做暗色模式
- 不做移动端适配

## Decisions

1. **vanilla JS + rAF 动画** — 不引入框架，保持与现有前端一致
2. **SSE 事件类型参考纸鸢 AI** — phase/text/tool_call/tool_result/tool_error/done
3. **侧边栏保留** — 题库/学情/考试管理等功能模块通过侧边栏导航

## Risks

- [HermesThinking.js 现有依赖] → 保留组件作为模块内嵌，不做破坏性删除

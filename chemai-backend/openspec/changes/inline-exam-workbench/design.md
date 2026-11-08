## Context

当前 Agent→考试工作台流程使用跨页面导航：Agent 返回 `_route` → SSE navigate/populate/action → sessionStorage → exam-v2.html bridge → aiGenerate()。该流程在生产环境中不可靠——任何环节断开用户就面对空白页面。方案将考试工作台改为聊天内嵌组件，零页面跳转。

## Goals / Non-Goals

**Goals:**
- 考试工作台作为内联 HTML 面板在聊天界面中渲染
- Agent 通过 `show_exam_workbench` 工具输出 `_component` 指令触发渲染
- 用户在面板中完成出题/预览/编辑/保存——不离开聊天页
- 参数收集加严：knowledge_points + question_types 两项必填

**Non-Goals:**
- 不修改 exam-v2.html 页面（保留为独立入口）
- 不修改 LangGraph 图结构
- 不修改 `POST /api/question/generate` API

## Decisions

### D1: Component as SSE event, not page navigation

**选择**: `show_exam_workbench` 返回 `_component` 指令，SSE adapter 发射 `component` 事件，前端渲染。

**理由**: 跨页面状态传递不可靠。同页面内联渲染消除了五步链中的所有故障点。

### D2: Inline HTML panel, not iframe

**选择**: 面板作为 HTML 字符串注入聊天 DOM。

**理由**: 同源 fetch 避免跨域问题，CSS 自然继承，比 iframe+postMessage 简单。

### D3: Panel is standalone for generation

**选择**: 面板直接调用 `POST /api/question/generate` 和 `POST /api/exam-bank/import-questions`，不走 Agent 工具。

**理由**: 题目生成和保存是确定性操作，不需要 LLM 参与。Agent 只负责参数配置。

### D4: _component stripped like _route

**选择**: `_guarded` 包装器剥离 `_component` 并存入 `GuardState.last_component`。SSE adapter 从 GuardState 读取并发射事件。

**理由**: 与 `_route` 处理模式一致，保持架构一致性。

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| 内联面板 HTML 过大影响聊天性能 | 面板按需渲染（`display:none` 直到 component 事件触发） |
| 面板样式与 chat 主题冲突 | 面板使用独立 CSS 命名空间（`.inline-exam-*`） |
| 面板 DOM 在聊天滚动中被销毁 | 面板挂载在 Agent 消息气泡内，随消息持久化 |

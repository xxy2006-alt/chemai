## Why

当前"Agent 收集参数 → 跳转考试工作台 → bridge 预填 → 自动生成"的跨页面流程不可靠。SSE 事件→sessionStorage→bridge→aiGenerate() 五步链任何一个环节断开，用户就面对空白页面。没有成功的 AI 产品使用这种模式。正确的做法是考试工作台作为内联组件直接渲染在聊天界面中——零页面跳转，参数直接传递，用户在同一个界面完成所有操作。

## What Changes

- **废弃页面跳转出题**：`navigate_to_exam_workbench`（返回 `_route`）替换为 `show_exam_workbench`（返回 `_component`），不再导航到 exam-v2.html
- **新增 SSE `component` 事件**：`LangGraphSSEAdapter.finalize()` 发送 `{"type": "component", "component": "exam-workbench", "params": {...}}`
- **GuardState 扩展**：新增 `last_component` 字段，`_guarded` 包装器剥离 `_component` 并存储
- **前端内联面板**：`agent.js` 处理 `component` SSH 事件，构建内联 HTML 考试工作台面板（参数摘要 + 生成按钮 + 题目展示 + 保存/编辑/删除）
- **参数检查加严**：`TOOL_PREREQUISITES` 增加 `question_types`，两项必填才允许渲染面板
- **零 LangGraph 架构改动**：StateGraph、ToolNode、MemorySaver、端点全部不变

## Capabilities

### New Capabilities
- `inline-exam-component`: `show_exam_workbench` 工具返回 `_component` 指令，聊天 UI 渲染内联考试工作台面板，预填参数，用户在同页面完成出题/预览/编辑/保存
- `component-sse-event`: SSE 流式协议新增 `component` 事件类型，`LangGraphSSEAdapter` 从 `GuardState.last_component` 发射

### Modified Capabilities
<!-- No existing specs to modify -->

## Impact

- `agent/tools.py` — `navigate_to_exam_workbench` → `show_exam_workbench`（~40 行改）
- `agent/langgraph_agent.py` — GuardState 加 `last_component`；`_guarded` 剥离 `_component`；TOOL_PREREQUISITES 加 `question_types`（~10 行改）
- `agent/langgraph_sse.py` — `finalize()` 发射 `component` 事件（~10 行加）
- `frontend/js/agent.js` — 处理 `component` SSE 事件 + `buildExamWorkbenchHTML()` + 面板交互（~80 行加）
- `frontend/css/agent.css` — 面板样式（~30 行加）
- `exam-v2.html` — 不变
- LangGraph graph — 不变

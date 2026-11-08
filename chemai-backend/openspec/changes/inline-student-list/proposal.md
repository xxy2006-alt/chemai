## Why

当前"找问题大的学生"→ Agent 反问学号 → 用户说"有哪些学生" → 页面跳转到 students.html。出题已经不走页面跳转了（内联考试工作台），找学生也不该跳转。跨页面状态传递不可靠，正确做法是学生列表作为内联组件直接在聊天中渲染——零页面跳转，学生在聊天中浏览、筛选、选中。

## What Changes

- **新增 `show_students` 工具**：查询班级学生列表和障碍数据，返回 `_component: {component: "student-list", params: {students, class_name}}`
- **注册到 diagnosis_expert**：搜索/诊断/学生列表三个能力在一个专家内
- **修复 `diagnose_barrier`**：班级级诊断不再导航到 `/pages/diagnosis.html`，改为返回 `_component`（复用已有 diagnosis 内联面板）
- **修复 `weekly_report`**：班级级周报不再导航到 `/pages/students.html`，取消 `_route`
- **新增 `renderStudentList`**：前端在聊天气泡中渲染学生卡片列表（姓名、学号、障碍标签、进度）
- **去掉导航跳转**：`_route: {navigate: True, page: "students"}` 和 `_route: {navigate: True, page: "diagnosis"}`

## Capabilities

### New Capabilities
- `student-list-component`: `show_students` 工具返回 `_component` 指令，聊天 UI 渲染内联学生列表面板（卡片 + 障碍标签 + 选中交互）

### Modified Capabilities
- `diagnosis` 组件：`diagnose_barrier` 班级级也走内联组件，不再导航

## Impact

- `agent/tools.py` — 新增 `show_students`（~50行）、修 `diagnose_barrier._route`（~5行）、修 `weekly_report._route`（~5行）
- `agent/langgraph_agent.py` — diagnosis_expert 工具列表加 `show_students`（1行）
- `frontend/js/agent.js` — 新增 `renderStudentList()` + component switch 分支（~80行）
- LangGraph graph — 不变
- SSE adapter — 不变（已有 `component` 事件支持）
- GuardState — 不变（已有 `last_component` 剥离逻辑）

## Why

6 个页面的功能各自独立，Agent 聊天跟考试工作台、障碍诊断、学生管理、OCR 识别没有任何交互。ToolCard 只展示原始 JSON（`JSON.stringify(result)`），看不到图表、卡片、表格。后端已有 14+ 个 skill 但没有一个能在前端被消费为可视化组件。

## What Changes

- **后端**：SSE `tool_result` 事件增加 `tool` 字段，前端据此判断渲染方式
- **前端**：新建 `agent-renderers.js`，6 个渲染函数将 JSON 结果转化为图表/卡片/表格
- **前端**：`agent.js` 的 `updateToolCard()` 改用渲染器替代 `JSON.stringify`
- **CSS**：收拢各页面分散的组件 CSS 到 `design-system.css`
- **布局**：`index.html` 增加快捷操作区 + 上下文指示器

## Capabilities

### New Capabilities
- `agent-renderers`: Agent 工具调用结果的可视化渲染组件库
- `agent-context-bar`: Agent 对话上下文指示器（当前班级/考试/学生）

## Impact

- `agent/core.py` SSE 事件改造
- `frontend/js/agent-renderers.js` 新建
- `frontend/js/agent.js` updateToolCard 改造
- `frontend/design-system.css` CSS 收拢
- `frontend/index.html` 布局改版
- 各页面 JS：导出渲染函数到 window 命名空间

## Step 1: 后端 SSE 增加 tool 字段
- [x] 1.1 agent/core.py run_stream() tool_call/tool_result/tool_error 增加 tool 字段

## Step 2: 前端 Agent 渲染器
- [x] 2.1 新建 frontend/js/agent-renderers.js，实现 6 个渲染函数
- [x] 2.2 各页面 JS 导出渲染函数到 window（已通过 agent-renderers.js 独立实现）
- [x] 2.3 agent.js updateToolCard() 改用 ChemRender 替代 JSON.stringify

## Step 3: CSS 收拢
- [x] 3.1 各页面组件 CSS 已在 design-system.css 中（前序任务完成）

## Step 4: Agent 首页布局改版
- [x] 4.1 index.html 增加上下文指示器 + agent.js setContext/clearContext

## Step 5: 验证
- [x] 5.1 Agent 对话触发诊断 → ToolCard 渲染柱状图
- [x] 5.2 Agent 对话触发出题 → ToolCard 渲染题目卡片
- [x] 5.3 6 页面 0 JS 错误

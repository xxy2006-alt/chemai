## Context

基于全景规划（`~/.gstack/projects/chemai/blueprint-agent-ui-20260623.md`）：
- 11 个功能中 9 个通过 Agent 工具完成
- 2 个需要内联面板：出题（视觉预览/编辑需求）和诊断（图表需求）
- 唯一外部依赖：ECharts CDN

当前 `show_exam_workbench` 面板只展示参数摘要——控件是只读的。需要扩展为完整交互面板。

## Goals / Non-Goals

**Goals:**
- 出题面板：完整交互（可调参数、可生成、可预览/编辑/保存题目）
- 诊断面板：ECharts 图表 + 关键指标 + 快捷操作
- 题库管理：纯工具，无面板
- 零页面跳转，零外部 widget 库

**Non-Goals:**
- 不改 exam-v2.html
- 不改 LangGraph 图结构
- 不引入 MCP
- 不换聊天 UI 框架

## Decisions

### D1: 复用 exam-v2 数据接口，不自建后端

面板调用与 exam-v2.html 相同的 API：`/api/knowledge/list`、`/api/question/generate`、`/api/exam-bank/import-questions` 等。Agent 工具只管意图路由和参数预填，不重复实现业务逻辑。

### D2: ECharts CDN，不打包

学情诊断的唯一图表需求是障碍分布图。ECharts CDN 引入 ~40KB gzip，远小于打包方案。仅在诊断面板渲染时初始化，不影响首屏加载。

### D3: 面板状态存储在 DOM 中

面板是自包含的——参数状态在面板的 DOM 元素中（input values、checkbox states、data attributes）。关闭后再打开需要重新渲染（Agent 重新调工具）。不在 sessionStorage 中维护面板状态。

### D4: 面板操作完成后通知 Agent

用户在面板中操作完成后（点"完成"），发送一条总结消息给 Agent：`sendMessage('题目已生成：3道，已保存2道。')`。Agent 继续处理后续需求。

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| ECharts CDN 加载失败 | 面板降级为纯文本指标卡片，无图表 |
| 面板 HTML 过大影响聊天性能 | 面板 display:none 直到 component 事件触发 |
| 蓝本浏览器在面板内弹窗交互复杂 | 先用简单下拉替代，后续迭代加弹窗 |

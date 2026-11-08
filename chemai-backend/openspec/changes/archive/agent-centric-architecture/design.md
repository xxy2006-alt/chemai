## Design: Agent-Centric 架构

### 整体思路
Agent 成为产品编排层。老师通过对话触发所有功能——出题、诊断、查学生、扫答题卡。ToolCard 不再展示 JSON，而是渲染与独立页面同样的富组件。

### 后端改动
`agent/core.py` `run_stream()` 的 SSE `tool_result` 事件：
```json
{"type":"tool_result","name":"diagnose_barrier","tool":"diagnosis","success":true,"result":{...}}
```
新增 `tool` 字段取值：`exam`, `diagnosis`, `parser`, `memory`, `improvement`, `notification`。

### 前端渲染器注册
`agent-renderers.js`:
```javascript
window.ChemRenderers = {
  exam_generate: renderQuestionCards,        // 题目列表 + 审核标记
  exam_audit: renderAuditReport,             // 审核结果卡片
  diagnosis_barrier: renderBarrierOverview,  // 柱状图 + 学生列表
  diagnosis_plan: renderLearningPlan,        // 学习计划
  exam_results: renderExamStats,             // 统计 + 成绩表
  student_detail: renderStudentProfile,      // 学情 + 趋势图
  parser_ocr: renderOcrTable,               // OCR 结果表
}
```

### 渲染流程
`SEE tool_result → updateToolCard() → 查 ChemRenderers[evt.name] → innerHTML 渲染 → body.open`

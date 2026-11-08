## Why

3 个高危前端 bug：`student/practice.js` 缺 studentId 导致请求 `/undefined/tasks`；`student/learning_plan.js` 中文属性名 JS 语法错误；`services/integration.js` api.post 第三参数被静默丢弃。

## What Changes

- `modules/student/practice.js:35` — 从 session 取 studentId 传给 `getStudentTasks()`
- `modules/student/learning_plan.js:65` — 中文属性名改 bracket notation
- `services/integration.js:59,75` — `api.post(url, null, {params})` → `api.post(url, {params})`

## Capabilities

### Modified Capabilities
- `student-practice`: 修复 studentId 缺失导致练习模块不可用
- `student-learning-plan`: 修复中文属性名导致学习计划渲染失败
- `integration-service`: 修复 webhook test 和 API key create 参数丢失

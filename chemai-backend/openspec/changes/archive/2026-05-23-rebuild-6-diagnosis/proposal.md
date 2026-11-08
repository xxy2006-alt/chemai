## Why

障碍诊断页面，按原型 `_1/code.html` 还原。三种障碍类型可视化 + 学生个体诊断 + 学习计划生成。

## What Changes

- 新建 `frontend/pages/diagnosis.html`
- 新建 `frontend/js/diagnosis.js`
- API: `GET /api/diagnosis/barrier/{classId}/{examId}`, `POST /api/diagnosis/learning-plan/generate`

## Capabilities

### New Capabilities
- `diagnosis-page`: 障碍诊断页面

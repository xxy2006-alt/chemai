## Why

题目管理页面，按原型 `_2/code.html` 还原。支持真题搜索、AI出题、试卷导入。

## What Changes

- 新建 `frontend/pages/questions.html`
- 新建 `frontend/js/questions.js`
- API: `GET /api/exam-bank/historical`, `POST /api/question/generate`, `POST /api/question/import`

## Capabilities

### New Capabilities
- `questions-page`: 题目管理页面（搜索+生成+导入）

## Why

学情报告 + 学情面板，按原型 `_6/code.html` 和 `_3/code.html` 还原。

## What Changes

- 新建 `frontend/pages/report.html` + `frontend/js/report.js`
- 新建 `frontend/pages/panel.html` + `frontend/js/panel.js`
- API: `GET /api/report/teacher/{examId}`, `GET /api/panel/class/{classId}`, `GET /api/panel/class/{classId}/trend`

## Capabilities

### New Capabilities
- `report-page`: 学情报告页面
- `panel-page`: 学情面板页面

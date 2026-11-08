# Student Mobile Frontend

## Why

旧学生端（Vite SPA, 1866 行 JS）在 `824c2c6` "前端完全重做"时被删。当前学生登录后重定向到教师工作台，无可用界面。后端 API（练习/考试/诊断）和数据库（Student/StudentAnswer/StudentSubmission）已完整，缺前端。

视觉原型 `frontend/m/design-v1.html` 已获认可：Material Icons + 教师端配色(#f7f4ed/#b43c28) + iPhone 15 Pro 移动端适配 + 4 Tab 导航。

## What Changes

- **新建 `frontend/m/` 目录**：7 个学生移动端页面，原生 HTML + 内联 JS
- **新建 `frontend/m/app.js`**：共享模块（认证/API 封装/导航栏组件）
- **新增路由 `/m/{filename}`**：`app/main.py` 已加，无需再改
- **修改 `login.html`**：学生/家长角色登录后跳转 `/m/index.html`（已改）
- **不改后端 API**：复用现有练习/考试/Agent 端点

## Capabilities

| # | 页面 | API 依赖 | 优先级 |
|---|------|---------|--------|
| 1 | AI 助教对话 | `POST /api/agent/chat/langgraph/stream` | P0 |
| 2 | 我的练习 | `GET /api/practice/student/{id}/tasks` + `POST /api/practice/submit` | P1 |
| 3 | 错题本 | `GET /api/exam/{id}/result/{student_id}` | P1 |
| 4 | 学习报告 | 同上 + 本地计算 | P2 |
| 5 | 复习中心 | 本地存储 | P2 |
| 6 | 学习计划 | `GET /api/practice/student/{id}/tasks?type=plan` | P2 |
| 7 | 个人设置 | 无（纯前端） | P2 |

## Impact

- `frontend/login.html` — 改 1 行（已完成）
- `frontend/m/index.html` — 新建，~250 行
- `frontend/m/app.js` — 新建，~100 行
- `frontend/m/practice.html` — 新建，~300 行
- `frontend/m/wrong.html` — 新建，~200 行
- `frontend/m/report.html` — 新建，~150 行
- `frontend/m/review.html` — 新建，~150 行
- `frontend/m/plan.html` — 新建，~150 行
- `frontend/m/profile.html` — 新建，~100 行
- 后端 — 不改
- 数据库 — 不改

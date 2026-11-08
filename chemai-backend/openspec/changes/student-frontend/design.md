# Design — Student Mobile Frontend

## Context

教师端是桌面 Web App（原生 HTML + 内联 JS），学生端被删后需重建。学生用手机访问，需要独立移动端页面。旧代码（`frontend/src/modules/student/`）和设计稿（`agent/spec_student.md`）作为参考。

## Goals

- 7 个学生移动端页面，原生 HTML + 内联 JS，与教师端技术栈统一
- 复用现有后端 API（零后端改动）
- 视觉风格：Material Icons + 教师端配色(#f7f4ed/#b43c28/#1a1a1a) + iPhone 15 Pro 适配
- 学生登录后自动跳转学生主页

## Non-Goals

- 不改后端 API 或数据库 schema
- 不恢复旧 Vite 构建系统
- 不做家长端（仅学生角色跳转 `/m/`）
- 不做 PWA/离线

## Decisions

### D1: 原生 HTML + 内联 JS，不用 React

设计原型用 React 是快速视觉验证，功能页面用原生 JS 避免额外依赖。

**理由**: 教师端已用这个架构，统一且零构建。学生页面逻辑简单（表单+列表+SSE），不需要 React。

### D2: 独立移动端页面，不响应式混合

教师端 `index.html` 是桌面布局（侧边栏+大表），不适合加 `@media` 适配手机。

**理由**: 学生和教师的交互模式完全不同（对话 vs 管理），强行响应式会两边都做不好。

### D3: 共享 `app.js` 而非每页独立

认证/API 封装/导航栏在每个页面都需要。

**理由**: 共享模块避免 7 个页面重复写登录检查和 tab 栏。

### D4: 设计稿 `design-v1.html` 保留作为参考

功能页面实现时参考原型的设计 token、间距、组件样式。

**理由**: 确保实现不偏离认可的设计方向。

## Risks

| Risk | Mitigation |
|------|-----------|
| SSE 流式在移动端渲染性能 | 累积 buffer 批量更新 DOM，不逐字符 |
| 练习 API 数据量大 | 分页加载，一次 10 题 |
| 学生账号无 token 访问 `/m/` 页面 | app.js 全局检查登录态，未登录跳 `/login.html` |

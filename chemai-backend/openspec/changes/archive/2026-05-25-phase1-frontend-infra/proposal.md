## Why

前端 Vite 项目 API 配置不统一：`src/services/parent.js` 硬编码 `localhost:8001`，`src/services/notification.js` 7处裸 `fetch()` 不带 token。登录重定向路径不一致。导致登录后秒退。

## What Changes

- `src/services/parent.js:5` — `API_BASE = 'http://localhost:8001'` → `''`
- `src/services/notification.js` — 7处裸 `fetch()` → `api.get/post`
- `src/pages/login.js:28` — 去掉 `login()` 多余的第三个参数
- `src/pages/login.js:37` — 登录重定向修复（role-based）

## Capabilities

### Modified Capabilities
- `frontend-api`: API_BASE 统一走 Vite proxy，token 自动注入

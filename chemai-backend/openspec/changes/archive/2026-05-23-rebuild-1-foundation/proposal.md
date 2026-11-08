## Why

前端全部重做，需要统一的设计系统和全局 JS 基础设施。所有页面共享同一套颜色、字体、间距、组件样式。全局 JS 负责登录状态检查、顶部导航栏渲染、fetch token 注入。

## What Changes

- 新建 `frontend/design-system.css` — 完整的设计系统 CSS（颜色 token、字体栈、组件样式、动画）
- 新建 `frontend/app.js` — 全局 JS（auth check、navbar render、fetch 拦截、页面路由）
- 更新 `frontend/vite.config.js` — 简化为新页面入口

## Capabilities

### New Capabilities
- `design-system`: Academic Catalyst 设计系统（Oxford Blue + 羊皮纸暖色调 + 三字体 + Material Symbols）
- `global-app`: 全局认证 + 导航 + API token 注入

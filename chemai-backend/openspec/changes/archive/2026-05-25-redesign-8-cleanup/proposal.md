## Why

清理不再使用的文件和代码残留。

## What Changes

- 删除 `frontend/pages/report.html` + `frontend/pages/panel.html` + `frontend/pages/questions.html`
- 删除 `frontend/js/report.js` + `frontend/js/panel.js` + `frontend/js/questions.js`
- 删除 `frontend/.vite/` (构建缓存)
- 更新 `frontend/vite.config.js` 构建 inputs
- 更新 `agent/REDESIGN.md` 为最终设计文档
- 提交 git

## Tasks

- [ ] 8.1 删除旧页面文件
- [ ] 8.2 删除旧 JS 文件
- [ ] 8.3 更新 vite.config.js 构建入口
- [ ] 8.4 Git commit

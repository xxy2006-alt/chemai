# P2-4 前端版本清理确认

## 修复日期
2026-04-25

## 问题描述
- `main.py` 中存在指向不存在文件的死路由（`teacher.html`、`student.html`）
- `dist/` 目录中存有过时的 Vite 构建产物，容易混淆
- 前端只有 `teacher_v2.html`/`student_v2.html` 是现行版本

## 修改内容

### 1. `app/main.py`
- 移除 `teacher.html` 路由（文件不存在）
- 移除 `student.html` 路由（文件不存在）
- 移除 `parent_portal.html` 独立路由（由兜底路由 `/{page}` 自动处理）
- `index.html` 路由改为：不存在时 fallback 到 `login.html`

### 2. `frontend/dist/` — 已删除
过时的 Vite 构建产物（包含旧版 login.html, teacher_v2.html, student_v2.html），`.gitignore` 已有 `dist/` 规则。

## 当前前端文件清单

| 文件 | 状态 | 说明 |
|------|------|------|
| `frontend/login.html` | 活跃 | 登录页 |
| `frontend/teacher_v2.html` | 活跃 | 教师端 SPA |
| `frontend/student_v2.html` | 活跃 | 学生端 SPA |
| `frontend/parent_portal.html` | 活跃 | 家长端（由兜底路由服务） |
| `frontend/index_new.html` | 保留 | Vite 构建入口，不直接服务 |
| `frontend/src/` | 活跃 | 源码目录 |
| `frontend/dist/` | 已删除 | 过时构建产物 |
| `teacher.html` | 不存在 | 路由已移除 |
| `student.html` | 不存在 | 路由已移除 |

## 验证方式
1. 访问 `http://localhost:8001/teacher_v2.html` → 正常显示教师端
2. 访问 `http://localhost:8001/student_v2.html` → 正常显示学生端
3. 访问 `http://localhost:8001/parent_portal.html` → 由兜底路由正常服务
4. 不再有 `teacher.html`/`student.html` 路由返回 404

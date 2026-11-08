# P0-3 前端角色常量修复确认

## 修复日期
2026-04-25

## 问题描述
前端 `auth.js` 的 `UserRole` 只定义了 `ADMIN`、`TEACHER`、`STUDENT` 三种角色，而数据库实际存在 5 种角色（`admin`、`教务管理员`、`学科组长`、`teacher`、`student`）。`isTeacher()` 方法严格检查 `user.role === 'teacher'`，导致 `学科组长` 和 `教务管理员` 登录后无法看到教师端功能。

## 修改内容

### 1. `frontend/src/services/auth.js`
- `UserRole` 新增 `ACADEMIC_LEADER: '学科组长'` 和 `EDUCATION_ADMIN: '教务管理员'`
- `isTeacher()` 改为 `['teacher', '学科组长', '教务管理员'].includes(user.role)`
- 新增 `isAcademicLeader()` 方法
- 新增 `isEducationAdmin()` 方法

### 2. `frontend/src/pages/home.js`
- `getRoleName()` 补充 `学科组长` 和 `教务管理员` 的显示名称
- `loadQuickStats()` 中教师统计条件补充 `学科组长` 和 `教务管理员`
- `renderQuickActions()` 中快捷操作条件补充 `学科组长` 和 `教务管理员`

## 未修改但已验证的文件
- `main.js:89` — 三元表达式 `user.role === 'student' ? student : teacher`，非 student 角色自动跳转教师端，无需修改
- `services/user.js:201-202` — 已直接处理中文角色名比较，无需修改
- `modules/teacher/ocr.js:1251-1255` — 已直接处理中文角色名比较，无需修改

## 验证方式
1. 使用 `hai / hai123456`（学科组长）登录 → 跳转教师端，左侧菜单完整显示
2. 使用 `admin / admin123`（管理员）登录 → 跳转管理端，功能完整
3. 使用 `202610101 / 123456`（学生）登录 → 跳转学生端
4. `authService.isTeacher()` 对 `teacher`、`学科组长`、`教务管理员` 三种角色均返回 `true`

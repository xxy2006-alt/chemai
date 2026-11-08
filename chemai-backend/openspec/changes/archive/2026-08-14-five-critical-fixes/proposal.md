## Why

五个影响三端核心体验的 bug：家长完全无法登录、Agent 找不到学生、学习计划发送后学生看不到、学生端设置是空壳、所有学生演示数据千篇一律。这些 bug 阻断家长端可用性、破坏教师-学生闭环、让演示效果大打折扣。

## What Changes

- **修复** 家长登录不返回 JWT token + 路由不在白名单 → 家长端可用
- **修复** `show_students` 缺 `student_name` 参数 → Agent 可按姓名找学生
- **修复** GET /learning-plan 不读 SqliteStore → 教师发送的计划学生能看到
- **新增** 学生数据随机化脚本 → 66 人各有不同的障碍分布和练习记录
- **实现** 学生端个人设置（改密码/绑定码/信息/关于）→ 替代 alert 占位符

## Capabilities

### New Capabilities
- `student-settings`: 学生端个人设置面板 — 修改密码、查看绑定码、个人信息、关于页面
- `data-randomizer`: 演示数据随机化 — 差异化障碍分布 + 练习记录 + 答题历史

### Modified Capabilities
- `parent-auth`: 家长登录流程 — 补充 JWT 生成 + 路由白名单
- `agent-student-search`: Agent 学生搜索 — show_students 扩充 student_name 参数
- `learning-plan-delivery`: 学习计划交付 — GET 端点接入 SqliteStore 读取

## Impact

| 层 | 文件 | 变更 |
|-----|------|------|
| 后端 API | `app/api/parent.py` | login 加 JWT 生成 |
| 后端路由 | `app/main.py` | 白名单加 /api/parent/ |
| Agent 工具 | `agent/tools/diagnosis.py` | show_students 加参数 |
| 后端 API | `app/api/diagnosis.py` | GET /learning-plan 接入 SqliteStore |
| 前端 | `frontend/m/report.html` | 设置面板替换 alert |
| 脚本 | `tools/randomize_students.py` | 新建数据随机化脚本 |

## Context

五个 bug 分散在认证、Agent、API、前端、数据五个层面，相互独立无依赖关系。

## Goals / Non-Goals

**Goals:** 修 5 个 bug，恢复家长/教师/学生三端核心闭环
**Non-Goals:** 不新增功能模块，不改变现有架构

## Decisions

### D1: 家长登录 — 复用现有 JWT 体系

`app/middleware/auth.py` 已有 `create_access_token()` 函数（HMAC-SHA256）。家长登录后直接调它生成 token，跟教师/学生完全一致。

**理由:** 不另外造认证体系。白名单加一行，login 加 5 行。

### D2: show_students — 加参数而非改名

不改工具名，只加 `student_name` 参数。两个参数互斥：传了 `student_name` 就走姓名搜索，传了 `class_id`/`class_name` 就走班级搜索。

**理由:** 保持向后兼容。Agent 和前端已有调用不变。

### D3: 学习计划 — GET 端三级查找

`_plan_cache`（快）→ SqliteStore（持久）→ LLM 生成（兜底）。POST /apply 改同步写入。

**理由:** SqliteStore 写入是轻量操作，同步写不会明显增加延迟（~10ms vs 之前的异步 task），但消除了竞态。

### D4: 学生设置 — 复用同页面组件

不新建页面。在 `m/report.html` 的"我的"Tab 里，把 alert 替换为内联设置面板，复用该页面已有的 CSS 和组件风格。

### D5: 数据随机化 — 独立脚本

不融入 init_db（避免影响正式初始化逻辑）。独立脚本 `tools/randomize_students.py`，手动运行一次即可。

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| POST /apply 同步写入可能增加延迟 | SqliteStore aput 是内存操作，<10ms |
| 数据随机化可能覆盖真实数据 | 加 `--force` 参数确认，默认跳过已有练习记录的学生 |
| show_students 加参数后 Agent 行为变化 | 评测覆盖 show_students 场景 |

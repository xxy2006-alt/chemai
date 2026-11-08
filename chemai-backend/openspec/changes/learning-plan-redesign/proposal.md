## Why

学习计划是教师→学生教学闭环的关键环节。当前实现有三个断裂点：(1) Agent Chat 中教师无法对指定学生生成、查看、修改、发送学习计划——缺少 Agent 工具；(2) 学生管理界面点击"生成学习计划"后 30 秒静默等待 + 硬编码障碍数据 + 只弹 alert 不展示内容；(3) 计划无法持久化——`POST /apply` 是空壳 TODO，服务器重启后丢失。

## What Changes

- **新增** `generate_learning_plan` Agent 工具 — 教师可在 Agent Chat 中对指定学生生成学习计划，计划文档在聊天中直接展示
- **新增** `send_learning_plan` Agent 工具 — 教师确认计划后一键发送给学生，持久化到 SqliteStore
- **修复** `POST /api/diagnosis/learning-plan/apply` 端点 — 补实现持久化逻辑（写入 SqliteStore 长期记忆）
- **重写** `frontend/js/students.js` genPlan 函数 — 用学生真实障碍数据替代硬编码、添加 spinner 进度反馈、渲染可编辑计划卡片、支持手动修改保存
- **注册** 两个新工具到 TOOLS + TOOL_META

## Capabilities

### New Capabilities

- `agent-learning-plan`: Agent Chat 中支持学习计划全流程——生成、展示、修改、发送
- `student-plan-editor`: 学生管理界面中支持可编辑学习计划卡片——生成进度反馈、字段级编辑、保存、发送

### Modified Capabilities

<!-- 无现有 capability 需要修改 -->

## Impact

| 层 | 影响 |
|-----|------|
| Agent 工具 | `agent/tools/diagnosis.py` 新增 2 个工具函数 |
| Agent 注册 | `agent/tools/__init__.py` TOOLS + TOOL_META 各新增 2 条 |
| 后端 API | `app/api/diagnosis.py` POST /apply 补实现 |
| 前端 | `frontend/js/students.js` genPlan 重写 (~80行→~150行) |
| 数据库 | 无新增表 — 使用已有 SqliteStore |

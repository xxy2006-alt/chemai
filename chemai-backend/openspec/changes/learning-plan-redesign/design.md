## Context

学习计划功能的后端 API (`POST /generate`, `GET /{student_id}`, `POST /apply`, `POST /send-to-parent`) 已存在于 `app/api/diagnosis.py`，LLM 生成引擎 (`llm_service.generate_learning_plan`) 已可用。但存在三个断裂点：

1. **Agent 层缺失** — 没有 `generate_learning_plan` 和 `send_learning_plan` 工具，Agent Chat 中教师无法触发生成和发送流程
2. **前端 UI 缺陷** — `students.js` 的 genPlan 使用硬编码 `barrier_type: 'concept'` 和空知识点，30 秒静默等待后只弹 alert
3. **持久化缺失** — `POST /apply` 端点只有 TODO 注释，计划仅存于内存缓存 (`_plan_cache`) 和浏览器 localStorage

## Goals / Non-Goals

**Goals:**
- Agent Chat 中支持完整的学习计划工作流：查找学生 → 生成计划 → 查看 → 修改 → 发送
- 学生管理界面支持：一键生成（用真实数据）→ spinner 反馈 → 可编辑卡片 → 手动修改保存 → 发送
- 计划持久化到 SqliteStore，服务器重启不丢失

**Non-Goals:**
- 不新建数据库表 — 复用 SqliteStore (`chemai_store.db`)
- 不修改 LLM 生成引擎 (`llm_service.generate_learning_plan`)
- 不改学生端展示模块（`learning_plan.js` 已写好, 只需后端正向写入）
- 不涉及家长端改动

## Decisions

### D1: Agent 工具设计 — 内联调用后端 API

Agent 工具 `generate_learning_plan` 直接调 `POST /api/diagnosis/learning-plan/generate` 而非绕过 API 直接调 `llm_service`。

**理由:** API 已包含学生验证、缓存逻辑 (`_plan_cache`)、错误处理。Agent 工具复用 API 保持单一路径。

**Alternatives considered:**
- 直接调 llm_service: 绕过验证和缓存, 代码重复
- 让 Agent 告诉前端去调 API: 增加往返, 用户体验差

### D2: 持久化方案 — SqliteStore

`POST /apply` 写入 `SqliteStore` 的 namespace `("student", student_id, "learning_plan")`，key 为 `"current"`。这与已有的 `memory_student_get` 读取端完全对称。

**理由:** SqliteStore 已在 Agent 层使用 (`chemai_store.db`)，无需新建表、迁移或额外依赖。

**Alternatives considered:**
- 新建 `learning_plans` 表: 需要 Alembic 迁移, 增加复杂度
- Redis/外部缓存: 过度工程, 当前规模不需要

### D3: 前端编辑模式 — contenteditable + 双向绑定

Drawer 内的计划卡片每个字段使用 `contenteditable="true"`，点击进入编辑，失焦保存到本地 plan 对象。点击「保存修改」更新 localStorage，点击「发给学生」调 API。

**理由:** 不引入富文本编辑器依赖。计划字段是纯文本（标题、任务描述），contenteditable 够用。

**Alternatives considered:**
- 弹窗编辑器: 打断 Drawer 上下文, 体验差
- 表单控件: 字段多且层级嵌套（每日任务列表），表单实现复杂

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| SqliteStore 非关系型存储，计划无法 SQL 查询 | 当前场景只需 key-value 存取，不需要跨学生查询计划 |
| contenteditable 可能产生格式垃圾 | 存前 `innerText` 清洗，不保留 HTML |
| Agent 生成的计划 JSON 可能格式不稳定 | 与已有 generate API 共享 JSON 解析逻辑，已处理 markdown 包裹 |
| genPlan 重写后 students.js 体积增加 | 新增 ~70 行，总文件 ~500 行，可接受 |

## Migration Plan

1. 先补后端 `POST /apply` 持久化（零前端依赖）
2. 再建 Agent 工具并注册（不影响现有功能）
3. 最后改前端 genPlan（用户可见变化）
4. 回滚：每步独立 git commit，可单独 revert

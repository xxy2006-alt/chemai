## Context

权限机制的设计文档（2026-04-22）与代码实现脱节。经过一轮完整审计（3 个探查 + 数据库直查 + 日志核对），确认：

- 权限矩阵存在但无人消费；设计好的三个工具函数零端点调用
- 234 个端点中 8.5% 有授权，32% 连 token 都不需要
- 前端完全不做角色区分，是用户"感觉权限都差不多"的直接原因
- 历史上三次角色相关修复（P0-3 / P2-2 / P1-3）有两次打在 `teacher_v2.html` / `services/auth.js` 上，React 重写后**文件消失、修复蒸发**，只剩文档

领域词汇落在 `CONTEXT.md` 的 Access Control Concepts（新增），架构决策落在 ADR-0008 ~ 0011。

## Goals / Non-Goals

**Goals:**
- 让"多层权限"从文档变成请求链路上真实执行的规则
- 默认拒绝，使"忘了声明权限"从静默漏洞变成红灯
- 策略唯一真源在后端，前端重写不丢
- 消除已知敞口：班级接口裸奔、任意 token 读任意数据、密码重置无鉴权

**Non-Goals:**
- 不改 Agent 的 Persona 机制（工具过滤是另一条轴，仅文档层面划清）
- 不做租户自定义角色 / 角色模板 / 角色继承
- 不做 SSO / SCIM / 组到角色映射
- 不建外部开放 API（`/api/integration/` 签发的 `ck_` key 目前无处校验，是独立的另一条活儿）
- 不顺手修相邻安全问题（密码 SHA256、无登录锁定、refresh token 明文返回、token 24h）——见提案外清单

## Decisions

### D1: 角色分两类（ADR-0008）

员工角色 4 → 5 个，加平台级 `super_admin`；本人角色 2 个不进矩阵。理由是矩阵装不下"身份即范围"这类规则——证据是矩阵里只有 `student` 有 `assignment` 键，其余角色没有，导致作业鉴权恒为 False。

### D2: 默认拒绝 + router 级声明（ADR-0009）

`app/api/` 下一个文件基本就是一个资源，router 即模块。21 条声明代替 234 条端点级声明，粒度对齐代码结构。混合权限的文件在 router 声明基线、端点在特权动作覆盖。

### D3: 数据范围从关系表推导（ADR-0010）

`teacher_class_subject` 已经在表达"谁教哪个班的哪科"、"谁是班主任"（`is_class_teacher`）——模型建好了，只是没人用。范围模块复活现有死代码 `get_teacher_classes` 的形状。**`classes.teacher_id` 不参与**（两行全 NULL，无写入路径，前端零引用）。

### D4: 前端只消费能力清单

登录响应返回 `role` + `role_label` + `permissions` + `menus`。前端建一层「菜单 key → 组件」映射，不做 `if role === 'admin'` 判断。这直接针对"修复蒸发"——策略活在后端，前端重写带走不了。

### D5: 超管跨校走 break-glass（ADR-0011）

默认数据范围为空。依据来自 SuperTokens 多租户指南：*"Never grant standing cross-tenant access."*

### D6: 三步走，每步可独立验证与回滚

① 前端调用方带 token（行为不变）→ ② 白名单收缩（认证生效）→ ③ 默认拒绝 + 逐个 router 接 scope（授权生效）。

顺序不能反：白名单里的端点压根没有 token，范围判断无从谈起。

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| ② 之后学生端对话 401 —— `frontend/m/index.html:246` 的流式调用是裸 fetch，不带 Authorization | ① 必须先把这一处补上；② 上线前用学生账号走一遍完整对话 |
| ② 与 ③ 之间的中间态：任意有效 token 仍能读任意数据 | 不粉饰。③ 按危害排序，`user.py` / `parent.py` 排最前，缩短窗口 |
| ③ 一次性翻默认拒绝会产生大量 403 | 一个 router 一次做完，不做半途；完整性守卫测试跟着每个 router 走 |
| scope 缓存 key 漏掉 `school_id` → 跨校权限泄漏 | 缓存 key 必须含 `school_id`（调研明确点名的失败模式） |
| 部署环境存在未知外部调用方 | 仓库内已查清无外部调用；部署环境无法证实——② 之前先开访问日志跑几天 |
| 权限判定出错时放行 | fail-closed：判定失败/查不到，一律拒绝 |
| 迁移 `学科组长` → `subject_lead` 漏改字面量，P1-3 的 bug 复发 | 0.3 单列一条任务，验证项就是"海老师登录后 name/teacher_id/school_id 三字段齐全" |

## Open Questions

- `/api/integration/` 外部开放 API 是否要建（当前签发的 `ck_` key 无任何地方校验）
- `classes.teacher_id` 的清理时机（可随本次，也可独立）
- 部署环境访问日志的开启时间点

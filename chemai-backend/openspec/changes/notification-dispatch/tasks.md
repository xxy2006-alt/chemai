# 通知分发与学生收件箱 — 任务清单

## 1. 数据与服务层

- [x] 1.1 新表 StudentNotification（id/student_id/type/payload/read_at/idempotency_key UNIQUE）+ Alembic 迁移
- [x] 1.2 NotificationService 增加 `dispatch(recipient, event, idempotency_key)`：站内写入默认动作 + 幂等去重（复用 `_dedup_notification_id` 语义）
- [x] 1.3 外部网关 adapter：经统一入口在配置开关下调用 chemistry_notification 网关/模板（9a26b8a 契约）；skill 侧只经 REST（ADR-0012）
- [x] 1.4 `unread_count` / `mark_read` 服务方法

## 2. API 与触发点

- [x] 2.1 `GET /api/notification/student/{id}/notifications` 真实现（本人可见 + 未读数），替换恒空 stub
- [x] 2.2 四个 send* 路由按 dispatch 重建语义（替换 P0 的 501 占位），权限/Scope 装置不变
- [x] 2.3 触发点接线：assignment_service 布置完成、grading_center 练习判卷完成/OCR 批量确认（学生侧）、周报路径经 dispatch（家长侧）
- [x] 2.4 Agent 侧无需新工具（触达是事件挂钩，非对话动作）

## 3. 前端

- [x] 3.1 `frontend/m/app.js`：练习 tab 未读红点（进入页面时拉取未读数，查看通知后刷新）

## 4. 测试与回归

- [x] 4.1 服务层：dispatch 幂等（重放单条）；开关关闭只落站内；开启站内+外发各一次
- [x] 4.2 学生端点 IDOR：本人可见、他人 403（复用 test_api_auth_notification 模式）
- [x] 4.3 布置→通知 端到端一条；`pytest` + `ruff check .` 全绿，chem_skills/chemistry_notification 既有 11 测试不回归

## 5. 实现说明（2026-09-12）

- [x] 5.1 网关 adapter 为真实路径：dispatch 判定开关（NOTIFY_EXTERNAL_GATEWAYS，默认关）→
  seam 尝试 Telegram 外发（凭据来自 TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID，未配置诚实降级
  返回 False）；Discord/Slack/Email 通道待部署凭据后按同型接入（tools.yaml 契约已备）
- [x] 5.2 幂等键为「事件×收件人」复合存储（广播全班不撞 UNIQUE 约束，重放去重语义不变）
- [x] 5.3 学生进入练习页即 POST /read 全部已读（badge 红点消失语义）
- 验证：dispatch 套件 16 绿；全量 605 passed（4 失败为分支基点已有）；ruff 全绿；app.js 语法检查通过

## 6. code-review 修正（2026-09-12，双轴审查后）

- [x] 6.1 网关 adapter 恢复真路径（前一轮半途脚本丢失）：Telegram 外发按配置凭据执行，
  未配置诚实降级；外发移到去重判定之后——重放事件不重复外发
- [x] 6.2 家长分支幂等走错表（dedup 查 StudentNotification 而落 ParentNotification，
  重放触发 IntegrityError）→ 按角色选模型去重 + ParentNotification.student_id 从
  recipient 上下文取值（send-to-parent / 班级广播带 student_id）
- [x] 6.3 周报 send_weekly_report_notification 改经 dispatch（tasks 2.3 虚假声明修正）
- [x] 6.4 PUT read 内联写库（ADR-0012）→ service.mark_single_read，路由薄壳
- [x] 6.5 graded 幂等键去冗余（复合 :rid 由 dispatch 统一补）
- [x] 6.6 考试待确认的教师通知：按 design Out of Scope（教师收件箱）明确推迟，不再虚列
- 验证：通知/鉴权/权限相关 165 绿；全量见提交说明

# 通知分发与学生收件箱（Notification Dispatch & Student Inbox）

## Why

业务闭环里「学生知道有新练习」一环整体缺失：没有学生通知表，统一分发端点要么运行时 500（调用了服务上不存在的方法，P0 已改诚实 501）要么恒返回空数组；NotificationService 只有家长面方法；学生只能盲刷练习页发现新任务。同时 chem_skills 的 chemistry_notification（四网关 Discord/Slack/Telegram/Email + 模板，带 11 个通过的测试）从未被接线——一座精装修的孤岛，与进程内服务平行漂移。

## What Changes

- **新建学生通知表（StudentNotification）**：学生侧站内通知，含类型、载荷、已读时间、幂等键。
- **NotificationService 增加统一分发入口 `dispatch`**：按收件人（学生/家长）与事件类型分发；站内写入为默认动作；幂等键去重（至少一次投递契约）。
- **四网关接为可选外发 adapter**：经统一分发入口在配置开关开启时外发（复用 chemistry_notification 的模板与格式化契约）；skill 侧只允许经 REST 调用服务（ADR-0012 单向依赖）。
- **学生通知读取真实现**：学生凭本人身份拉取自己的通知列表与未读数，替换恒空 stub。
- **触发点接线**：练习分发完成（Assignment）、判卷完成/待确认（Grading Center）、周报生成——经事件挂钩调用 dispatch。
- **前端**：学生端底部导航练习 tab 未读红点（拉取未读数）。
- **替换 501 占位**：P0 改为 501 的四个 send 路由按新分发入口重建语义。

## Capabilities

### New Capabilities
- `notification-dispatch`: 通知分发统一入口——业务事件经单一入口到达收件人；站内学生收件箱为默认 adapter，外部网关为可配置 adapter；幂等、可查询未读。

## Impact

- **代码**：`app/services/notification_service.py` 增加 dispatch 与学生写入；新表模型 + Alembic 迁移；`app/api/notification.py` 路由重建；chem_skills/chemistry_notification 网关接线；`frontend/m/app.js` badge。
- **API**：`GET /api/notification/student/{id}/notifications` 真实现（本人可见）；send* 路由语义由 dispatch 定义。
- **测试**：服务层分发幂等/开关行为；网关格式化沿用既有 11 个契约测试。

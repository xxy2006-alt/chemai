# 通知分发与学生收件箱 — 设计决策

> 来源：grilling 定案（2026-09-12），决策编号 C3-1。
> 总纲：ADR-0012；触达决策与 ADR-0005 不冲突（0005 否决的是 agent 后台轮询/主动推送，落表+学生拉取不在其列）。

## 载体定案（决策 C3-1）：站内 inbox + 网关接为第二 adapter

两步都做：

1. **站内（闭环最小集）**：StudentNotification 表 + NotificationService 学生方法 + 学生本人拉取端点 + 学生端 badge。不依赖任何外部平台，学校环境零配置可用。
2. **网关接为 adapter**：chemistry_notification 的四网关（Discord/Slack/Telegram/Email）经统一分发入口在配置开关下外发。skill 从孤岛变成第二 adapter——「一个 adapter 是假想 seam，两个 adapter 才是真 seam」；格式化沿用 9a26b8a 定下的 (platform, data) 模板契约。

否决「只做站内」（孤岛继续漂着，未来接线又是一次平行实现）；否决「只接外发网关」（依赖学生在群里且看消息，站内无感知，badge 体验丢失，学校环境未必允许）。

## Interface

```
dispatch(recipient: {role, id}, event: {type, payload}, idempotency_key) -> None
  # 站内写入为默认动作；网关开关开启时按事件类型外发
unread_count(student_id) -> int
mark_read(student_id, notification_id) -> None
```

幂等键语义与既有 `_dedup_notification_id` 一致（ADR-0006 至少一次投递 → 消费端幂等）。

## 触发点

| 事件 | 触发方 |
|------|--------|
| 布置完成（逐生） | assignment_service 通知挂钩 |
| 判卷完成 / 考试待确认 | grading_center save/confirm 尾部 |
| 周报生成 | 既有周报路径 |

## 测试决策

- 服务层为测试面：dispatch 幂等（重放不重复落通知）、网关开关关闭时只落站内、开启时站内+外发各断言一次。
- 学生端点：本人可见、他人 403（复用 test_api_auth_notification 的 IDOR 测试模式）。
- 网关格式化：沿用 chem_skills/chemistry_notification 既有 11 个契约测试，不重写。

## Out of Scope

- 实时推送（SSE/WebSocket）——学生拉取 + badge 已满足闭环；ADR-0005 明确不做 agent 侧推送。
- 教师收件箱（教师触达后续需要时另行）。
- 通知中心独立页面（badge + 练习页入口够用）。

## 追加决策（2026-09-14）
- **网关保守禁用（发现 #8）**：无 per-收件人 chat_id/webhook 配置时网关直接不外发（宁可不发不可把学生成绩广播进共享频道）；per-收件人路由列为后续配置项。

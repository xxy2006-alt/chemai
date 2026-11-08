## Context

家长端 `parent.html` 已有基础功能（概览/报告/通知/AI聊天），需要增强报告展示和教师-Parent双向打通。

## Goals / Non-Goals

**Goals:** 完整报告展示、AI总结、教师推送→家长接收
**Non-Goals:** 不新建数据库表、不改家长端页面架构

## Decisions

### D1: AI 摘要 — 后端 DeepSeek 调用

新建 `POST /api/parent/child/{sid}/report/ai-summary` 端点，接收 `{section, data}`，调 DeepSeek 生成 2-3 句通俗摘要。

**理由:** API key 保留在服务端。前端只传数据片断，不传敏感信息。

### D2: 教师→家长 — Agent 两步确认

分开两个工具：`generate_parent_report`(生成预览) 和 `send_report_to_parent`(发送)。教师必须明确说"发"才推送。

**理由:** 给教师修改和确认的空间。跟学习计划流程一致。

### D3: 报告推送 — ParentNotification

报告作为 `type="weekly_report"` 的通知写入 `parent_notifications` 表，`content` 存完整报告 JSON。家长端通知列表点报告型通知 → 展开报告面板。

**理由:** 复用现有通知基础设施。不新建表。

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| AI 摘要质量不稳定 | 按钮可重复点击重新生成 |
| 报告数据量大导致通知 content 过长 | JSON 控制在 5KB 以内 |

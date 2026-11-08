---
name: chemistry-notification
description: ChemAI 消息通知网关。支持 Discord/Slack/Telegram/Email 多渠道推送，实现作业通知、错题报告、学习计划等精准送达。
version: 1.0.0
author: ChemAI
license: MIT
metadata:
  hermes:
    tags: [notification, discord, slack, telegram, email, messaging]
    related_skills: [chemistry-memory, chemistry-diagnosis]
---

# Chemistry Notification Skill

## Overview

ChemAI 的消息通知网关，支持多种渠道推送各类教学通知。

## Supported Channels

| 渠道 | 用途 | 特点 |
|------|------|------|
| Discord | 班级群作业通知 | 实时、群组 |
| Slack | 企业协作 | 集成、归档 |
| Telegram | 家校通知 | 即时、加密 |
| Email | 正式报告 | 正式、存档 |

## Notification Types

| 类型 | 渠道 | 内容长度 |
|------|------|---------|
| 作业布置 | Discord/Slack | 短摘要 |
| 错题报告 | Telegram/Email | 完整报告 |
| 学习计划 | Telegram/Email | 详细计划 |
| 班级通知 | Discord/Slack | 短通知 |
| 成绩预警 | Email | 简短+建议 |
| 日常鼓励 | Telegram | 简短 |

## Templates

所有推送模板支持多格式：
- `default` - 标准格式
- `discord` - Discord 嵌入式
- `slack` - Slack Block Kit
- `telegram` - Telegram Markdown
- `email` - Email HTML/Text

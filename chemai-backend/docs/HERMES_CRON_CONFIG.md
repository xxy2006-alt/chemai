# ChemAI × ChemAI Agent Cron 配置指南

## Cron 任务配置命令

在 ChemAI Agent 中使用以下命令配置定时任务：

---

### 1. 每日学情检查 (每天 8:00)

```bash
hermes cron add "chemai-daily-check" \
  --schedule "0 8 * * *" \
  --action "call chemai.trigger_warning_check" \
  --platform telegram \
  --description "每天8点检查学生学情，异常时推送给教师"
```

**功能**：自动检测学情异常（3天未登录、成绩下降、错题率>50%），有异常时通过 Telegram 通知教师。

---

### 2. 复习提醒 (每天 20:00)

```bash
hermes cron add "chemai-review-reminder" \
  --schedule "0 20 * * *" \
  --action "call chemai.get_review_tasks" \
  --platform telegram \
  --description "每天20点提醒学生复习到期任务"
```

**功能**：检查学生当日到期复习任务，通过 Telegram 推送提醒，学生完成后记录结果。

---

### 3. 家长周报推送 (每周五 18:00)

```bash
hermes cron add "chemai-weekly-report" \
  --schedule "0 18 * * 5" \
  --action "call chemai.send_weekly_reports" \
  --platform telegram \
  --description "每周五18点汇总周报推送给家长"
```

**功能**：汇总全班学生本周学习情况，生成周报并推送给家长。

---

### 4. 晨间练习推送 (每天 7:30)

```bash
hermes cron add "chemai-morning-practice" \
  --schedule "30 7 * * *" \
  --action "call chemai.generate_questions" \
  --platform telegram \
  --description "每天7:30推送今日练习题"
```

**功能**：根据课程表或知识点安排，每日推送适量练习题。

---

## Cron 任务配置参数说明

| 参数 | 说明 | 示例 |
|------|------|------|
| `--schedule` | Cron 表达式（本地时区） | `"0 8 * * *"` |
| `--action` | 触发的 Action | `"call chemai.trigger_warning_check"` |
| `--platform` | 推送渠道 | `telegram/discord/email` |
| `--description` | 任务描述 | `"每天8点检查学情"` |

## Cron 表达式参考

| 表达式 | 含义 |
|--------|------|
| `0 8 * * *` | 每天 8:00 |
| `0 20 * * *` | 每天 20:00 |
| `0 18 * * 5` | 每周五 18:00 |
| `30 7 * * *` | 每天 7:30 |
| `0 */2 * * *` | 每 2 小时 |
| `0 9 * * 1-5` | 工作日 9:00 |

## 查看已配置的任务

```bash
hermes cron list
```

## 删除任务

```bash
hermes cron remove chemai-daily-check
```

## 手动触发任务测试

```bash
hermes cron trigger chemai-daily-check
```

---

*文档版本: V1.0*
*创建日期: 2026-04-24*

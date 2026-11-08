# 业务闭环整改批次（Loop Remediation）

## Why

外部声音审查（10 发现，判定 FIX FIRST）经代码核实全部属实：线上考试提交绕过确认制且不喂诊断（C1-3 违约）；主观题判定失败静默丢失且无 Redis 部署上提交请求内阻塞 LLM；题型按学生作答文本启发式判定导致短化学式（Be/HF）被误判；练习重做被静默丢弃但完成数照加；chat 每答触发一次诊断作业；同步布置毫秒时间戳无幂等；网关单 chat_id 广播属隐私事故；finalize 部分数据即可收卷；全闭环无 e2e 且 adaptive 硬编码 choice。修复设计已经 grilling 定案（ADR-0013 + 各 change design.md 追加决策）。

## What Changes

- **成绩确认门（confirmed 列）**：考试作答默认 `confirmed=False`，`confirm(exam_record_id)` 批量翻转并触发诊断；诊断/finalize/错题本/统计读侧只认生效行；练习/chat/training 默认生效。
- **主观题「落行 + 消费」管线（ADR-0013）**：提交时主观题落 `PENDING_SEMANTIC` 行，Celery/APScheduler 双路消费覆盖判定；判定失败保留待扫，永不静默丢失；提交路径零 LLM 调用。
- **题型路由**：AnswerKey 增可选 `choice` 标记（题库路径从 options 提供）；无元数据回退双边启发式；废除单边 `_is_choice(学生作答)`。
- **练习重做 upsert**：save 对练习路径覆盖更新（重放同值无害）；EXAM 一次性守卫不变。
- **chat 诊断去抖**：Student 增 `diagnosis_requested_at`，5 分钟窗口去重。
- **同步布置幂等**：sync 路径 record_id 加内容摘要。
- **网关保守禁用**：无 per-收件人配置不外发。
- **finalize 参与率 + 闭环 e2e + adaptive 主观题型**。

## Capabilities

### Modified Capabilities
- `grading-center`：确认门、待判定管线、题型路由、重做 upsert、finalize 参与率
- `assignment`：同步幂等、adaptive 主观题型
- `notification-dispatch`：网关保守禁用
- `chat-answer-capture`：诊断去抖

## Impact

- **代码**：grading_center/practice/jobs(handlers+新扫描作业)/assignment_service/notification_service/tutoring；Student/StudentAnswer 各加一列；migrate.py 幂等迁移。
- **读侧契约**：诊断/finalize/错题本/统计增加「生效行 + 非待判定」过滤（统一查询助手收敛）。
- **合入门**：本批次修完并全量绿后才合 main（CEO/ENG 审查 ISSUES_OPEN 的整改）。

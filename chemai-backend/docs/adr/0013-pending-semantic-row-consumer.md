# ADR-0013: 主观题判定「落行 + 消费」——判定不丢失契约

**Date**: 2026-09-14
**Status**: Accepted（grilling 定案，修复外部声音 #2/#6）

## Context

外部声音审查发现两个已证实的缺陷：主观题 LLM 语义判定失败时作答被静默丢弃（judge_failed 行被作业丢弃、Celery autoretry 因无异常永不触发、无持久待判状态）；无 Redis 的参考部署上 `enqueue_job` 同步降级导致提交请求内阻塞 LLM 调用。两者的共同根因：主观题判定被建模为「提交时的动作」而非「持久状态 + 异步消费」。

## Decision

1. 主观题作答在提交时**立即落 StudentAnswer**：`is_correct=False`、`grade_reason='PENDING_SEMANTIC'`。学生看到「已提交，N 道主观题判定中」。
2. 消费端双路共用同一段判定代码：有 Redis 走 Celery 作业；无 Redis 走 APScheduler 周期扫描（扫 `grade_reason='PENDING_SEMANTIC'` 行）。判定结果**覆盖更新**该行，随后触发诊断与通知。
3. 判定失败不清除标记——该行留待下一轮扫描重试。**判定不丢失契约**：任何已落行的主观题作答最终会被判定或保持可见的待判定态，永不静默消失。
4. 诊断与统计读侧排除 `PENDING_SEMANTIC` 行（成绩未定的作答不入学情）。

## Consequences

- Positive：#2（丢失）与 #6（无 Redis 阻塞）同时消灭；提交路径零 LLM 调用。
- Positive：幂等天然成立——判定是覆盖更新，重放/重扫同值无害。
- Negative：诊断/统计/错题本读侧多处需加排除条件（遗漏一处就会让未定成绩漏入学情）——以统一查询助手收敛。
- Negative：无 Redis 部署的判定延迟取决于扫描周期（默认 2 分钟），产品语义为「主观题判定本就异步」。

## Alternatives Considered

- **grading_pending 备份表 + 队列失败时写入**：两张表两套生命周期、两条落库路径，否决。
- **handler 内 raise 交给 Celery autoretry**：同步降级路径没有消息可重放，丢失原样保留，否决。

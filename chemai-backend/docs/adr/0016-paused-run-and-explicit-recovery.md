# ADR-0016: Paused Run 与显式恢复契约——恢复永不自动

**Date**: 2026-09-20
**Status**: Accepted（grilling 定案；架构评审报告 architecture-review-20260920）

## Context

「打断后智能体自动尝试和恢复都有问题」的排查结论（2026-09-20）：恢复的实现方式是让 agent
再跑一遍——

- 清中断 = 偷偷 `ainvoke(Command(resume="cancelled"))` 跑一个完整 agent turn：事件全丢、
  副作用照跑（langgraph_channel.py:149-158）；若该 turn 再中断，后续流挂死至 180s 超时。
- GuardState 在进程内存：重启后点批准只改 DB、重放无物，草稿搁浅在 approved-never-sent。
- checkpoint 任务带 error 即永久毒化线程（生产日志 chemai_agent_errors.log 的 OpenAI 400
  「insufficient tool messages」已实证），只能「请新对话」。
- 无会话锁：双击批准 / 双标签页并发两条流，在同一 thread 上交错写 checkpoint。
- 客户端断开即静默取消，前端把无 [DONE] 的流当正常收尾——「看不见的取消」。

领域语言里「等待老师决定」（Confirmation Gate）与「被系统挂起」（Paused Run）此前共用一个
词汇（`phase:awaiting_approval`），两个状态、两个出口被压成一个。

## Decision

1. **Paused Run 是一等状态**（CONTEXT.md 已立词条）：客户端断开、服务重启、回合崩溃、
   残留中断 → run 标 paused，步骤状态与开着的门原样保留。gated（等待人工）与 paused
   （系统挂起）是不同状态、不同出口。
2. **恢复永不自动**：图级不重跑（重跑 = 双发副作用）；重试只存在于模型调用层
   （ChatOpenAI max_retries，维持）。恢复的唯一路径是老师的显式动作：决定一个门、发下一条
   消息、或刷新后经 /history 重同步再操作。
3. **断线即取消 + 立刻 paused**：取消点维持现状（不 shield 工具协程），但 run 立即标
   paused、执行到哪步如实入库；绝不自动重试。
4. **毒化自动迁移**：checkpoint 任务带 error → 自动开新 thread，messages 历史 + 活跃
   run/gate 实体迁过去，旧 thread 作废，老师无感。
5. **每会话一把 asyncio 锁**：/stream 与 /resume 共用；争用立即 409「已有进行中的回复」，
   不排队。前端流式期间禁用确认按钮与输入（handleDecision 补 streaming 检查）。

## Consequences

- Positive：「看不见的取消/重试」消失，恢复行为可预测（永远显式）。
- Positive：断线 / 重启 / 毒化三类故障共用一个恢复契约（paused + /history 重同步）。
- Negative：断线后当前工具可能执行到一半即停，副作用不回滚——与 At-least-once Delivery
  契约一致，靠幂等键兜底。
- Negative：自动迁移逻辑本身是新风险面，需迁移后校验（run/gate 计数一致）。

## Alternatives Considered

- **后台跑完当前 turn**：老师回来看到结果就绪，体验顺；但「看不见的副作用在跑」与确认门
  理念相悖，还需后台任务生命周期管理。否决。
- **锁争用排队等待**：免改前端防重，但第二次点击延迟生效，感知成「幽灵双发」。否决。
- **shield 当前工具协程跑完再停**：半途而废最少，但多一层 asyncio 复杂度，收益有限。否决。

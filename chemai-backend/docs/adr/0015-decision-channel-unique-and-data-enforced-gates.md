# ADR-0015: 决策通道唯一化与门的数据强制统一——自然语言批准退役、布尔门实体化

**Date**: 2026-09-20
**Status**: Accepted（grilling 定案；架构评审报告 architecture-review-20260920）

## Context

架构评审（2026-09-20）沿 ADR-0013「两套门并存直至逐一实体化」的预告收尾时，钉出四类缺陷的
共同根因：Confirmation Gate 这一个领域概念在代码里是三个互不知情的实现，且批准语义存在两条
通道：

- **门覆盖与键错位**：门开着时 LLM 仍可继续调工具，第二个门直接覆盖
  `GuardState.pending_approval`（guard.py:284-289）；批准决定记在 `decision.draft_id` 上、
  重放却取 `pending_approval` 的 fn/kwargs（channel:907-924 vs 1154）——「批准发学生的卡片
  重放发家长的调用」由此而来。
- **自然语言批准**：/stream 上 ≤12 字含「发送」即判批准——「不要发送」= 批准并真发
  （guard.py:79、channel:313-336）；前端却把门开着时打字一律当打回，同一动作两种语义。
- **粘性 approved**：`guard_state.approved` 置 True 后永不复位，同轮后续破坏性工具全放行。
- **步进权错位**：SSE adapter 把 `approval_needed`（不含 error）当 success，门步骤被标
  completed、下一步立刻 running（langgraph_sse_v2.py:161/318/383-399）——「人工还没确认
  就往下推」。

## Decision

1. **决策通道唯一化**：批准只来自 /resume 的结构化三值决定（ADR-0013 协议）与「点击即
   决定」的面板/REST 入口（内部同样走决定原语，审计留痕）。/stream 上的自然语言确认词
   降级为引导（回复「请点击确认卡」，零副作用）；门开着时的其他打字一律 reject+feedback。
   ADR-0013 的「确认白名单→approve」向后兼容条款正式废止（同仓同部署，无旧客户端）。
2. **门统一数据强制**：布尔门（assign_adaptive_practice / delete_bank）实体化——
   `conversation_gates` 演进为通用 gate 实体（kind: draft|boolean，携带 tool+kwargs 或
   draft_id）。拦下→登记实体→返回等待；批准→按实体重放。draft 与 boolean 成为同一
   seam 后的两个 adapter。图内 `interrupt()` 与 `request_approval` 工具整体退役：门不再
   依赖图中断，孤儿中断以纯状态标记处理（不 ainvoke、不偷跑模型）。
3. **一决定一动作**：决定必带 gate_id，重放前强校验一致；不一致拒绝执行并重发当前门状态。
   粘性 `approved` 概念退役；out-of-workspace 文件提权与门分离，改为真·单次
   （一次调用后失效，与 `set_elevate_once` 的名字终于一致）。
4. **步进权归位**（ADR-0012 的应用）：Plan Run 步进状态机由 plan_run_service 独占；
   `awaiting_confirmation` 是绝对阻塞态——门开着，任何后续步骤不得标 running，GuardState
   机械拒绝 agent 的一切工具调用。「被门拦下（未批准）」与「批准后重放完成」由双驱动转移
   区分：`approval_needed`→awaiting，approve→running（重放中），重放成功→completed。

## Consequences

- Positive：学生/家长交叉发射、门覆盖、幽灵批准、「未确认就推进」四类缺陷在语义层根除，
  不再依赖提示词自觉。
- Positive：门的测试面收敛到一个 interface（open→decide→replay）＋两个 adapter；重启后
  布尔门与草稿门同等待遇（DB 可重建）。
- Negative：/stream 确认分支重写为引导文案后，依赖自然语言批准的旧脚本（如
  _e2e_plan_hitl.py 部分断言）需同步改造。
- Negative：`interrupt()` 退役后，LangGraph 线程上残留的旧中断状态需要一次性迁移处理。

## Alternatives Considered

- **收紧词表保留自动批准**：精确匹配可救「不要发送」，但「确认意图→直接执行副作用」的
  风险通道仍在。否决。
- **保留 interrupt() 只修清理**：LangGraph 取消中断必须 `Command(resume)` 恢复执行——
  「不跑模型的清理」在该机制下不可表达。否决。
- **布尔门用内容哈希当身份、不建实体**：轻量，但重启即失、/history 无法重建，seam 后
  只剩一个真 adapter。否决。

# ADR-0013: 确认门实体化与三值决定协议——打回-修订-再确认循环

**Date**: 2026-09-12
**Status**: Accepted（grilling 定案，spec 见 GitHub issue #9）

## Context

学习计划的「确认后发送」存在系统性断裂：拒绝在线上协议里只是一个无理由的布尔值
（`message: 'approved'|'cancelled'`）；老师打字反馈会被前端涂成假批准、被 channel 作废
挂起审批并当作全新回合流转；agent 无修订原语，只能无上下文重新生成；todolist
（plan_steps）是单回合内存投影，修订回合一开，剩余步骤全部孤儿化。根因有三：

1. **门没有实体**——审批是 GuardState 里的进程级一次性布尔（`set_elevate_once`），
   重启即失，也没有版本与反馈链。
2. **协议没有词汇**——线上只有两个字符串，「打回 + 修改意见」无法表达。
3. **运行不跨回合**——计划状态只活在单个 180 秒回合与内存 guard 缓存里。

openspec `learning-plan-redesign` 的 design D2 曾决定「不新建表，复用 SqliteStore」——
那是为「持久化已发送计划」做的，装不下确认门的状态机（活跃草稿约束、版本链、
审批记录），本 ADR 正式取代 D2。

## Decision

1. **计划草稿是一等实体**（`learning_plan_drafts` 表）：同 draft_id 版本链、
   status 状态机（`awaiting_confirmation →（revise）* → sent`；regenerate 标
   `superseded`）、每版记录老师反馈、`teacher_approved` 是发送放行的唯一钥匙。
   生命周期（生成/修订/决定/发送）全部住在 `PlanDraftService`；agent 工具、
   REST 端点、InlinePanel 按钮皆为薄 adapter（沿用 ADR-0012）。
2. **三值决定协议**：`/resume` 请求体新增 `decision {action: approve|reject|abandon,
   feedback?, draft_id?}`。批准 → 发送并推进剩余步骤；打回 → 必带反馈，channel
   确定性调 `service.revise_draft` 出新版本、重开门（闭环靠契约，不靠模型自觉）；
   放弃 → 门步骤取消、运行继续、草稿保留。旧字符串向后兼容映射
   （`approved`→approve、`cancelled`→abandon、确认白名单→approve）。
   新前端在门开着时一律走 `/resume`；channel 在 `/stream` 上对草稿门开着时的
   打字输入按「打回+反馈」处理，属防御旧客户端/直连调用的兜底分支，非新协议的一部分。
3. **门由数据状态强制**：`send_draft` 对未经确认的草稿一律返回 `approval_needed`——
   学习计划路径上的进程级提权布尔退役（家长报告路径暂留）。
4. **Plan Run 实体化**（`plan_runs` 表）：todolist 按 conversation 持久化，
   步状态机扩展 `awaiting_confirmation / revising / cancelled`，历史接口携带活跃
   run 与待决门（刷新/重启后重同步）。每会话最多一个活跃 run。
5. **发送效果补全**：经 Notification Dispatch 投学生收件箱
   （`student_notifications` 表），幂等键 `draft_id+version`。
6. **权限挂 Data Scope**：确认/打回/放弃/发送按「老师教该生所在班」的关系检查
   （REST 走 ScopeGuard，agent 走 service 关系检查），不绑生成草稿的会话。

## Consequences

- Positive：打回-修订-再确认循环成为一等公民；门循环可多轮， todolist 不再孤儿化。
- Positive：门循环的测试面收敛到三接缝（SSE 事件序列、service 生命周期、reducer 投影）。
- Positive：刷新页面、服务重启后 todolist 与待确认门完好。
- Negative：两张新表 + 学生通知表需随 `create_all` 建表（本项目 alembic 目录已停滞，
  新表走启动时 `Base.metadata.create_all`，与现状惯例一致）。
- Negative：`guard_state.approved` 的会话内粘性与 elevation 机制仍在（家长报告、
  文件访问、布置练习路径），两套门并存直至这些路径逐一实体化。

## Alternatives Considered

- **图内 interrupt + LLM 自主修订**：闭环成立依赖模型自觉调 request_approval /
  revise 工具——今天假门正是这个失败模式的产物；且多轮修订挤 180s 回合与递归预算。否决。
- **SqliteStore key-value 存草稿**（延续旧 D2）：状态机、版本链、每生活跃约束全靠
  key 约定拼装，service 无法拥有实现。否决。
- **两值门（批准/拒绝）+ 可选反馈**：「空反馈的拒绝」是要改还是算了，又变成模型
  猜测题。否决——三值把意图表达清楚。

# ADR-0014: Agent 工具层纳入 Data Scope——接缝统一校验，而非逐工具自查

**Date**: 2026-09-14
**Status**: Accepted（grilling 定案）

## Context

阶段 4 把 232 个 HTTP 端点接上了认证、权限与 Data Scope（ADR-0009 / ADR-0010），**但 agent 工具层完全绕过这一层**：42 个工具全部进程内直调 service，不走 HTTP，因此 `PermissionChecker` 与 `RequestScope` 对它们一律无效。

实测（2026-09-14）：

- **16 / 42 个工具**收身份类参数（`student_id` / `class_id` / `teacher_id` / `student_name` / `class_name`）。按 persona 白名单交叉：11 个在 `teacher` persona，`weekly_report` + `diagnose_barrier` 在 `parent` persona，`memory_student_get` 在 `student` persona。
- **`weekly_report` 是可实际利用的入口**：参数既可传学号也可传姓名，姓名走 `SELECT ... WHERE name LIKE '%…%'` **全库模糊匹配**，全程无范围校验。家长一句「看看张浩宇的周报」就能拿到别人孩子的 `name / class_id / barrier_type / exercises_completed` 并生成报告——**不需要知道学号，知道名字即可**。
- **身份机制形同虚设**：`agent/tools/context.py` 的 docstring 写着「服务端身份优先于模型输入／无法通过传参冒充其他教师」，但 `guard.py:225` 的实现是**只在模型没传 `teacher_id` 时补上**——模型传了就信模型。且 `student_id` / `class_id` **连默认填充都没有**。
- 三个 agent 端点里，**非流式那个（`agent_chat_langgraph`）没有注入身份**。

`CONTEXT.md` 已经写明 Persona ≠ Role，且「a teacher may open a `tutor`-Persona conversation and stays a `teacher` throughout」——即 **Agent 会话本应处在某个 Role 的 Data Scope 之下**。所以这不是「缺一个功能」，是**实现违反了项目自己已经写下的模型**。

## Decision

1. **校验点放在接缝**：`agent/guard.py` 的 `_guarded`。它是全部工具调用的唯一必经点（v2 在 `langgraph_agent_v2.py:246` 用 `_make_guarded_tool` 逐个包装，v1 同源），且身份注入本就在那里。
2. **工具通过 `TOOL_META` 声明**「参数 → 范围维度」（如 `{"student_id": "student", "class_id": "class"}`）。接缝执行，工具不写校验代码。
3. **接缝统一处理「ID 或姓名」**：值不是 ID 时，在**调用者范围内**做模糊搜索。搜不到即拒，措辞用「未找到名为 X 的学生」而**不是**「无权访问」——沿用 `ScopeGuard` 已有的「查不到一律 403、不泄漏存在性」惯例。解析出的 ID 回填 `kwargs`，**工具代码不需要改**（工具里 `if not isdigit()` 那条分支对 agent 路径自然失效，直接调用/SDK 的调用方照旧）。
4. **身份从已签名的 token 扩进 `contextvars`**：`role` / `school_id` 本来就在 JWT payload 里（`create_access_token(user_id, role, school_id)`），channel 现在只是把它们丢掉了。三个 agent 端点都注入（含补上非流式那个缺口）。
5. **fail-closed**：没有身份时，收身份参数的工具一律拒绝。与 `RequestScope` 的 fail-closed 一致。
6. **评测身份按 persona 忠实映射**（`teacher→学科组长` · `tutor/student→学生` · `parent→家长`），场景可用 `identity: {username: ...}` 显式覆盖——越权类 eval 必须能声明「我是谁、要越谁的权」。
   实现见 `evals/identity.py`：**按角色从库里解析**、不写死账号（本文档原文写的是 `teacher_hai` / `202610201` / `lgh`，2026-09-14 演示数据整体换过一轮后全部失效），身份字段一律经 `get_user_info()` 产出，与登录下发 token 同一口径。`tutor` 与 `parent` 刻意取同一家人，家长场景问自己孩子才是「范围内」的那一半。

配套守卫测试：**收了身份参数却没在 `TOOL_META` 里声明范围维度的工具 → 直接红**。这是本决策能被长期遵守的关键——新增工具忘了声明会被拦住，而不是静默放行。

## Consequences

- **范围「规则」仍然只有一个家**（`RequestScope`），接缝只是 agent 路径上的**应用点**。这与 ADR-0012「业务逻辑的唯一家园是 service module，agent 工具是薄 adapter」一致：接缝做的是授权（横切关注点，和护栏同类），不是业务逻辑。
- ⚠️ **范围过滤必须在「搜」的时候就做，不能等匹配完再判**（2026-09-14 实施中踩到并修复）：第一版把过滤放在 `many` 分支**之后**，于是候选列表原样带出全库 LIKE 结果 —— 家长搜一个常见姓氏（「周」）拿到**全校 7 个学生的姓名 + 学号**。这恰好是决策 3 要封的那条路的变体（不泄漏存在性）。现在解析时就用 `scope.student_ids()` / `class_ids()` 收窄，范围外的名字一律表现为「查不到」。回归测试：`tests/test_teacher_identity.py::test_guard_does_not_leak_out_of_scope_candidates`（探针串动态生成，不写死姓名）。
- **评测从「无身份」这个线上不存在的状态，变成真实身份** —— 现有 evals 一直跑在真实用户永远不会遇到的上下文里，这个改动顺带修掉了它。
- **14 / 70 个场景需要复看**（提到身份类工具的那些）。但实测：它们的断言里 **19 条是 `tool_called` 只有 3 条 `has_text_response`**，且**零个场景硬编码真实学号**（占位学号 `S001` 只出现一次）——即这批场景测的是「agent 会不会挑对工具」，不是「能不能拿到数据」，所以打分漂移预计很小。仍需跑基线对比确认。
- **写 / 发送类工具保留已有的 `_consume_elevation` 审批门，另加范围校验**。两者正交：审批门管「要不要发」，范围管「发给谁」。`send_report_to_parent` 写的是本项目自己的 `ParentNotification` 行（不是外部短信/邮件），所以可以确定性断言。
- ⚠️ **实施前必须验证 `contextvars` 的跨 task 传播**：它是任务级隔离的，若 SSE 的流式生成器跑在与端点函数不同的 task 里，注入的身份传不进工具。真传不进就得改成显式传参，工程影响会跳一档。

## Alternatives Considered

- **逐工具自查（16 处）**：否决——会腐化。这正是本次 RBAC 改造的根因「没写检查不会报错」；16 处分散校验，新增工具忘了写没有任何东西会提醒。
- **下沉到 service 层校验**：否决——要给每个 service 函数传调用者身份（签名全改），而 HTTP 侧已经在 router 层做过一遍，会变成双重校验；且 service 层现在完全不知道「谁在调用」。
- **fail-open（无身份则按旧行为放行）**：否决——会让「新增第 4 个 agent 入口、忘了注入身份」成为一个**永久静默**的洞，复刻同一个根因。
- **接缝只校验 ID、姓名交回工具自己按范围搜**：否决——留下的正是**实际可利用的那条路**（家长用姓名查别人孩子）。
- **全部场景用 `teacher_hai` 一个身份**：否决——`tutor`（学生端）persona 有 32 个场景是最大群体，用教师身份跑学生 persona 会让 `memory_student_get` 被放行，**恰好测不出「学生只能看自己」**，而那是最需要被测的一条。

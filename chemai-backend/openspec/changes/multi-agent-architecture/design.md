## Context

ChemAI 当前是单体 ReAct agent（`agent/langgraph_agent.py`），绑了 14 个工具。Graph 结构为 `START → llm → router → check → tools → llm (loop)`，其中 router 和 check 节点是在 LLM 选错工具之前拦截的补丁。根因是 14 个工具造成 LLM 上下文过载，选不准工具。

当前关键约束：
- `tools.py` 中工具函数有 `_route` / `_component` 字段，被 GuardState 剥离后存到 `last_route` / `last_component`
- SSE 适配器 `LangGraphSSEAdapter` 在 `finalize()` 中从 `guard_state` 读取 route/component 发出事件
- `MemorySaver` 模块级共享（`_checkpointer`）
- `request_approval` 使用 `interrupt()` 暂停 graph，`/resume` 端点用 `Command(resume=...)` 恢复
- 4 个 API 端点：`/chat/langgraph/stream`, `/chat/langgraph`, `/chat/langgraph/resume`, `/chat/langgraph/reset`

## Goals / Non-Goals

**Goals:**
- 将单体 14-tool ReAct 拆成 5 个 sub-agent，每个绑 2-4 个工具
- Sub-agent 是独立的 StateGraph node（非 @tool 黑盒）
- Coordinator + Router 做意图路由
- GuardState 下沉到 sub-agent 层
- 跨 agent 共享学生/班级信息（shared_context）
- 现有 API 端点和 SSE 格式保持兼容

**Non-Goals:**
- 不引入 `langgraph-supervisor` 库
- 不改 `tools.py` 函数签名
- 不改前端 `agent.js` / `index.html`
- 不新增浏览器 agent（另见 `browser-agent` change）
- 不删除旧 router/check 代码（另见 `remove-legacy-nodes` change）

## Decisions

### D1: Sub-agent 是独立的 StateGraph node

Sub-agent 不作为 coordinator 的 `@tool` 黑盒，而是和 coordinator 平级的 graph node。
Coordinator 用 `with_structured_output` 输出 `RoutingDecision`，Router 节点 dispatch 到 sub-agent node。
Sub-agent 用 `create_react_agent` 编译，嵌入 coordinator graph。

**Why:** node 形式直接共享 state（shared_context），interrupt 在 graph 层触发，`astream_events` 自然捕获。

### D2: Coordinator 不做 ReAct，做 one-shot 路由

Coordinator 只用 `with_structured_output` 输出一次路由决策，不绑定工具做 ReAct 循环。
如果 sub-agent 返回 `reroute`，coordinator 重新路由。

**Why:** 5 个路由选项 + 1 个 respond，比当前 14 选 1 简单得多。一次 LLM 调用就够了。

### D3: GuardState 下沉到 sub-agent

每个 sub-agent 拥有独立 GuardState（去重、限流、审批）。Coordinator 不需要 GuardState。

**Why:** 审批逻辑（`request_approval` → `interrupt()`）在 sub-agent node 内执行，interrupt 在 coordinator graph 上下文触发。

### D4: Shared context 通过 MultiAgentState 传递

```python
class MultiAgentState(MessagesState):
    shared_context: dict    # {student_id, student_name, barrier_type, class_id}
    route_decision: dict | None
    target_agent: str | None
    agent_query: str | None
    last_component: dict | None
    last_route: dict | None
    reroute: str | None
```

每次 `invoke()` / `astream_events()` 创建独立 state 实例，天然线程安全。

### D5: Sub-agent 和 coordinator 共享 checkpointer

Sub-agent 使用 coordinator 的 `_checkpointer`，确保 `interrupt()` 后 `/resume` 能从正确的 checkpoint 恢复。

### D6: SSE 事件过滤：抑制 sub-agent 内部事件

Sub-agent node 内部的 tool_call 事件通过 `metadata.langgraph_node` 前缀匹配过滤，不发给前端。
Component/route 从 state 读取，不依赖全局变量。

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| Coordinator 路由错误 | Sub-agent 可返回 `reroute`，coordinator 重新路由 |
| Sub-agent LLM 不按 output contract 返回 JSON | except 分支 fallback 为纯文本 |
| Sub-agent ReAct 循环超出 recursion_limit | Coordinator limit=12，sub-agent 内部 limit=3 |
| SSE 事件过滤依赖 LangGraph 内部 node 命名 | `langgraph_node` 前缀匹配。fallback: `config["tags"]` |
| 5 个 sub-agent 编译慢（冷启动）| 模块级 lazy init，首次路由到该 agent 时编译并缓存 |
| shared_context 并发请求交叉污染 | state channel 天然隔离，每次 invoke 创建独立实例 |

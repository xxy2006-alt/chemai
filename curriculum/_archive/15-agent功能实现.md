# 15 · Agent 功能实现

## LangGraph StateGraph 的完整实现

ChemAI 的 Agent 是基于 LangGraph 1.2 的 `StateGraph`，1 个协调器 + 6 个子专家 + 路由工具节点。以下是每一行的真实代码分析。

### 1. State 定义（`agent/langgraph_agent.py:147-158`）

```python
class MultiAgentState(MessagesState):
    shared_context: dict           # Agent 间共享上下文（学生信息、班级信息）
    route_decision: dict | None    # 协调器的路由决策 {agent, query}
    target_agent: str | None       # 路由器确定的目标子专家名
    agent_query: str | None        # 传给子专家的用户原始问题
    last_component: dict | None    # 子专家返回的内联面板指令（如 exam-workbench）
    last_route: dict | None        # 子专家返回的页面跳转指令
    last_result_text: str | None   # 子专家返回的纯文本结果
    reroute: str | None            # 子专家要求重新路由到另一个专家
    pre_routed_agent: str | None   # Gateway 预路由的目标（高置信度直接跳过 LLM）
    suggested_tools: list | None   # Gateway 建议的工具列表
```

`MessagesState` 是 LangGraph 内置的，自带 `messages: list[BaseMessage]` 字段。所以 MultiAgentState 实际有 11 个字段：`messages` + 上面 10 个。

关键设计：`pre_routed_agent` 让 Gateway 的关键词匹配结果直接传给协调器，跳过 LLM 路由判断。这是准确率从 70% 提升到 100% 的关键字段。

### 2. 节点清单（7 个节点）

| 节点 | 类型 | 文件位置 | 函数 |
|------|------|---------|------|
| `coordinator` | Python 函数 | `langgraph_agent.py:365` | `_coordinator_node` |
| `routing_tools` | ToolNode | `langgraph_agent.py:342` | `ToolNode(_ROUTING_TOOL_LIST)` |
| `router` | Python 函数 | `langgraph_agent.py:408` | `_router_node` |
| `search_expert` | create_react_agent | `langgraph_agent.py:191` | 子 Agent |
| `exam_expert` | create_react_agent | `langgraph_agent.py:191` | 子 Agent |
| `diagnosis_expert` | create_react_agent | `langgraph_agent.py:191` | 子 Agent |
| `tutor_expert` | create_react_agent | `langgraph_agent.py:191` | 子 Agent |
| `bank_manager` | create_react_agent | `langgraph_agent.py:191` | 子 Agent |
| `browser_expert` | create_react_agent | `langgraph_agent.py:191` | 子 Agent |

共 9 个节点（1 协调器 + 1 路由工具 + 1 路由器 + 6 子专家）。

### 3. 协调器节点 `_coordinator_node`（行 365-405）

三步路由决策，优先级从高到低：

**Step 1：重路由检查**（行 368-369）
```python
if state.get("reroute"):
    return {"route_decision": {"agent": state["reroute"], "query": ""}, "reroute": None}
```
子专家执行完后可能要求重新路由（如搜索专家搜不到结果，要求路由到出题专家）

**Step 2：返回检查**（行 372-374）
```python
if (len(msgs) >= 2 and isinstance(msgs[-1], AIMessage)
        and not getattr(msgs[-1], 'tool_calls', None)):
    return {"route_decision": {"agent": "respond", "query": ""}, "messages": []}
```
如果最后一条消息是子专家的纯文本回复（没有 tool_call），说明对话已完成。`respond` 表示不需要进一步路由。

**Step 3：Gateway 预路由**（行 377-388）
```python
pre_routed = state.get("pre_routed_agent") or state.get("shared_context", {}).get("pre_routed_agent")
if pre_routed:
    return {
        "route_decision": {"agent": pre_routed, "query": user_msg},
        "messages": [],
    }
```
这是性能关键路径。Gateway 已通过关键词匹配确定了目标专家（如在消息中检测到"出题"→ exam_expert），协调器直接采纳，不调用 LLM。

**Step 4：LLM fallback 路由**（行 390-405）
```python
model = get_langchain_model("deepseek")
model_with_tools = model.bind_tools(_ROUTING_TOOL_LIST)
response = model_with_tools.invoke([SystemMessage(content=_COORDINATOR_SYS_PROMPT)] + msgs)
```
前三步都没有命中时，由 LLM 判断路由。`_ROUTING_TOOL_LIST` 包含 6 个路由工具（`route_to_search_expert` 等），LLM 选择一个调用。

协调器的系统 prompt（行 349-362）：
```python
_COORDINATOR_SYS_PROMPT = """你是 ChemAI 调度员。分析用户消息，调用路由工具。

**只调工具，不说话！** 不要在调用前生成任何文字。

[ROUTING]
查学生/班级/障碍/诊断/练习 → route_to_diagnosis_expert
搜索/查资料/真题 → route_to_search_expert
出题/组卷/保存/考试 → route_to_exam_expert
讲解/实验/配平/周报 → route_to_tutor_expert
题库管理/删除题库 → route_to_bank_manager
打开网页/看网站 → route_to_browser_expert

**班级名/学生名一律走 diagnosis_expert，和关键词无关。**
只有闲聊/打招呼时才不调工具直接回复。"""
```

### 4. 路由工具节点 `routing_tools`（行 342）

```python
_routing_tool_node = ToolNode(_ROUTING_TOOL_LIST)
```

`_ROUTING_TOOL_LIST` 是 `_make_routing_tool` 生成的 6 个路由工具（行 305-341）。每个路由工具只是一个占位 function，实际不做任何事——它的存在是为了让协调器的 LLM 能通过 tool_call 来表达路由意图。

```python
async def _route(query: str = "") -> str:
    return f"已将请求路由到{display}"
```

ToolNode 执行后，进入 `router` 节点。

### 5. 路由器节点 `_router_node`（行 408-438）

```python
def _router_node(state: MultiAgentState) -> dict:
    decision = state.get("route_decision") or {}
    agent = decision.get("agent", "respond")
    if agent == "respond":
        return {"target_agent": None, "route_decision": None}
```

`route_decision.agent` 是协调器填入的（如 "exam_expert"）。路由器负责提取查询文本、设置 `target_agent` 和 `agent_query`，这些字段会被下游的子专家节点消费。

### 6. 子专家节点（行 173-242）

```python
def create_sub_agent_node(name, tool_names, system_prompt, approval_tools):
    guard_state = GuardState()
    tools = [_make_guarded_tool(t, guard_state, tn in approval) for tn in tool_names]
    tools.append(_make_request_approval_tool(guard_state))

    agent = create_react_agent(
        model=get_langchain_model("deepseek"),
        tools=tools,
        name=name,
        prompt=system_prompt + "\n\n" + _SUB_AGENT_OUTPUT_CONTRACT,
    )

    async def node_fn(state: MultiAgentState) -> dict:
        query = state.get("agent_query", "") or ""
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=full_query)]},
            {"configurable": {"thread_id": f"{name}-{uuid4()}"}, "recursion_limit": 7},
        )
        # 从 guard_state 提取 _component / _route
        return {
            "messages": [AIMessage(content=result_text)],
            "shared_context": {**ctx, **extracted_ctx},
            "last_component": component or (json_data or {}).get("_component"),
            "last_route": route or (json_data or {}).get("_route"),
            "last_result_text": result_text,
            "reroute": reroute,
        }
```

每个子专家是一个独立的 `create_react_agent` 实例，有自己的工具集、system prompt、GuardState。子专家之间不共享状态——只有 `shared_context` 在节点间传递。

`_SUB_AGENT_OUTPUT_CONTRACT`（行 165-170）：
```python
"""你必须先调用至少一个工具。工具返回后，基于工具返回的 result 字段输出。
如果工具返回 error，将 error 文本原样输出。
如果工具返回了 _component，不要输出任何额外文字。
严禁跳过工具调用直接生成回复。"""
```

### 7. Graph 编译（行 444-466）

```python
async def create_chemai_agent(persona, provider, ...):
    global _current_persona
    _current_persona = persona or "tutor"
    _agent_node_cache.clear()

    builder = StateGraph(MultiAgentState)

    # 添加 9 个节点
    builder.add_node("coordinator", _coordinator_node)
    builder.add_node("routing_tools", _routing_tool_node)
    builder.add_node("router", _router_node)
    for name in _SUB_AGENT_DEFS:
        builder.add_node(name, _get_or_compile_agent_node(name))

    # START → coordinator
    builder.add_edge(START, "coordinator")

    # coordinator 条件边
    builder.add_conditional_edges("coordinator", _route_after_routing, {
        "routing_tools": "routing_tools", "router": "router",
    })

    # routing_tools → router
    builder.add_edge("routing_tools", "router")

    # router 条件边
    builder.add_conditional_edges("router", _route_after_router, {
        name: name for name in _SUB_AGENT_DEFS
    } | {END: END})

    # 每个子专家执行完后回到 coordinator
    for name in _SUB_AGENT_DEFS:
        builder.add_edge(name, "coordinator")

    cp = await _get_checkpointer()
    graph = builder.compile(checkpointer=cp)
    return graph, None
```

### 8. 条件边函数

**`_route_after_routing`（行 428-431）**：
```python
def _route_after_routing(state: MultiAgentState) -> str:
    decision = state.get("route_decision") or {}
    if decision.get("agent") == "respond":
        return "router"  # 不需要路由工具，直接到路由器
    return "routing_tools"  # 需要 LLM 判断 → 先经过路由工具
```

**`_route_after_router`（行 434-442）**：
```python
def _route_after_router(state: MultiAgentState) -> str:
    target = state.get("target_agent") or state.get("route_decision", {}).get("agent")
    if not target or target == "respond":
        return END
    if target in _SUB_AGENT_DEFS:
        return target
    return END
```

### 9. Graph 可视化

```
                    ┌──────────────┐
                    │    START     │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  coordinator │ ◄──────────────────────────┐
                    └──────┬───────┘                            │
                           │ _route_after_routing()              │
              ┌────────────┼────────────┐                       │
              │ respond    │            │ needs routing         │
              ▼            │            ▼                       │
       ┌──────┐     ┌──────┴──────┐                            │
       │router│     │routing_tools│                             │
       └──┬───┘     └──────┬──────┘                            │
          │                │                                    │
          └────────┬───────┘                                    │
                   │ _route_after_router()                      │
    ┌──────┬───────┼───────┬──────┬──────┬──────┐              │
    │      │       │       │      │      │      │              │
    ▼      ▼       ▼       ▼      ▼      ▼      ▼              │
 search exam  diagnosis tutor  bank  browser  END              │
 expert expert expert   expert mgr   expert                    │
    │      │       │       │      │      │                      │
    └──────┴───────┴───────┴──────┴──────┴──────────────────────┘
              add_edge(name, "coordinator")
```

### 10. 对话持久化

```python
_checkpointer = None
async def _get_checkpointer():
    global _checkpointer
    if _checkpointer is None:
        conn = await aiosqlite.connect("chemai_checkpoints.db")
        _checkpointer = AsyncSqliteSaver(conn)
        await _checkpointer.setup()
    return _checkpointer
```

`AsyncSqliteSaver` 把每一次 StateGraph 的状态快照（checkpoint）写入 SQLite。对话中断后可以通过 `thread_id` 恢复。`builder.compile(checkpointer=cp)` 把这个持久化层注入到 Graph 中。

### 11. 从用户消息到子专家的完整数据流

1. 用户输入 → Gateway `classify()` 做关键词匹配（`agent/gateway.py:245-289`）
2. Gateway 返回 `IntentResult(type, tools, target_agent, confidence)`
3. `intent_hints` 传入 `create_chemai_agent` → 写入 `shared_context.pre_routed_agent`
4. Coordinator 读到 `pre_routed_agent`，直接设置 `route_decision`
5. Router 从 `route_decision` 提取 `target_agent` 和 `agent_query`
6. 子专家收到 `agent_query`，执行 `create_react_agent` → 调工具 → 返回结果
7. 子专家的 `_component` / `_route` 被 GuardState 剥离 → 写入 `state.last_component` / `state.last_route`
8. 子专家执行完 → coordinator → `respond` → router → END
9. SSE adapter 的 `finalize()` 读 `last_component` / `last_route` → emit SSE 事件
10. 前端收到 `component` 事件 → 渲染内联面板

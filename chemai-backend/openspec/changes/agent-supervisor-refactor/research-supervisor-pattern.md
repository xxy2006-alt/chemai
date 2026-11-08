# LangGraph Supervisor 模式深度调研 — ChemAI Agent 重构

**日期:** 2026-06-23
**背景:** ChemAI 当前 14 个工具的 ReAct agent 存在"上下文过载"问题——LLM 在 14 个工具定义里找不到正确的，router/check/pre-flight 是症状不是根因。

---

## 核心结论

**推荐方案：Pattern 1 — Subagents as Tools**

原因：
- LangChain 官方 2026 年 3 月起推荐 Subagents-as-Tools 作为默认生产模式
- `langgraph-supervisor` 库降级为快速原型工具，不再推荐用于生产
- Subagents-as-Tools 对上下文工程有完全控制，无黑盒

---

## 三种模式对比

| # | 模式 | 适合场景 | 样板代码 | 控制力 |
|---|------|---------|---------|--------|
| 1 | **Subagents as Tools** | 生产项目（官方推荐默认） | 中等 | 高 |
| 2 | **Supervisor** (`langgraph-supervisor`) | 快速原型、非重叠 agent | 最少 | 中 |
| 3 | **Handoffs** (peer-to-peer) | 顺序流程 A→B→C | 中等 | 高 |

### 决策矩阵

| 场景 | 模式 | 原因 |
|------|------|------|
| 2-5 个专家, 清晰路由 | Subagents as Tools | 完全控制, 官方默认 |
| 快速原型, 非重叠 agent | Supervisor | 最少样板, 自动生成 handoff |
| 顺序 pipeline | Handoffs | 自然流转 |
| 客服（账单↔技术支持） | Handoffs + recursion_limit | agent 交叉 domain 时切换 |
| 复杂路由 + 并行执行 | 自定义 StateGraph | 完全拓扑控制 |

---

## Pattern 1: Subagents as Tools（推荐）

### 原理

每个专业 agent 包装成一个 LangChain `@tool`。协调者 agent 看到的是 3-5 个"专家工具"，而不是 14 个底层工具。

```
当前（单体, 14 tools）:
┌────────────────────────────────┐
│ 1 个 ReAct agent + 14 个 tools │
│ router/check/pre-flight 补丁    │
└────────────────────────────────┘

改造后（Subagents as Tools）:
┌─────────────────────────────────────┐
│ Coordinator (5 个 sub-agent tools)   │
├──────────┬──────────┬───────────────┤
│ Search   │ Exam     │ Diagnosis     │
│ 3 tools  │ 3 tools  │ 3 tools       │
├──────────┴──────────┴───────────────┤
│ Bank Mgmt (2) │ Report (2)          │
└─────────────────────────────────────┘
```

### 基础用法

```python
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool

model = ChatOpenAI(model="gpt-4o")

# ---------- 1. 定义专业 agent ----------

search_agent = create_react_agent(
    model=model,
    tools=[search_knowledge, search_exam_bank, list_knowledge],
    name="search_expert",
    prompt="你是知识搜索专家。处理知识点查询和题库搜索。"
)

exam_agent = create_react_agent(
    model=model,
    tools=[generate_questions, save_to_bank, show_exam_workbench],
    name="exam_expert",
    prompt="你是出题专家。处理出题生成、保存和工作台交互。"
)

diagnosis_agent = create_react_agent(
    model=model,
    tools=[analyze_student, show_diagnosis, assign_practice],
    name="diagnosis_expert",
    prompt="你是诊断专家。处理学情分析和自适应练习分配。"
)

# ---------- 2. 包装为 tools ----------

@tool
def ask_search_expert(query: str) -> str:
    """知识点搜索和题库查询。当用户搜索知识点、查找题目时调用。"""
    result = search_agent.invoke(
        {"messages": [{"role": "user", "content": query}]}
    )
    return result["messages"][-1].content

@tool
def ask_exam_expert(query: str) -> str:
    """出题相关操作。当用户要生成考试题、保存题目、打开发卷工作台时调用。"""
    result = exam_agent.invoke(
        {"messages": [{"role": "user", "content": query}]}
    )
    return result["messages"][-1].content

@tool
def ask_diagnosis_expert(query: str) -> str:
    """学情诊断相关。当用户要看诊断报告、分配练习、分析学生弱点时调用。"""
    result = diagnosis_agent.invoke(
        {"messages": [{"role": "user", "content": query}]}
    )
    return result["messages"][-1].content

# ---------- 3. 协调者 ----------

coordinator = create_react_agent(
    model=model,
    tools=[ask_search_expert, ask_exam_expert, ask_diagnosis_expert],
    prompt=(
        "你是 ChemAI 化学助教。"
        "搜索知识点/题库 → ask_search_expert。"
        "出题/保存/工作台 → ask_exam_expert。"
        "诊断/练习/学情 → ask_diagnosis_expert。"
    ),
)
```

---

## Pattern 2: langgraph-supervisor（原型备选）

### 安装与用法

```bash
pip install langgraph-supervisor langchain-openai
# Python >= 3.10
```

```python
from langgraph_supervisor import create_supervisor
from langgraph.prebuilt import create_react_agent

# 创建 sub-agents
search_agent = create_react_agent(model=model, tools=[...], name="search_agent")
exam_agent = create_react_agent(model=model, tools=[...], name="exam_agent")
diagnosis_agent = create_react_agent(model=model, tools=[...], name="diagnosis_agent")

# 自动生成 handoff tools
workflow = create_supervisor(
    agents=[search_agent, exam_agent, diagnosis_agent],
    model=model,
    prompt="你是团队主管。根据用户意图路由到正确的专家。",
    output_mode="full_history",  # 或 "last_message"
)

app = workflow.compile()
result = app.invoke({"messages": [{"role": "user", "content": "..."}]})
```

### `create_supervisor` API 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `agents` | `list[CompiledStateGraph]` | 被管理的 sub-agent 列表 |
| `model` | `BaseChatModel` | 主管用的 LLM |
| `prompt` | `str` | 主管 system prompt |
| `output_mode` | `"full_history"` 或 `"last_message"` | 返回模式 |
| `supervisor_name` | `str` | 主管名（默认 "supervisor"） |

### 自定义 Handoff Tools

```python
from langgraph_supervisor import create_handoff_tool

custom_handoff = create_handoff_tool(
    agent_name="exam_expert",
    name="switch_to_exam_expert",
    description="当用户需要生成考试题、保存题库时使用",
    # 自定义传递给目标 agent 的数据
)

workflow = create_supervisor(
    agents=[search_agent, exam_agent],
    model=model,
    tools=[custom_handoff],  # 替代自动生成的 transfer_to_exam_expert
)
```

### 多层级 Supervisor

```python
# 可以嵌套 supervisor
research_team = create_supervisor(
    [search_agent, math_agent], model=model,
    supervisor_name="research_supervisor"
).compile()

writing_team = create_supervisor(
    [write_agent, publish_agent], model=model,
    supervisor_name="writing_supervisor"
).compile()

top_level = create_supervisor(
    [research_team, writing_team], model=model,
    supervisor_name="top_level"
).compile()
```

---

## 生产环境关键问题

### 1. 上下文黑洞

每个 sub-agent 的输出都累积在协调者上下文里。5-6 轮后 token 窗口满了。

**解决方案：**
- 强制摘要 sub-agent 输出，丢弃中间的 reasoning chain
- Sub-agent 返回时只保留最后一条消息
- 设置 `output_mode="last_message"`（仅 supervisor 模式）

### 2. 无限路由循环

Supervisor 在 "查询 → 出题 → 查询 → 出题" 之间振荡。

**解决方案：**
```python
result = app.invoke(
    {"messages": [...]},
    config={
        "recursion_limit": 15,  # 硬上限
        "configurable": {"thread_id": "conv-123"}
    }
)
```

ChemAI 已有的 `recursion_limit=8` 可以直接复用。

### 3. 状态设计五域模型

生产 State 应覆盖：

| 域 | 内容 |
|----|------|
| **对话状态** | 消息历史、计划、摘要 |
| **业务状态** | 任务 ID、租户、优先级、SLA |
| **执行状态** | 当前节点、重试次数、耗时 |
| **治理状态** | 风险等级、人工确认标记、审计标记 |
| **恢复状态** | 检查点、幂等键、回放位置 |

### 4. 持久化检查点

```python
from langgraph.checkpoint.postgres import PostgresSaver

with PostgresSaver.from_conn_string("postgresql://...") as cp:
    app = workflow.compile(checkpointer=cp)
```

`MemorySaver` 在重启后丢失状态——生产环境用 `PostgresSaver` 或 `RedisSaver`。

### 5. MCP 工具解耦

不把工具硬编码到 agent 里，而是通过 MCP server 提供：
```python
from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient({
    "search": {"url": "http://localhost:9000/sse"},
    "exam": {"url": "http://localhost:9001/sse"},
})
tools = client.get_tools()
```

更新工具实现不需要重新部署 agent。

---

## ChemAI 改造路线图

### 工具分组方案

当前 14 个工具，按 domain 分组：

| Sub-Agent | 工具 | 数量 |
|-----------|------|------|
| **search_expert** | `search_knowledge`, `search_exam_bank`, `list_knowledge` | 3 |
| **exam_expert** | `generate_questions`, `save_to_bank`, `show_exam_workbench` | 3 |
| **diagnosis_expert** | `analyze_student`, `show_diagnosis`, `assign_adaptive_practice` | 3 |
| **bank_manager** | `list_banks`, `delete_bank` | 2 |
| **report_expert** | `import_exam_paper`, `request_approval` | 2 |

Coordinator 只有 5 个工具（每个 sub-agent 一个）。加上 `GuardState` 和 `recursion_limit=8`。

### 实现步骤

1. **定义 sub-agent prompts** — 精确描述每个 agent 的职责边界
2. **创建 sub-agent 实例** — 用 `create_react_agent(model, tools, name, prompt)`
3. **包装为 @tool** — 每个 sub-agent 一个 wrapper 函数
4. **创建 coordinator** — `create_react_agent(model, sub_agent_tools, coordinator_prompt)`
5. **集成现有 GuardState** — `seen_calls`、`requires_approval`、`_route` 剥离
6. **更新 SSE 适配器** — `langgraph_sse.py` 确保 sub-agent 的 `_component` 事件能传递到前端
7. **更新 eval 测试** — `test_langgraph_agent.py` 新增 supervisor 行为场景
8. **回归测试** — 确保 5 个 workflow 场景通过

### 需要调研的细节

- [ ] `create_react_agent` 的 `name` 参数在新版 LangGraph 中的行为
- [ ] Sub-agent 的 stream 模式如何在 coordinator 的 astream_events 中体现
- [ ] GuardState `requires_approval` 如何在 sub-agent 调用链中生效
- [ ] `_component` SSE 事件从 sub-agent → coordinator → 前端的传递路径
- [ ] 是否可以利用 2026 年新增的 `subagent_name` 参数做可观测性

---

## 关键链接

- [langgraph-supervisor PyPI](https://pypi.org/project/langgraph-supervisor/)
- [langgraph-supervisor-py GitHub](https://github.com/langchain-ai/langgraph-supervisor-py)
- [LangGraph Multi-Agent Tutorial (官方)](https://langchain-ai.github.io/langgraph/tutorials/multi_agent/agent_supervisor/)
- [3 Multi-Agent Patterns (dev.to)](https://dev.to/klement_gunndu/build-your-first-multi-agent-system-in-python-3-patterns-that-scale-3o7o)
- [LangGraph Supervisor 深度解析 (CSDN)](https://blog.csdn.net/Ring7852/article/details/161750831)
- [Production Agent Design Patterns 2026](https://www.youngju.dev/blog/culture/2026-05-14-production-agent-design-patterns-2026-supervisor-codeact-plan-execute-self-rag-handoff-deep-dive.en)
- [LangGraph + MCP: Build a Supervisor Multi-Agent System](https://dev.to/jangwook_kim_e31e7291ad98/langgraph-mcp-build-a-supervisor-multi-agent-system-25jg)

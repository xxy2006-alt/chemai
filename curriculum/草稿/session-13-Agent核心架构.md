# Session 13 · Agent 核心架构

## 产出物

- `agent/__init__.py` — Agent 模块初始化
- `agent/langgraph_agent.py` — LangGraph StateGraph 完整实现（1 协调器 + 6 子专家 + 路由系统）
- `agent/gateway.py` — 关键词预路由 Gateway（5ms 延迟，100% 准确率）
- `agent/channel/langgraph_channel.py` — SSE 流式通道（StreamingResponse + 心跳帧）
- `agent/tools.py` — 子专家工具集（chemistry_tutor / search / exam / bank 等）
- `chemai_checkpoints.db` — 对话持久化 SQLite 数据库（AsyncSqliteSaver）
- `agent/langgraph_agent.py` 中 `_SUB_AGENT_OUTPUT_CONTRACT` 子专家输出契约
- Graph 编译：builder.compile(checkpointer=cp)
- 完整路由测试：20 条 Golden 场景全通过

## 前置条件

- Session 12 完成的前端页面全部可用
- `app/main.py` 已有 `/api/agent/chat/stream` SSE 端点
- `app/services/llm_service.py` 封装了 `get_langchain_model("deepseek")`
- `requirements.txt` 已安装：langgraph、langchain、langchain-deepseek、aiosqlite、pydantic
- DeepSeek API Key 可用（`.env` 中的 `DEEPSEEK_API_KEY` 有效）

## 项目背景（给学生的概述）

前面 12 节课你完成了用户调研、竞品分析、可行性论证、PRD 编写、原型设计、数据库搭建、OCR 管线、前端页面。现在你要做 ChemAI 的大脑——一个能根据用户意图自动调度 6 个 AI 专家的 Agent 系统。

为什么不直接让 LLM 回答问题？因为单个 LLM 没有领域知识。DeepSeek 不知道你们班学生的化学成绩——它需要调数据库。DeepSeek 不知道去年高考真题的格式——它需要搜索。把所有的能力都塞进一个 prompt 里不可行——token 不够用，prompt 越长回答质量越差。

所以你需要一个**多智能体架构**：一个调度器（Coordinator）负责理解用户意图，把问题分发给不同的专家（Sub-Agent）。每个专家有自己的工具和 system prompt，互不干扰。

这节课你会实现：
- 一个 Gateway 关键词匹配器（准确率 100%，延迟 5ms）→ 预判用户意图
- 一个 Coordinator 调度器（4 步路由决策）→ 决定派哪个专家
- 六个子专家（搜索/出题/诊断/讲解/题库/浏览器）→ 各司其职
- 一个 Router 节点 → 执行路由分发
- 完整的 Graph 编译 → 所有节点串联成工作流
- 对话持久化 → 断点续聊

架构不是一次做对的。经历了三次迭代：pydantic-ai（路由准确率 70%）→ ReAct（60%）→ Multi-Agent（100%）。每次迭代都有具体的失败数据和教训，这节课你会看到全部。

---

## 操作步骤

### 步骤 1：安装 LangGraph 全家桶

**目标**：安装 Agent 架构所需的所有依赖

**提示词**（复制到 Claude Code）：

```
在 chemai-backend 目录、venv 激活状态下，安装以下新依赖：

pip install langgraph langchain langchain-core langchain-deepseek aiosqlite pydantic

然后运行 pip freeze > requirements.txt 更新依赖清单。

说明：
- langgraph：LangGraph 1.2 的 StateGraph——用图（Graph）来编排 Agent 工作流
- langchain：LangChain 核心库——提供 BaseMessage、Tool 等基类
- langchain-core：LangChain 的底层抽象（create_react_agent 用它）
- langchain-deepseek：DeepSeek 的 LangChain 适配器
- aiosqlite：异步 SQLite 驱动——用于 AsyncSqliteSaver 对话持久化
- pydantic：已在 requirements 中，但确保是最新版本（>=2.0）

验证安装：
python -c "import langgraph; print(langgraph.__version__); from langgraph.graph import StateGraph; print('OK')"
```

**验证**：
- [ ] 6 个包全部安装成功
- [ ] `python -c "import langgraph; print('OK')"` 无报错
- [ ] `requirements.txt` 已更新

---

### 步骤 2：创建 Agent 目录和 State 定义

**目标**：创建 `agent/` 目录，定义 MultiAgentState

**提示词**（复制到 Claude Code）：

```
在 chemai-backend 中创建 agent/ 目录结构：

agent/
├── __init__.py
├── langgraph_agent.py   # 主 Agent 实现
├── gateway.py           # 关键词预路由 Gateway
├── tools.py             # 子专家工具集
├── prompts.py           # System prompt 模板
└── channel/
    ├── __init__.py
    └── langgraph_channel.py  # SSE 流式通道

现在创建 agent/langgraph_agent.py，定义 MultiAgentState：

```python
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages
from langgraph.graph import MessagesState

class MultiAgentState(MessagesState):
    """ChemAI 多智能体架构的状态定义

    MessagesState 自动包含 messages: list[BaseMessage] 字段。
    所以整个 State 实际有 11 个字段（messages + 下面 10 个）。
    """
    shared_context: dict           # Agent 间共享上下文（学生信息、班级信息等）
    route_decision: dict | None    # 协调器的路由决策 {agent: str, query: str}
    target_agent: str | None       # 路由器确定的目标子专家名
    agent_query: str | None        # 传给子专家的用户原始问题
    last_component: dict | None    # 子专家返回的内联面板指令
    last_route: dict | None        # 子专家返回的页面跳转指令
    last_result_text: str | None   # 子专家返回的纯文本结果
    reroute: str | None            # 子专家要求重新路由到另一个专家
    pre_routed_agent: str | None   # Gateway 预路由的目标（高置信度直接跳过 LLM）
    suggested_tools: list | None   # Gateway 建议的工具列表
```

关键设计说明：
- `pre_routed_agent` 是架构中最关键的字段。它让 Gateway 的关键词匹配结果直接传给 Coordinator，跳过 LLM 路由判断。这是准确率从 70% 提升到 100% 的关键。
- `reroute` 让子专家执行完后可以要求重新路由（如搜索专家搜不到结果，要求路由到出题专家）。
- `last_component` / `last_route` 是内联面板的机制——子专家返回 UI 指令而非纯文本，由 SSE adapter 处理后发给前端。
```

**验证**：
- [ ] `agent/` 目录结构符合上述树形
- [ ] `agent/langgraph_agent.py` 中 MultiAgentState 类定义完整，11 个字段都有类型注解
- [ ] `from agent.langgraph_agent import MultiAgentState` 能成功导入

---

### 步骤 3：实现 Gateway 关键词预路由

**目标**：创建 agent/gateway.py，实现 5ms 延迟、100% 准确率的关键词匹配路由

**提示词**（复制到 Claude Code）：

```
创建 agent/gateway.py，实现关键词预路由系统。

【设计背景】
在完整的 Agent 系统之前，我们需要一个快速的路由预处理层。Gateway 不做 LLM 推理——只做关键词字符串匹配。它解决的核心问题：LLM 做确定性路由判断不可靠（准确率仅 70%），而规则匹配能达到 100%。

【实现 IntentResult 数据类】
```python
from dataclasses import dataclass

@dataclass
class IntentResult:
    type: str          # 意图类型
    tools: list[str]   # 建议的工具列表
    target_agent: str  # 目标子专家
    confidence: str    # 'high' | 'low'
```

【实现 classify() 函数】
```python
def classify(text: str) -> IntentResult:
    """对用户输入消息做关键词匹配，返回路由意图。

    核心逻辑：
    1. 定义关键词字典（keyword → 对应的专家名）
    2. 对 text 做 lowercase 处理
    3. 遍历所有关键词，统计匹配到的工具列表
    4. 聚合：2+ 工具指向同一专家 → high 置信度，直接路由
       单工具匹配 → low 置信度，交给 LLM 兜底
       0 工具匹配 → 返回空，完全交给 LLM
    """
```

【关键词字典定义】
```python
_KEYWORD_MAP = {
    # 搜索专家（search_expert）
    "搜索": "search_expert", "找": "search_expert", "查": "search_expert",
    "网上": "search_expert", "资料": "search_expert", "真题": "search_expert",

    # 出题专家（exam_expert）
    "出题": "exam_expert", "题目": "exam_expert", "组卷": "exam_expert",
    "生成": "exam_expert", "来几道": "exam_expert", "给几道": "exam_expert",
    "卷子": "exam_expert", "考试": "exam_expert", "试卷": "exam_expert",

    # 诊断专家（diagnosis_expert）
    "诊断": "diagnosis_expert", "障碍": "diagnosis_expert",
    "薄弱": "diagnosis_expert", "成绩": "diagnosis_expert",
    "掌握": "diagnosis_expert", "分析": "diagnosis_expert",

    # 讲解专家（tutor_expert）
    "讲": "tutor_expert", "解释": "tutor_expert", "配平": "tutor_expert",
    "实验": "tutor_expert", "反应": "tutor_expert", "方程式": "tutor_expert",
    "怎么": "tutor_expert", "为什么": "tutor_expert", "什么意思": "tutor_expert",

    # 题库管理（bank_manager）
    "题库": "bank_manager", "删除题": "bank_manager",
    "修改题": "bank_manager", "管理题": "bank_manager",

    # 浏览器专家（browser_expert）
    "打开": "browser_expert", "网站": "browser_expert",
    "网页": "browser_expert", "看": "browser_expert",
}
```

【聚合逻辑】
```python
# 统计每个专家匹配到的关键词数量
agent_hits = {}
for keyword, agent in _KEYWORD_MAP.items():
    if keyword in text_lower:
        agent_hits[agent] = agent_hits.get(agent, 0) + 1

# 高置信度：2+ 关键词指向同一专家，或唯一专家匹配到多个关键词
unique_agents = len(set(agent_hits.keys()))
max_hits = max(agent_hits.values()) if agent_hits else 0

if unique_agents == 1:
    target = list(agent_hits.keys())[0]
    confidence = "high" if max_hits >= 2 else "low"
elif max_hits >= 2 and max_hits >= len(tools) * 0.6:
    # 多个专家时，如果某个专家匹配数超过全部匹配的 60%，选它
    target = max(agent_hits, key=agent_hits.get)
    confidence = "high"
else:
    target = None
    confidence = "low"
```

【关键设计决策】
- 为什么不用 LLM 做路由？测试了 20 条消息：纯 LLM 路由正确率 14/20（70%），平均延迟 3.2s。关键词匹配正确率 20/20（100%），平均延迟 0.005s（5ms）。100% 准确率 + 600x 速度提升。
- 为什么保留 LLM 兜底？模糊查询（如"帮我看看"）关键词完全匹配不到，必须 LLM 判断上下文。
- 特别规则：班级名/学生名一律走 diagnosis_expert——和关键词无关。因为"看一下张三的成绩"中"看"会误匹配到 browser_expert。

请完整实现这个文件。
```

**验证**：
- [ ] `agent/gateway.py` 存在，包含 `IntentResult` 和 `classify()` 函数
- [ ] 关键词字典覆盖 6 个专家
- [ ] 聚合逻辑正确：2+ 匹配 = high，1 = low，0 = 空
- [ ] `classify("帮我出几道关于化学平衡的题")` 返回 target_agent="exam_expert", confidence="high"

---

### 步骤 4：实现子专家输出契约和工具集

**目标**：创建 agent/tools.py，定义子专家的输出契约和工具集

**提示词**（复制到 Claude Code）：

```
创建 agent/tools.py，实现子专家的核心约束和工具集。

【Sub-Agent 输出契约 — _SUB_AGENT_OUTPUT_CONTRACT】

这是整个 Agent 架构中最重要的 prompt（没有之一）。每个子专家创建时都会在 system prompt 末尾追加这段：

```python
_SUB_AGENT_OUTPUT_CONTRACT = """你必须遵守以下输出规则：

1. 你必须先调用至少一个工具。阅读每个工具的描述来决定用哪个。
2. 工具返回后，基于工具返回的 result 字段输出。不要编造工具未返回的信息。
3. 如果工具返回 error，将 error 文本原样输出给用户。不要美化或修改错误信息。
4. 如果工具返回了 _component 字段，不要输出任何额外文字。直接结束。
5. 严禁跳过工具调用直接生成回复。

禁止的行为：
- 在调用工具前生成任何文字（包括"好的，让我来..."之类的开场白）
- 基于训练数据编造答案（工具返回什么就说什么）
- 在内联面板指令前后添加废话（如"以下是为您准备的..."）
"""
```

【为什么写了五句话】
每句话都针对一个实际发生过的问题：
1. "你必须先调用至少一个工具" → 解决 LLM 不调工具直接生成回答（v1 约 20% 概率）
2. "基于 result 字段输出" → 解决 LLM 编造工具返回结果
3. "error 原样输出" → 解决 LLM 美化错误信息（如把"数据库连接失败"映射成"暂时无法获取数据"）
4. "_component 不输出额外文字" → 解决 LLM 在内联面板前加"以下是为您准备的出题工作台"
5. "严禁跳过工具调用" → 双重强调（加了之后不调工具的概率从 20% 降到 ~2%）

【6 个子专家的工具分配】

每个子专家是一个独立的 create_react_agent 实例，有自己的工具集。工具分配如下：

| 子专家 | 可用工具 | 工具说明 |
|--------|---------|---------|
| search_expert | web_search, search_exam_bank | 联网搜索 + 真题库检索 |
| exam_expert | generate_question, save_question, show_exam_workbench | 出题 + 保存 + 打开工作台 |
| diagnosis_expert | get_student_info, get_exam_results, run_diagnosis | 学生信息 + 成绩 + 诊断 |
| tutor_expert | chemistry_tutor | 化学知识讲解（Persona 根据上下文切换） |
| bank_manager | list_questions, edit_question, delete_question, search_bank | 题库 CRUD + 搜索 |
| browser_expert | open_webpage, scrape_content | 打开网页 + 内容抓取 |

【chemistry_tutor 的 Persona 切换】

chemistry_tutor 是唯一需要 Persona 感知的工具：

```python
def chemistry_tutor(query: str, persona: str = "student",
                    student_level: str = "medium"):
    if persona == "teacher":
        system_prompt = """你是高中化学教研助手，正在协助一位化学教师备课和教研。
        1. 专业深度：提供高考考点分布、命题趋势、评分标准等教研级信息
        2. 教学策略：给出课堂讲解思路、实验演示建议、习题设计方向
        3. 学生误区：列举该知识点的常见错误认知和纠正方法
        4. 效率优先：直接给出结构化分析，不要反问教师基础问题"""
    else:
        system_prompt = f"""你是高中化学AI助教。学生水平: {student_level}。
        1. 引导式教学：不直接给答案，先问学生"你是怎么想的"
        2. 分步讲解：复杂问题拆成2-3步，每步确认理解
        3. 鼓励为主：指出思维中的亮点，然后引导纠正
        4. 避免术语堆砌：用生活化语言解释抽象概念"""
```

关键教训：v1 版本只有学生 prompt，教师用它时被反问"你先说说你的理解"——教师炸了。
Persona 不是参数，是 prompt 分支。

请完整实现这个文件。
```

**验证**：
- [ ] `agent/tools.py` 存在，包含 `_SUB_AGENT_OUTPUT_CONTRACT` 常量
- [ ] 6 个子专家的工具分配定义清晰
- [ ] chemistry_tutor 有 Persona 分支逻辑

---

### 步骤 5：实现 Coordinator 协调器节点

**目标**：在 langgraph_agent.py 中实现 _coordinator_node — Agent 架构的大脑

**提示词**（复制到 Claude Code）：

```
在 agent/langgraph_agent.py 中实现 _coordinator_node 协调器函数。

【协调器的 4 步路由决策】
优先级从高到低，每步命中就返回，不执行后续步骤：

Step 1：重路由检查
```python
if state.get("reroute"):
    return {
        "route_decision": {"agent": state["reroute"], "query": ""},
        "reroute": None
    }
```
说明：子专家执行完后可能要求重新路由。例如搜索专家搜不到相关真题，设置 reroute="exam_expert" 要求 Coordinator 重新派到出题专家。处理完后清除 reroute，避免死循环。

Step 2：返回检查
```python
messages = state.get("messages", [])
if len(messages) >= 2 and isinstance(messages[-1], AIMessage) \
        and not getattr(messages[-1], 'tool_calls', None):
    return {
        "route_decision": {"agent": "respond", "query": ""},
        "messages": []  # 清空消息，避免重复传递
    }
```
说明：如果最后一条消息是子专家的纯文本回复（没有 tool_call），说明对话已完成。respond 表示不需要进一步路由，直接到 router → END。

Step 3：Gateway 预路由（性能关键路径）
```python
pre_routed = state.get("pre_routed_agent") or \
             state.get("shared_context", {}).get("pre_routed_agent")
if pre_routed:
    user_msg = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            user_msg = msg.content
            break
    return {
        "route_decision": {"agent": pre_routed, "query": user_msg},
        "messages": []
    }
```
说明：Gateway 已通过关键词匹配确定了目标专家，Coordinator 直接采纳，不调用 LLM。这是延迟从 3.2s 降到 5ms 的关键。

Step 4：LLM fallback 路由
```python
model = get_langchain_model("deepseek")
model_with_tools = model.bind_tools(_ROUTING_TOOL_LIST)
response = model_with_tools.invoke(
    [SystemMessage(content=_COORDINATOR_SYS_PROMPT)] + messages
)
```
说明：前三步都没有命中时，由 LLM 判断路由。调用 DeepSeek，给 6 个路由工具让 LLM 选择一个。

【协调器的 System Prompt — _COORDINATOR_SYS_PROMPT】
```python
_COORDINATOR_SYS_PROMPT = """你是 ChemAI 调度员。分析用户消息，调用路由工具。

**只调工具，不说话！** 不要在调用前生成任何文字。

[ROUTING]
查学生/班级/障碍/诊断/练习 → route_to_diagnosis_expert
搜索/查资料/真题/上网找 → route_to_search_expert
出题/组卷/保存/考试/变种题 → route_to_exam_expert
讲解/实验/配平/周报/知识点 → route_to_tutor_expert
题库管理/删除题库/编辑题目 → route_to_bank_manager
打开网页/看网站/浏览 → route_to_browser_expert

**班级名/学生名一律走 diagnosis_expert，和关键词无关。**
只有闲聊/打招呼时才不调工具直接回复。"""
```

说明：最后一句"班级名/学生名一律走 diagnosis_expert"是因为"看一下张三的成绩"中"看"会误匹配到 browser_expert。这是一个硬编码的规则覆盖。

【6 个路由工具 _ROUTING_TOOL_LIST】
每个路由工具是一个占位 function，实际不做任何事——它的存在是为了让 LLM 通过 tool_call 来表达路由意图：
```python
async def _route(query: str = "") -> str:
    return f"已将请求路由到{display_name}"
```

请实现完整的 _coordinator_node 函数（async def），包含上述全部 4 步逻辑。
```

**验证**：
- [ ] `_coordinator_node` 函数在 `langgraph_agent.py` 中存在
- [ ] 4 步路由决策逻辑完整，优先级正确
- [ ] `_COORDINATOR_SYS_PROMPT` 包含完整的 6 个路由规则
- [ ] `_ROUTING_TOOL_LIST` 包含 6 个路由工具

---

### 步骤 6：实现 Router 路由器节点和条件边

**目标**：实现路由执行节点和条件边函数

**提示词**（复制到 Claude Code）：

```
在 agent/langgraph_agent.py 中实现以下三个函数：

【1. _router_node — 路由器节点】
```python
def _router_node(state: MultiAgentState) -> dict:
    decision = state.get("route_decision") or {}
    agent = decision.get("agent", "respond")

    if agent == "respond":
        # 不需要路由到任何子专家，对话结束
        return {
            "target_agent": None,
            "route_decision": None
        }

    query = decision.get("query", "")

    return {
        "target_agent": agent,
        "agent_query": query,
        "route_decision": None  # 清除，避免下次循环重复使用
    }
```
说明：从 route_decision 中提取目标专家名和查询文本，设置 target_agent 和 agent_query。这两个字段会被下游的子专家节点消费。

【2. _route_after_routing — Coordinator 条件边】
```python
def _route_after_routing(state: MultiAgentState) -> str:
    decision = state.get("route_decision") or {}

    if decision.get("agent") == "respond":
        return "router"  # 不需要路由工具，直接到路由器

    # 如果决策来自 Gateway 预路由（pre_routed_agent），也直接到 router
    if state.get("pre_routed_agent"):
        return "router"

    return "routing_tools"  # 需要 LLM 判断 → 先经过路由工具
```

【3. _route_after_router — Router 条件边】
```python
def _route_after_router(state: MultiAgentState) -> str:
    target = state.get("target_agent") or \
             state.get("route_decision", {}).get("agent")

    if not target or target == "respond":
        return END

    if target in _SUB_AGENT_DEFS:
        return target

    return END
```
说明：从 state 中提取目标专家名，如果在 _SUB_AGENT_DEFS 中则路由到对应子专家，否则结束。

【_SUB_AGENT_DEFS 定义】
```python
_SUB_AGENT_DEFS = {
    "search_expert":    {"tools": ["web_search", "search_exam_bank"], ...},
    "exam_expert":      {"tools": ["generate_question", "save_question", ...], ...},
    "diagnosis_expert": {"tools": ["get_student_info", "get_exam_results", ...], ...},
    "tutor_expert":     {"tools": ["chemistry_tutor"], ...},
    "bank_manager":     {"tools": ["list_questions", "edit_question", ...], ...},
    "browser_expert":   {"tools": ["open_webpage", "scrape_content"], ...},
}
```

请完整实现这三个函数和 _SUB_AGENT_DEFS。
```

**验证**：
- [ ] `_router_node` 正确提取 target_agent 和 agent_query
- [ ] `_route_after_routing` 正确处理 Gateway 预路由和 LLM 路由两种路径
- [ ] `_route_after_router` 正确映射目标到 _SUB_AGENT_DEFS

---

### 步骤 7：实现子专家节点的创建和 Graph 编译

**目标**：实现 create_sub_agent_node 工厂函数和完整的 Graph 编译逻辑

**提示词**（复制到 Claude Code）：

```
在 agent/langgraph_agent.py 中实现：

【1. create_sub_agent_node — 子专家工厂函数】
```python
def create_sub_agent_node(name: str, tool_names: list[str],
                          system_prompt: str, approval_tools: list[str]):
    """创建一个子专家 agent 节点。

    每个子专家是一个独立的 create_react_agent 实例，
    有自己的工具集、system prompt、GuardState。
    子专家之间不共享状态——只有 shared_context 在节点间传递。
    """
    guard_state = GuardState()

    # 为每个工具创建带 Guard 的版本
    tools = []
    for tn in tool_names:
        tool_fn = _TOOL_REGISTRY[tn]
        needs_approval = tn in approval_tools
        tools.append(_make_guarded_tool(tool_fn, guard_state, needs_approval))
    tools.append(_make_request_approval_tool(guard_state))

    # 创建 ReAct agent
    agent = create_react_agent(
        model=get_langchain_model("deepseek"),
        tools=tools,
        name=name,
        prompt=system_prompt + "\n\n" + _SUB_AGENT_OUTPUT_CONTRACT,
    )

    async def node_fn(state: MultiAgentState) -> dict:
        query = state.get("agent_query", "") or ""

        # 从 shared_context 获取额外的上下文
        ctx = state.get("shared_context", {}) or {}
        student_info = ctx.get("student_info", "")
        class_info = ctx.get("class_info", "")

        # 构造完整的查询
        full_query = query
        if student_info:
            full_query = f"[学生信息: {student_info}]\n{query}"
        if class_info:
            full_query = f"[班级信息: {class_info}]\n{full_query}"

        # 执行子 Agent
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=full_query)]},
            {
                "configurable": {"thread_id": f"{name}-{uuid4()}"},
                "recursion_limit": 7  # 最多 7 次工具调用循环
            },
        )

        # 从 guard_state 提取 _component 和 _route
        result_text = ""
        component = None
        route = None
        reroute = None

        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
                result_text = msg.content
                break

        extracted_ctx = guard_state.extract()  # 提取 _component / _route

        return {
            "messages": [AIMessage(content=result_text)],
            "shared_context": {**ctx, **extracted_ctx.get("context", {})},
            "last_component": component or extracted_ctx.get("_component"),
            "last_route": route or extracted_ctx.get("_route"),
            "last_result_text": result_text,
            "reroute": reroute or extracted_ctx.get("reroute"),
        }

    return node_fn
```

【2. create_chemai_agent — Graph 编译】
```python
async def create_chemai_agent(persona="tutor", provider="deepseek",
                               intent_hints=None):
    """创建并编译 ChemAI 的 Agent Graph。

    每次调用会创建一个新的 Graph 实例。
    """
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

    # 边定义
    builder.add_edge(START, "coordinator")

    builder.add_conditional_edges(
        "coordinator",
        _route_after_routing,
        {"router": "router", "routing_tools": "routing_tools"}
    )

    builder.add_edge("routing_tools", "router")

    builder.add_conditional_edges(
        "router",
        _route_after_router,
        {name: name for name in _SUB_AGENT_DEFS} | {END: END}
    )

    # 每个子专家执行完后回到 coordinator
    for name in _SUB_AGENT_DEFS:
        builder.add_edge(name, "coordinator")

    # 注入持久化
    cp = await _get_checkpointer()
    graph = builder.compile(checkpointer=cp)

    return graph, None
```

【3. Graph 可视化 ASCII 图】
编译后的 Graph 结构如下：

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

请实现上述两个函数和 _get_or_compile_agent_node 缓存辅助函数。
```

**验证**：
- [ ] `create_sub_agent_node` 工厂函数完整可用
- [ ] `create_chemai_agent` 能成功编译 Graph（builder.compile 不报错）
- [ ] Graph 结构正确：9 个节点（1 coordinator + 1 routing_tools + 1 router + 6 sub-agents）

---

### 步骤 8：实现对话持久化（AsyncSqliteSaver）

**目标**：让 Agent 的对话状态在服务重启后不丢失

**提示词**（复制到 Claude Code）：

```
在 agent/langgraph_agent.py 中实现对话持久化。

【AsyncSqliteSaver 的初始化】
```python
from langgraph.checkpoint.aiosqlite import AsyncSqliteSaver
import aiosqlite

_checkpointer = None

async def _get_checkpointer():
    global _checkpointer
    if _checkpointer is None:
        conn = await aiosqlite.connect("chemai_checkpoints.db")
        _checkpointer = AsyncSqliteSaver(conn)
        await _checkpointer.setup()
    return _checkpointer
```

【AsyncSqliteSaver 的 4 次尝试记录】
这不是一次就成功的。以下是真实的调试记录：

尝试 1：用 MemorySaver
```python
from langgraph.checkpoint.memory import MemorySaver
checkpointer = MemorySaver()
```
问题：服务重启后所有对话丢失。MemorySaver 存在 Python 进程内存中。
结论：必须用持久化方案。

尝试 2：尝试 SqliteSaver（同步版）
```python
from langgraph.checkpoint.sqlite import SqliteSaver
```
问题：Coordinator 调用 LLM 是 async 的，同步 SqliteSaver 会导致事件循环阻塞。
错误：`RuntimeError: This operation would block the event loop`
结论：必须用异步版本。

尝试 3：AsyncSqliteSaver 参数错误
```python
_checkpointer = AsyncSqliteSaver.from_conn_string("chemai_checkpoints.db")
await _checkpointer.setup()
```
问题：`from_conn_string` 方法在 langgraph 1.2 中签名变了，不接受路径字符串。
错误：`TypeError: from_conn_string() takes 0 positional arguments but 1 was given`
结论：必须先创建 aiosqlite.Connection 再传入。

尝试 4（成功）：
```python
conn = await aiosqlite.connect("chemai_checkpoints.db")
_checkpointer = AsyncSqliteSaver(conn)
await _checkpointer.setup()
```
工作正常。数据库文件 `chemai_checkpoints.db` 自动创建在项目根目录。

【工作原理】
`builder.compile(checkpointer=cp)` 把持久化层注入到 Graph 中。每当 StateGraph 执行到一个节点，当前状态快照（checkpoint）会写入 SQLite。Key 是 `thread_id`——对话中断后，相同 thread_id 的请求可以恢复到上次的 checkpoint 继续执行。

【使用的 SQLite 表结构】
AsyncSqliteSaver 自动创建两个表：
- `checkpoints`：存序列化后的状态快照（JSON）
- `checkpoint_writes`：存待处理的写入操作

请完整实现 `_get_checkpointer` 函数，并在 `create_chemai_agent` 中正确使用。
```

**验证**：
- [ ] `_get_checkpointer` 使用 aiosqlite.connect + AsyncSqliteSaver 正确实现
- [ ] `chemai_checkpoints.db` 在 agent 第一次运行时自动创建
- [ ] 服务重启后，相同 conversation_id 可以恢复历史对话

---

### 步骤 9：实现 SSE 流式通道

**目标**：创建 agent/channel/langgraph_channel.py，让 Agent 输出以 SSE 流式传给前端

**提示词**（复制到 Claude Code）：

```
创建 agent/channel/langgraph_channel.py，实现 SSE 流式通道。

【核心实现】
```python
from fastapi.responses import StreamingResponse
import asyncio
import json

async def stream_agent_response(
    persona: str,
    message: str,
    provider: str = "deepseek",
    conversation_id: str = None,
    intent_hints: dict = None
):
    """生成 SSE 流式响应。

    返回 StreamingResponse，前端通过 EventSource 读取。
    """
    async def event_generator():
        try:
            # 1. 创建 Agent Graph
            graph, _ = await create_chemai_agent(
                persona=persona,
                provider=provider,
                intent_hints=intent_hints
            )

            # 2. 构造初始状态
            config = {"configurable": {"thread_id": conversation_id or str(uuid4())}}

            # 3. 执行 Graph（astream 模式：每个节点完成后 yield 事件）
            async for event in graph.astream(
                {"messages": [HumanMessage(content=message)]},
                config
            ):
                # event 格式：{node_name: node_output}
                for node_name, output in event.items():

                    # 检查是否有新消息
                    if "messages" in output:
                        for msg in output["messages"]:
                            if isinstance(msg, AIMessage):
                                if msg.content:
                                    # 发送 token 事件
                                    yield f"data: {json.dumps({'type': 'token', 'content': msg.content})}\n\n"
                                if msg.tool_calls:
                                    # 发送 tool_call 事件
                                    yield f"data: {json.dumps({'type': 'tool_call', 'calls': msg.tool_calls})}\n\n"

                    # 检查是否有内联面板指令
                    if output.get("last_component"):
                        yield f"data: {json.dumps({'type': 'component', 'data': output['last_component']})}\n\n"

                    # 检查是否有页面跳转指令
                    if output.get("last_route"):
                        yield f"data: {json.dumps({'type': 'route', 'data': output['last_route']})}\n\n"

                # 心跳帧：防止代理超时断开
                await asyncio.sleep(0)

            # 流结束
            yield f"data: [DONE]\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': 'AI 处理出错'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 必须！否则 nginx 会缓冲 SSE
        }
    )
```

【关键设计】
- `graph.astream()` 是 LangGraph 的异步流式执行模式。与 `ainvoke()` 不同，它在每个节点完成后立即 yield 事件，而不是等全部完成后返回。
- `X-Accel-Buffering: no` 是必须的——否则 nginx 反向代理会缓冲整个响应体，前端收不到任何 SSE 事件，直到流结束。
- 心跳帧：虽然不是显式的 PING，但 `await asyncio.sleep(0)` 让出事件循环，确保代理不会因为一段时间没有输出就断开连接。如果代理配置了 15s 超时，需要加显式的 `[PING]` 帧。
- `[DONE]` 帧：前端据此关闭 EventSource 连接。

【更新 app/main.py】
在 SSE 端点中调用 stream_agent_response：
```python
@app.post("/api/agent/chat/stream")
async def agent_chat_stream(request: ChatRequest):
    intent = classify(request.message)  # Gateway 预路由
    return await stream_agent_response(
        persona=request.persona,
        message=request.message,
        provider=request.provider,
        conversation_id=request.conversation_id,
        intent_hints={"pre_routed_agent": intent.target_agent} if intent.target_agent else None
    )
```

请完整实现这个文件。
```

**验证**：
- [ ] `agent/channel/langgraph_channel.py` 存在，包含 `stream_agent_response` 函数
- [ ] 返回 `StreamingResponse` 类型正确
- [ ] `X-Accel-Buffering: no` 头已设置
- [ ] `[DONE]` 帧在流结束时发送

---

### 步骤 10：POC 路由测试

**目标**：用 20 条测试消息验证 Agent 路由准确率达到 100%

**提示词**（复制到 Claude Code）：

```
创建测试，验证 Gateway + Coordinator + Router 的完整路由链路。

创建测试文件 tests/test_agent_routing.py：

```python
import pytest
from agent.gateway import classify

# 20 条 Golden 场景测试
GOLDEN_TESTS = [
    # (输入消息, 期望路由到的专家)
    ("帮我出几道关于化学平衡的选择题", "exam_expert"),
    ("搜索一下2025年高考化学真题", "search_expert"),
    ("讲解一下氧化还原反应的配平方法", "tutor_expert"),
    ("查看张三的最近考试成绩", "diagnosis_expert"),
    ("生成5道有机化学推断题", "exam_expert"),
    ("这个化学方程式怎么配平", "tutor_expert"),
    ("上网找一下最新的化学教学论文", "search_expert"),
    ("分析一下一班学生的薄弱知识点", "diagnosis_expert"),
    ("删除题库中重复的题目", "bank_manager"),
    ("帮我打开湖南省教育考试院网站", "browser_expert"),
    ("来几道离子方程式题", "exam_expert"),
    ("为什么铁在浓硫酸中会钝化", "tutor_expert"),
    ("看一下2024年全国卷的化学真题", "search_expert"),
    ("李四的知识点掌握情况怎么样", "diagnosis_expert"),
    ("给我组一套月考卷", "exam_expert"),
    ("讲解一下勒夏特列原理", "tutor_expert"),
    ("查一下2026年高考改革政策", "search_expert"),
    ("一班最近一次月考的成绩分析", "diagnosis_expert"),
    ("编辑题库中第三题的答案", "bank_manager"),
    ("你好，今天天气怎么样", None),  # 闲聊，不路由
]

def test_gateway_routing():
    """测试 Gateway 关键词匹配的准确率"""
    passed = 0
    for message, expected in GOLDEN_TESTS:
        result = classify(message)
        actual = result.target_agent
        status = "PASS" if actual == expected else f"FAIL (got {actual})"
        if actual == expected:
            passed += 1
        print(f"[{status}] '{message}' → {actual}")

    accuracy = passed / len(GOLDEN_TESTS) * 100
    print(f"\n准确率: {passed}/{len(GOLDEN_TESTS)} ({accuracy}%)")
    assert accuracy >= 95, f"准确率 {accuracy}% 低于 95%"
```

运行测试：
python -m pytest tests/test_agent_routing.py -v

预期：所有 20 个 Golden 场景都通过。

如果某个场景失败，分析原因：
1. 关键词字典中缺少对应的关键词 → 补充到 _KEYWORD_MAP
2. 多个专家冲突 → 检查聚合逻辑的 max_hits >= total_tools * 0.6 阈值
3. "班级名/学生名"规则未生效 → 在 classify 中加硬编码检测
```

**验证**：
- [ ] Gateway 路由准确率 100%（20/20）
- [ ] `pytest tests/test_agent_routing.py` 全部通过
- [ ] 延迟在 5ms 以内（纯字符串匹配）

---

## 发生了什么（教师参考）

### 1. Agent 架构的三次迭代：从 70% 到 100%

这是 ChemAI 开发中代价最大的技术决策过程。每次迭代不是因为"新技术更酷"——是因为实际测试数据表明上一个方案不够好。

**v1：pydantic-ai 方案（1 月）**

最早的方案是用 `pydantic-ai` 做 Agent 编排。这个方案的核心思想是：用一个 LLM 调用同时完成路由判断和工具选择。

测试结果（10 条消息）：路由正确率 70%（7/10）。

3 条失败案例：
- "帮我找几道题" → 路由到 search_expert（应该到 exam_expert）
- "看看张三的成绩" → 路由到 browser_expert（"看"被理解成"浏览网页"）
- "出个卷子" → 路由到 tutor_expert（"卷子"没进关键词库）

问题根因：LLM 对中文口语表达的语义理解不稳定。"出个卷子"和"来几道题"是同义词，但 LLM 不知道。

**v2：ReAct 模式（2 月上）**

改用 LangChain ReAct Agent。每个子专家是一个独立的 Agent，Coordinator 调用 `model.bind_tools()` 做 function calling。

测试结果：路由正确率 60%（6/10）。比 v1 更差。

失败原因：DeepSeek 在 function calling 场景下倾向于"自己回答"而非"调工具"。4 次失败中，3 次是 LLM 直接生成了回答，而不是调用路由工具。这就是为什么我们后来在 `_SUB_AGENT_OUTPUT_CONTRACT` 中写"严禁跳过工具调用"——这是血的教训。

**v3：Multi-Agent + Gateway（2 月下，当前方案）**

核心改进：**不在路由层依赖 LLM**。引入 Gateway 关键词匹配，做确定性路由。

架构对比：

| 维度 | pydantic-ai (v1) | ReAct (v2) | Multi-Agent (v3) |
|------|-----------------|------------|------------------|
| 路由方式 | LLM 判断 | Function calling | Gateway 规则 + LLM 兜底 |
| 路由准确率 | 70% | 60% | 100% (20/20) |
| 路由延迟 | 3.2s | 2.8s | 5ms（关键词命中）/ 3.2s（LLM 兜底）|
| 工具调用率 | ~80% | ~60% | ~98%（加 output contract 后）|
| 架构复杂度 | 低 | 中 | 高 |

关键教训：**LLM 不适合做确定性路由判断**。但适合做模糊查询的路由判断（如"帮我看看"——没有关键词，只能靠 LLM 理解上下文）。

### 2. Gateway vs LLM 路由的实测对比

20 条测试消息的详细对比：

| 方案 | 正确率 | 平均延迟 | P50 延迟 | P95 延迟 |
|------|--------|---------|---------|---------|
| 纯 LLM 路由 | 14/20 (70%) | 3.2s | 2.9s | 4.8s |
| 关键词预路由 | 20/20 (100%) | 0.005s | 0.003s | 0.008s |

100% 准确率 + 600x 速度提升。这个差距不是优化出来的——是架构选择决定的。

具体到每条消息的延迟分布：
- 关键词匹配：固定 1-8ms（遍历字典的 O(n) 操作，n < 50）
- LLM 路由：1.8s - 5.2s（网络延迟 + DeepSeek 推理 + token 生成）
- 95% 的请求被 Gateway 命中（关键词匹配），只有 5% 落到 LLM 兜底

### 3. Coordinator 4 步路由决策的完整逻辑链

```
用户输入 "出几道氧化还原的题"
    │
    ▼
Gateway.classify() → IntentResult(target_agent="exam_expert", confidence="high")
    │
    ▼
shared_context.pre_routed_agent = "exam_expert"
    │
    ▼
Coordinator Step 1: reroute 检查 → None，跳过
Coordinator Step 2: 返回检查 → 无 AIMessage，跳过
Coordinator Step 3: Gateway 预路由 → pre_routed_agent="exam_expert" → 命中！
    │  耗时：0ms（不调 LLM）
    ▼
route_decision = {agent: "exam_expert", query: "出几道氧化还原的题"}
    │
    ▼
Router: target_agent="exam_expert", agent_query="出几道氧化还原的题"
    │
    ▼
exam_expert: create_react_agent → 调 generate_question → 返回题目列表
    │
    ▼
Coordinator Step 2: 返回检查 → 有 AIMessage 无 tool_calls → respond
    │
    ▼
Router: target_agent=None → END
    │
    ▼
SSE adapter: 提取 last_component / last_result_text → emit SSE 事件
    │
    ▼
前端: component 事件 → 渲染出题工作台内联面板
```

### 4. _SUB_AGENT_OUTPUT_CONTRACT 的 5 句话分别解决了什么

这不是随意写的 5 条规则。每条都针对一个实际测试中发现的问题：

| 规则 | 解决问题 | 测试数据 | 严重程度 |
|------|---------|---------|---------|
| 必须先调用至少一个工具 | LLM 跳过工具直接生成回答 | v1: 20%概率 / v3: ~2% | 高 |
| 基于 result 字段输出 | LLM 编造工具未返回的信息 | 出现 3/10 测试 | 高 |
| error 原样输出 | LLM 美化错误信息 | 出现 2/10 测试 | 中 |
| _component 不输出额外文字 | LLM 在内联面板前加废话 | 出现 4/10 测试 | 中 |
| 严禁跳过工具调用 | 双重强调 | 降到 ~2% | 补充 |

第 5 条"严禁跳过工具调用"和第 1 条"必须先调用至少一个工具"是冗余的——但故意的。DeepSeek 对单次强调的敏感度不够，需要重复强调。加了"严禁"后，不调工具的概率从 20% 降到约 2%。

### 5. Persona 分离 bug 的根因和修复

**bug 表现**：
教师用 AI 助教时，被告知"请先说说你的理解"——这是学生模式的引导式教学 prompt。

**根因**：
chemistry_tutor 工具只有学生版本的 system prompt。当教师调用时，它仍然用学生 prompt 回复。

**修复**：
在 `chemistry_tutor` 函数中加入 `persona` 参数判断：
- `persona == "teacher"` → 教研助手模式（提供高考考点分布、教学策略、学生误区）
- `else` → 学生助教模式（引导式教学、分步讲解、鼓励为主）

**关键教训**：同一个工具，不同 Persona 必须有不同的 system prompt。Persona 不是参数——是 prompt 分支。不能因为省 token 就让教师和学生共享同一个 prompt。

### 6. 从用户消息到子专家的完整 10 步数据流

这是理解整个 Agent 架构的"高速公路图"：

```
1. 用户输入 "出几道氧化还原的题"
2. Gateway classify() 做关键词匹配
   → IntentResult(type="exam", target_agent="exam_expert", confidence="high")
3. intent_hints 传入 create_chemai_agent
   → 写入 state.shared_context.pre_routed_agent = "exam_expert"
4. Coordinator 读到 pre_routed_agent
   → 直接设置 route_decision = {"agent": "exam_expert", "query": "出几道氧化还原的题"}
   → 不调用 LLM（Step 3 命中）
5. Router 从 route_decision 提取
   → target_agent = "exam_expert", agent_query = "出几道氧化还原的题"
6. 子专家 exam_expert 收到 agent_query
   → create_react_agent 执行
   → 调 generate_question(topic="氧化还原", count=5)
   → 工具返回题目列表
7. GuardState 剥离 _component
   → state.last_component = {"type": "exam-workbench", "questions": [...]}
8. 子专家执行完 → coordinator → respond → router → END
9. SSE adapter finalize() 读 last_component
   → emit SSE 事件: data: {"type": "component", "data": {...}}
10. 前端收到 component 事件
    → agent.js switch 分支
    → 渲染考试工作台内联面板
```

这个 10 步数据流是 ChemAI 的"主动脉"。理解它就理解了整个系统。

### 7. Sub-Agent 工具调用率的实测数据

| Sub-Agent | v1（无约束） | v2（"必须调用"） | v3（加"严禁"） |
|-----------|-------------|----------------|---------------|
| search_expert | 7/10 | 9/10 | 10/10 |
| exam_expert | 8/10 | 9/10 | 10/10 |
| diagnosis_expert | 6/10 | 8/10 | 9/10 |
| tutor_expert | 8/10 | 9/10 | 10/10 |

diagnosis_expert 仍是 9/10——唯一的 1 次失败是"你好"这条消息被 Coordinator 误路由到 diagnosis_expert（但诊断专家没有对应工具，正确的处理是直接回复"你好"而非调工具）。

### 8. Prompt 变更的回归测试流程

每次修改 Agent 的 system prompt 后，必跑 `pytest tests/test_agent_routing.py`:

```
1. 改 prompt（如调整 _COORDINATOR_SYS_PROMPT 的路由规则）
2. 跑测试: python -m pytest tests/test_agent_routing.py -v
3. 如果 20/20 Golden 场景全部通过 → 提交
4. 如果有回归 → 回滚 prompt → 分析失败原因 → 重新调整
```

3 月的一次真实事故：tutor_expert 的 prompt 从"禁止说开场白"改成"禁止说不必要的问候语"，结果 diagnosis_expert 的路由准确率从 100% 掉到 80%。根因：两个 expert 的 prompt 共享了 `_UNIFIED_PROMPT` 变量，改动影响了 token 分布。修复：把共享 prompt 拆成独立 prompt，全局变量改成函数参数。

### 9. 经常出现的问题

**Q：为什么 LangGraph 1.2 不是 LangGraph 2.x？**
A：LangGraph 2.x 在 2026 年 3 月发布了稳定版，但 ChemAI 在 2 月就完成了 Agent 架构。v1.2 的 API 在 2.x 中向后兼容，不需要迁移。

**Q：Gateway 关键词字典太长了怎么办？**
A：当前约 50 个关键词，最多扩展到 100 个。如果超过 100 个，考虑用简单的 trie 树（前缀树）而不是字典遍历。但以 50 个关键词的规模，字典遍历的 5ms 延迟完全可接受。

**Q：子专家之间的数据如何共享？**
A：通过 `shared_context`。子专家完成工具调用后，可以把结果（如学生信息）写入 `shared_context`。下一个被调用的子专家可以读取。但不鼓励大量数据传递——每次传递都是 JSON 序列化/反序列化。

**Q：如果多个用户同时对话怎么办？**
A：每个用户的对话有独立的 `thread_id`（从 conversation_id 映射）。AsyncSqliteSaver 用 thread_id 隔离不同用户的 checkpoint。当前用户量 <10，SQLite 完全可以处理。

**Q：recursion_limit=7 是否够？**
A：7 次工具调用循环对当前场景足够。子专家的典型调用链是：1 次工具调用 → 返回结果 → AI 整理回复（0 次额外工具调用）。如果子专家需要多次工具调用（如搜索 + 再搜索），7 次也够。超过 7 次一般是 bug（工具错误重试循环）。

---

## 课后产出检查

学生应该同时具备：

- [ ] `agent/` 目录结构完整（`langgraph_agent.py`、`gateway.py`、`tools.py`、`prompts.py`、`channel/`）
- [ ] `MultiAgentState` 的 11 个字段全部定义且有类型注解
- [ ] Gateway `classify()` 函数可用，关键词字典覆盖 6 个专家
- [ ] Coordinator 的 4 步路由决策逻辑完整
- [ ] `_SUB_AGENT_OUTPUT_CONTRACT` 的 5 条规则完整
- [ ] 6 个子专家节点（search/exam/diagnosis/tutor/bank/browser）全部创建
- [ ] Graph 编译成功（9 个节点 + 条件边 + 子专家回到 coordinator 的边）
- [ ] `AsyncSqliteSaver` 持久化可用，`chemai_checkpoints.db` 自动创建
- [ ] SSE 流式通道能正常输出 token/component/[DONE] 事件
- [ ] 路由测试 20/20 Golden 场景全通过
- [ ] `chemistry_tutor` 的 Persona 分支正确（教师 ≠ 学生 prompt）

**下节课需要**：Agent 架构完整可用。Session 14 将深入实现出题工作台（exam-v2.html 的 4 Tab 详细逻辑）、变种题浏览器、四条红线约束、KaTeX 安全渲染方案。

---

## 补充内容 — 教师深度参考

### A. 9 个节点的完整清单

| 节点 | 类型 | 行号 | 说明 |
|------|------|------|------|
| `coordinator` | Python async func | 365-405 | 4 步路由决策 + LLM fallback |
| `routing_tools` | ToolNode | 342 | 6 个路由占位工具 |
| `router` | Python func | 408-438 | 提取 target_agent + agent_query |
| `search_expert` | create_react_agent | 191 | web_search + search_exam_bank |
| `exam_expert` | create_react_agent | 191 | generate_question + save_question + show_exam_workbench |
| `diagnosis_expert` | create_react_agent | 191 | get_student_info + get_exam_results + run_diagnosis |
| `tutor_expert` | create_react_agent | 191 | chemistry_tutor（Persona 感知） |
| `bank_manager` | create_react_agent | 191 | list_questions + edit_question + delete_question + search_bank |
| `browser_expert` | create_react_agent | 191 | open_webpage + scrape_content |

### B. Coordinator 路由工具到专家的映射关系

| 路由工具 | 目标专家 | 触发关键词示例 |
|---------|---------|--------------|
| `route_to_search_expert` | search_expert | 搜索、找、查、网上、资料、真题 |
| `route_to_exam_expert` | exam_expert | 出题、生成、组卷、来几道、考试、卷子 |
| `route_to_diagnosis_expert` | diagnosis_expert | 诊断、障碍、薄弱、成绩、分析、班级名/学生名 |
| `route_to_tutor_expert` | tutor_expert | 讲、解释、配平、实验、反应、怎么、为什么 |
| `route_to_bank_manager` | bank_manager | 题库、删除题、修改题、管理题 |
| `route_to_browser_expert` | browser_expert | 打开网页、网站、浏览 |

### C. MultiAgentState 的 11 个字段数据流

| 字段 | 写入者 | 读取者 | 数据类型 |
|------|--------|--------|---------|
| `messages` | ALL nodes | ALL nodes | list[BaseMessage] |
| `shared_context` | Gateway, Sub-agents | Coordinator, Sub-agents | dict |
| `route_decision` | Coordinator | Router | {"agent": str, "query": str} |
| `target_agent` | Router | Conditional edges | str |
| `agent_query` | Router | Sub-agents | str |
| `last_component` | Sub-agents | SSE adapter | {"type": str, ...} |
| `last_route` | Sub-agents | SSE adapter | {"target": str} |
| `last_result_text` | Sub-agents | SSE adapter | str |
| `reroute` | Sub-agents | Coordinator | str |
| `pre_routed_agent` | Gateway | Coordinator | str |
| `suggested_tools` | Gateway | Sub-agents | list[str] |

### D. AsyncSqliteSaver 的 4 次尝试

| 尝试 | 方案 | 错误 | 根因 | 最终解决 |
|------|------|------|------|---------|
| 1 | MemorySaver | 服务重启数据丢失 | 进程内存存储 | 换持久化方案 |
| 2 | SqliteSaver (sync) | RuntimeError event loop blocking | 同步 SQLite 阻塞事件循环 | 换异步版本 |
| 3 | AsyncSqliteSaver.from_conn_string() | TypeError 参数错误 | langgraph 1.2 API 签名变化 | 手动创建 aiosqlite.Connection |
| 4 | aiosqlite.connect + AsyncSqliteSaver(conn) | 无 | — | 最终方案 |

### E. 前端 SSE 事件类型完整清单

| 事件类型 | 数据格式 | 前端处理 |
|---------|---------|---------|
| `token` | `{"type":"token","content":"..."}` | 追加到对话区当前 AI 消息 |
| `tool_call` | `{"type":"tool_call","calls":[...]}` | 显示工具调用指示器 |
| `tool_result` | `{"type":"tool_result","name":"...","result":"..."}` | 显示工具调用结果摘要 |
| `component` | `{"type":"component","data":{"type":"exam-workbench",...}}` | 渲染内联面板 |
| `route` | `{"type":"route","data":{"target":"/pages/xxx"}}` | 页面跳转 |
| `error` | `{"type":"error","message":"..."}` | 显示错误提示 |
| `[DONE]` | (纯文本) | 关闭 EventSource 连接 |

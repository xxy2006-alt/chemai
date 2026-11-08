# LangGraph Agent 迁移 — ReAct + Human-in-the-Loop

> 状态: 重写 | 日期: 2026-06-18

## Why

pydantic-ai 是单轮 tool calling：用户消息 → LLM 选 tool → 执行 → 回复。结束。

真实教学场景需要的是：
- 老师说"帮我准备一份期中考试"
- Agent 自己判断：考试范围没说过？问。出给哪个班？问。题型？问。
- 参数齐了出题。出完自己看一遍。觉得化学方程式配平有问题？自己修。
- 推给老师预览。老师说"第三题太难了换掉"——agent 记下来，下一轮不出这个难度。
- 老师确认了，agent 自己决定题目存哪个文件夹，发布到哪个班。

**每一步是 LLM 自己决定的，不是预设的图说了算。** 这是 ReAct agent，不是 workflow。

## What Changes

### 核心思路

```
pydantic-ai 单轮            →    LangGraph ReAct Agent
─────────────────                ──────────────────────
LLM 调用 1 次                    LLM 自己决定调几次
tool 调用 0-1 次                 可以连续调多个 tool
没有自我纠错                     tool 返回错误？自己重试
没有暂停等人                     interrupt() — LLM 判断需要确认时暂停
固定回复格式                     LLM 自己组织最终回答
```

### 技术选型

LangGraph 的 `create_react_agent` 提供预置的 ReAct loop：
- LLM node（bind tools）→ tool node → 回到 LLM node → 重复直到 LLM 输出最终文本
- `interrupt()` 可嵌入任一步骤，等待外部输入后 `Command(resume=...)` 继续

**不做固定 DAG。** LLM 自主决定执行路径。

### 改动的文件

| 文件 | 改动 |
|------|------|
| `agent/langgraph_agent.py` | **新** — `create_chemai_agent()` 工厂，create_react_agent + interrupt + SSE 流式 |
| `agent/langgraph_channel.py` | **新** — FastAPI 端点，复用 ChatRequest，SSE 流式 + 非流式 |
| `agent/langgraph_sse.py` | **新** — astream_events → ChemAI SSE 事件格式（保留所有现有字段） |
| `agent/tools.py` | **微量** — 工具分类/分组，不改函数签名 |
| `agent/gateway.py` | **不变** — 分类器仍用作 tool 预筛选 |
| `app/main.py` | **1 行** — 注册新路由 |
| `agent/channel/fastapi_sse.py` | **保留** — 旧端点不退，并行运行 |
| `agent/agents.py` | **保留** — pydantic-ai fallback |

### 不改的部分（零改动）

| 组件 | 理由 |
|------|------|
| 前端 `agent.js` / `agent-renderers.js` | SSE 事件格式 100% 保持 |
| 10 个 tool 函数 | 函数签名不变 |
| Persona YAML (3 个) | 系统提示词注入到 ReAct agent 的 system prompt |
| `gateway.py` (IntentClassifier) | 作为 ReAct agent 的 tool 之一（`classify_intent`）或独立预筛选 |
| `models.py` | provider 工厂适配 LangChain ChatOpenAI |
| `deps.py` | 状态值从 LangGraph state 或 tool context 获取 |

## Capabilities

- `react-agent-loop`: LLM 自主决定 tool 调用顺序和次数，多步连续执行
- `llm-driven-interrupt`: LLM 判断操作需要用户确认时调用 interrupt()，不是预设检查点
- `self-correction`: tool 返回错误/异常时 LLM 自行重试或调整参数
- `sse-compat`: SSE 事件格式（phase/tool_call/tool_result/text/navigate/populate/action）完全保持不变
- `gateway-pre-filter`: 保留两段式 tool 筛选（分类器缩小候选集 → LLM 在 ReAct loop 里精判）

## Impact

- **Breaking**: 无。新端点 `/api/agent/chat/langgraph/stream`，旧端点保留
- **Frontend**: 零改动
- **Tool 函数**: 零改动
- **新增依赖**: langgraph 1.2.5 + langchain-core 1.4.7（已安装验证通过）
- **代码量**: 净增 ~400 行（3 个新文件 ~500 行，旧文件微量改动 ~-100 行）

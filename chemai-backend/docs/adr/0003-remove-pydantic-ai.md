# 移除 pydantic-ai 依赖

pydantic-ai 已从代码库移除：`agent/agents.py` 的 Agent 工厂（`ChemAIAgentFactory`/`factory`）、旧 SSE 端点 `/api/agent/chat` 与 `/api/agent/chat/stream`、`agent/models.py`（`get_model`）、`agent/sse_adapter.py`（`SSEAdapter`）一并删除。前端已全部走 LangGraph 端点（`/api/agent/chat/langgraph/*`），旧端点无人调用；且 pydantic-ai 1.107.0 需要 pydantic>=2.9，而项目钉住 pydantic 2.6.1，导入即崩。

**Status**: accepted

**Considered Options**
- 升级 pydantic 到 >=2.9 迁就 pydantic-ai：改动集中在依赖清单，但会保留已废弃的旧 SSE 路径和两套 Agent 体系（pydantic-ai + LangGraph），长期维护成本高。
- 移除 pydantic-ai：删掉废弃路径，统一到 LangGraph v2。**选择此项**。

**Consequences**
- 旧端点 `/api/agent/chat`、`/api/agent/chat/stream`、`/api/agent/chat/reset` 不再存在；前端不调用，无影响。对话列表/历史端点由 `agent/channel/conversation.py` 独立挂载，保留。
- `agent/agents.py` 仅保留 `load_persona()`，供 LangGraph v2 与测试使用。
- `evals/test_agent_routing.py`、`test_gateway_router.py`、`test_sse_streaming.py` 随旧代码一并删除，`evals/run_evals.py` 移除对应 STAGE。
- pydantic 保持 2.6.1 不变。

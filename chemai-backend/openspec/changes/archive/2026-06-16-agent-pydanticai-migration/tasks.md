## Phase 1: 基础设施（1.5h，依赖 agent-pydanticai-validation PASS）✅

- [x] 1.1 创建 `agent/deps.py` — ChemAIDeps dataclass
- [x] 1.2 创建 `agent/models.py` — 4 个 model 工厂
- [x] 1.3 迁移 10 个 skill → `agent/tools.py`
- [x] 1.4 验证：`python -c "from agent.tools import *"` 10 个函数可导入

## Phase 2: Agent 工厂 + SSE 适配（1.5h，依赖 §1）✅

- [x] 2.1 创建 `agent/agents.py` — ChemAIAgentFactory（persona YAML → tool 过滤 → Agent）
- [x] 2.2 创建 `agent/sse_adapter.py` — SSEAdapter + pydantic_stream_to_sse
- [x] 2.3 `fastapi_sse.py` 新增 `POST /api/agent/chat/v2/stream`
- [x] 2.4 验证：curl v2 端点 SSE 输出正常

## Phase 3: 会话持久化（1h，依赖 §2）✅

- [x] 3.1 `memory.py` 加 `to_pydantic_messages()` / `from_pydantic_messages()`
- [x] 3.2 v2 端点 `conversation_id` 存储 message_history
- [ ] 3.3 验证：带 conversation_id 的两轮对话上下文保留

## Phase 4: 清理（0.5h，依赖 §3 全部验证通过）

- [ ] 4.1 删除旧文件：core.py, skill_registry.py, provider/*, skills/*, pydantic_agent.py
- [ ] 4.2 `skills_init.py` 改为 `from agent.tools import TOOLS`
- [ ] 4.3 v2 端点改为 `/api/agent/chat/stream`（替换旧端点）
- [ ] 4.4 全量回归：所有 persona × provider × skill 组合冒烟

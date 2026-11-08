## Phase 0: PoC 修补（30 min，无依赖）

升级 pydantic_agent.py 到 1.107.0 API，解除 agent-pydanticai-poc 的 stream_events 阻塞。

- [x] 0.1 验证 pydantic-ai 1.107.0 DeepSeek 连接：`from pydantic_ai import Agent; Agent('deepseek:deepseek-chat')` 可创建
- [x] 0.2 `stream_to_sse()` 从 `result.stream_text(delta=True)` 改为 `agent.run_stream_events()`
- [x] 0.3 修复 SSE 双重输出 bug（裸 JSON + data: 前缀共存）
- [x] 0.4 升级 `pydantic_event_to_sse()` 适配 1.107.0 事件类型（验证 PartStartEvent/PartDeltaEvent/FunctionToolCallEvent/FunctionToolResultEvent/FinalResultEvent 映射正确）
- [x] 0.5 验证：curl search_exam_bank 请求 → SSE 输出含 tool_call + tool_result 事件

## Phase 0.5: generate_questions 验证（1h，依赖 §0）✅ GATE PASS

验证 pydantic-ai tool_plain 能否正确处理"skill 自己调 LLM"的嵌套场景。

- [x] 0.5.1 创建 `agent/tools/generate_pydantic.py`，内含 `generate_questions_pydantic(knowledge_points, difficulty, quantity)` 函数
- [x] 0.5.2 函数内部用 `DeepSeekProvider` 调 LLM 出题（与 skills/generate.py 逻辑一致）
- [x] 0.5.3 在 `pydantic_agent.py` 中创建 `create_chem_agent()` 注册 search_exam_bank + generate_questions 双 tool
- [x] 0.5.4 验证：curl `/api/agent/chat/pydantic` -d '{"message":"出3道盐类水解的题"}' → SSE 事件序列完整
- [x] 0.5.5 通过标准检查：3 道题有 content/options/answer/explanation，SSE 含 tool_call → tool_result → text → done

### Phase 0.5 Gate

- **PASS** ✅ → 启动作业 Phase 1-4 的 openspec change `agent-pydanticai-migration`
- ~~FAIL~~

## Phase 1: 基础设施（1.5h，依赖 §0.5 PASS）

- [ ] 1.1 创建 `agent/deps.py` — ChemAIDeps dataclass（student_id, student_profile, persona, episodic, provider_name）
- [ ] 1.2 创建 `agent/models.py` — 4 个 model 工厂（DeepSeek 内置, MiMo/Zhipu/DashScope 用 OpenAIChatModel）
- [ ] 1.3 创建 `agent/tools.py` — 10 个 skill 全部迁移为 async 函数，参数类型化（str/int/bool/Optional）
- [ ] 1.4 验证：`python -c "from agent.tools import *"` 10 个函数可导入

## Phase 2: Agent 工厂 + SSE 适配（1.5h，依赖 §1）

- [ ] 2.1 创建 `agent/agents.py` — ChemAIAgentFactory（persona × provider 预建 Agent）
- [ ] 2.2 创建 `agent/sse_adapter.py` — AgentStreamEvent → SSE 完整映射（7 种事件类型 + phase 状态机）
- [ ] 2.3 `fastapi_sse.py` 新增 `POST /api/agent/chat/v2/stream` 端点
- [ ] 2.4 验证：curl v2 端点 → SSE 格式与旧端点一致，前端 agent.js 正常渲染

## Phase 3: 会话持久化（1h，依赖 §2）

- [ ] 3.1 `memory.py` 加 `to_pydantic_messages()` 和 `from_pydantic_conversation()`
- [ ] 3.2 `_conversations` 从存 ChemAgent 改为存 message_history
- [ ] 3.3 验证：带 conversation_id 的两轮对话上下文保留

## Phase 4: 清理（0.5h，依赖 §3）

- [ ] 4.1 删除 `core.py`, `skill_registry.py`, `provider/*`, `skills/*`, `pydantic_agent.py`
- [ ] 4.2 更新 `app/main.py` 导入
- [ ] 4.3 全量回归：所有 3 persona + 4 provider + 10 skill 冒烟测试

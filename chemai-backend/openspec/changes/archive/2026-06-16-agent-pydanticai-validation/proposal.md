## Why

`agent-pydanticai-poc` (6/13) 验证了 pydantic-ai 的基础可行性：DeepSeek 连接、文本流式、skill 迁移模式、端点集成均通过。但被 pydantic-ai 0.0.10 缺少 `stream_events()` 阻塞——无法验证 tool_call/tool_result 事件映射。

现在 pydantic-ai 1.107.0 已安装（6/15），阻塞解除。但 PoC 只验证了最简单的 skill（`search_exam_bank`，纯函数，不调 LLM）。在全量迁移 10 个 skill 之前，必须验证 **pydantic-ai 能否正确处理"skill 自己调 LLM"的嵌套场景**（`generate_questions` 是代表）。

如果通过，启动 Phase 1-4 全量迁移（替代自建 ChemAgent ~1000 行）。如果失败，记录原因，保持自建 ChemAgent。

## What Changes

### Phase 0: PoC 修补（依赖：无）
- `agent/pydantic_agent.py`: `stream_text()` → `run_stream_events()`（1.107.0 API）
- 修复 SSE 双重输出 bug
- 用内置 `DeepSeekProvider` 替代手写 `OpenAIModel`

### Phase 0.5: generate_questions 验证（依赖：Phase 0）
- `agent/tools/generate_pydantic.py`: 新建，`generate_questions` 的 pydantic-ai tool_plain 版本
- `agent/pydantic_agent.py`: 注册为第二个 tool，形成双 tool agent
- 验证：curl 端点 → SSE 完整链路（tool_call → tool_result → text → done）

### Phase 1-4: 全量迁移（依赖：Phase 0.5 通过）
- `agent/deps.py`: ChemAIDeps 依赖注入容器
- `agent/models.py`: 4 个 model 工厂函数
- `agent/tools.py`: 10 个 skill 全部迁移为 tool_plain
- `agent/agents.py`: ChemAIAgentFactory（persona × provider）
- `agent/sse_adapter.py`: AgentStreamEvent → SSE 完整适配
- `agent/channel/fastapi_sse.py`: 新增 `/api/agent/chat/v2/stream`
- `agent/memory.py`: MessageHistory 桥接方法
- 删除 `core.py`, `skill_registry.py`, `provider/*`, `skills/*`, `pydantic_agent.py`

### Phase 0 revert path
如果 Phase 0.5 验证失败，删除 `agent/tools/generate_pydantic.py`，回退 `pydantic_agent.py` 改动。自建 ChemAgent 不受影响。

## Capabilities

### Continuing from agent-pydanticai-poc
- `tool-migration`: 扩展验证范围，从纯函数 skill → LLM 嵌套 skill
- `sse-adapter`: 从手动 stream_text → run_stream_events 完整事件流

### New
- `llm-nested-tool`: 验证 tool_plain 函数内调 LLM 的可行性
- `deps-injection`: 验证 RunContext.deps 承载 student_profile

## Impact

- **Files (Phase 0-0.5)**: 2 new, 1 modified
- **Files (Phase 1-4)**: 5 new, 2 modified, ~10 deleted
- **API**: Phase 0.5 复用现有 `/api/agent/chat/pydantic`；Phase 2 新增 `/api/agent/chat/v2/stream`
- **Breaking**: 无。Phase 1-4 完成后旧端点可切换到新版，但旧版代码先保留
- **Dependencies**: pydantic-ai 1.107.0（已安装）
- **Risk**: Phase 0.5 是 gate——1h 内判断全量迁移可行性

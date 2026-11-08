## Why

`agent-pydanticai-poc` (6/13) + `agent-pydanticai-validation` (6/16) 已验证：
- pydantic-ai 1.107.0 `run_stream_events()` 完整 tool_call/tool_result/text/done 事件
- `@agent.tool_plain` 可处理"skill 自己调 LLM"的嵌套场景（generate_questions PASS）
- SSE 事件格式与现有前端 agent.js 兼容

自建 ChemAgent（core.py 427行 + skill_registry.py 89行 + provider/* 566行 = ~1100行）可以全部替换为 pydantic-ai 等价功能。Gate 已通过，执行全量迁移。

## What Changes

### New files
- `agent/deps.py` (~30行) — ChemAIDeps 依赖注入容器
- `agent/models.py` (~80行) — 4 个 model 工厂（DeepSeek 内置, MiMo/Zhipu/DashScope OpenAIChatModel）
- `agent/tools.py` (~350行) — 10 个 skill 全部迁移为 tool_plain async 函数
- `agent/agents.py` (~120行) — ChemAIAgentFactory（persona × provider）
- `agent/sse_adapter.py` (~80行) — AgentStreamEvent → SSE（从 pydantic_agent.py 抽出）

### Modified files
- `agent/channel/fastapi_sse.py` — 新增 `/api/agent/chat/v2/stream`，旧端点保留
- `agent/memory.py` — 加 `to_pydantic_messages()` / `from_pydantic_conversation()`
- `agent/skills_init.py` — 导入从 skills/* 改为 tools.py

### Deleted files（Phase 4）
- `agent/core.py` — 被 pydantic-ai Agent 替代
- `agent/skill_registry.py` — 被 @agent.tool_plain 替代
- `agent/provider/` — 被 models.py + pydantic-ai 内置替代
- `agent/skills/` — 业务逻辑迁移到 tools.py
- `agent/pydantic_agent.py` — 被 agents.py + sse_adapter.py 替代

### Net code change
- 删除 ~1100 行自研代码
- 新增 ~660 行适配代码
- 净减少 ~440 行

## Capabilities

- `full-tool-migration`: 10 个 skill 全部迁移到 pydantic-ai tool_plain
- `persona-system`: 3 个 persona（tutor/teacher/parent）的 Agent 工厂
- `provider-unified`: DeepSeek/MiMo/Zhipu/DashScope 统一通过 pydantic-ai Model 接口
- `sse-compatibility`: 前端 agent.js 零改动
- `session-persistence`: conversation_id 对话记忆保留

## Impact

- **Breaking**: 无。新端点 `/api/agent/chat/v2/stream` 与旧端点并行，前端按需切换
- **Dependencies**: pydantic-ai 1.107.0（已安装）
- **Risk**: 低。Phase 0.5 已验证最复杂的嵌套 LLM 场景，其余 9 个 skill 迁移为机械操作

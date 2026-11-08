## Why

Agent 代码审查发现 6 个问题，其中 4 个影响功能正确性（消息重复导致上下文膨胀、无跨请求记忆、技能创建自己的 LLM 实例绕过 agent 管理、技能无超时可能阻塞管道），2 个是健壮性问题（SSE 断连后连接未清理）。

与其重写 550 行的 `core.py`（风险高、阻塞功能迭代），采用分 4 批修补的策略，每批 2-3 个文件、独立可测。

## What Changes

### Batch 1: 消息重复 + 会话持久化（`agent/core.py`, `agent/memory.py`, `agent/channel/fastapi_sse.py`）

- **Fix**: `run_stream()` 中 `add_turn("user")` 从循环内移到循环前，删除循环内和 reply phase 前的重复调用
- **New**: `MemoryStack.to_dict()` / `MemoryStack.from_dict()` 序列化方法
- **New**: `ChatRequest.conversation_id` 可选字段，提供时复用已有 agent 实例
- **New**: `POST /api/agent/chat/reset` 重置对话端点
- **Change**: stream 端点去掉 `finally: agent.close()`（持久化 agent 不关连接）

### Batch 2: 技能执行超时（`agent/skill_registry.py`）

- **New**: `registry.execute()` 中包装 `asyncio.wait_for(timeout=30)`
- 超时返回 `{"error": "Skill 'xxx' timed out after 30s"}`，不抛异常

### Batch 3: Skill 注入 provider（`agent/skill_registry.py`, `agent/core.py`, 4 个 skill）

- **New**: `SkillRegistry._provider` + `set_provider()` 方法
- **Change**: `generate.py`, `tutor.py`, `experiment.py`, `weekly_report.py` 中 `DeepSeekProvider()` 替换为 `registry._provider or DeepSeekProvider()`

### Batch 4: SSE 连接清理（`agent/channel/fastapi_sse.py`）

- **Fix**: `generate()` 协程 `finally` 块中显式清理非持久化 agent 的 provider 连接

## Capabilities

### New Capabilities
- `memory-persistence`: agent 跨请求保持对话记忆，支持通过 conversation_id 恢复会话
- `skill-timeout`: 每个 skill 执行有 30s 超时保护，防止阻塞 agent 管道
- `skill-provider-injection`: skill 通过 registry 获取 agent 的 LLM provider，不再各自创建实例
- `sse-cleanup`: 客户端断连后正确清理 httpx 连接

## Impact

- **Files changed**: 8 files, ~120 lines added, ~10 lines removed
- **API**: `ChatRequest` 新增可选 `conversation_id` 字段。`POST /api/agent/chat/reset` 新端点。**向后兼容**
- **Breaking**: 无。不提供 `conversation_id` 时行为和当前一致
- **Dependencies**: 无新增依赖

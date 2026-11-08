## Why

当前自研 agent 循环（`core.py` 550 行）在稳定后可以工作，但 Gateway（意图分类）、Planner（目标分解）、`_parse_decision()`（JSON 解析）三层增加了不必要的复杂度和额外 LLM 调用。

PydanticAI 是 Pydantic/FastAPI 团队的官方 agent 框架（MIT 协议，v1.0+），天然适配我们的技术栈。它提供：
- 原生 DeepSeek 支持
- `event_stream_handler` 细粒度流式事件（可映射到我们的 14 种 SSE 事件）
- `@agent.tool` 装饰器（和我们 `@registry.register` 模式一致）
- 内置 `message_history` 会话持久化
- Capabilities 插件（Thinking、WebSearch、Memory、Compaction）
- 类型安全的结构化输出验证

**本次只做概念验证**：将一个 skill（`search_exam_bank`）迁移到 PydanticAI，验证技术可行性后再决定是否全量迁移。

## What Changes

### New: `agent/pydantic_agent.py` (~80 lines)

- 用 PydanticAI `Agent` 创建一个最小 agent 实例
- 注册 `search_exam_bank` 为 `@agent.tool`
- 实现 `event_stream_handler` 适配层，将 PydanticAI 流式事件映射为现有 SSE 格式

### Changed: `agent/channel/fastapi_sse.py` (~30 lines)

- 新增 `/api/agent/chat/pydantic` 端点，复用 PydanticAI agent
- 或直接在现有端点中增加 provider 分支选择

### New: `agent/skills/search_pydantic.py` (~40 lines)

- `search_exam_bank` 的 PydanticAI 版本
- 带类型注解的参数和返回值
- 通过 `RunContext` 获取依赖（替代全局 import）

## Capabilities

### New Capabilities
- `tool-migration`: 验证 `@registry.register` → `@agent.tool` 迁移的可行性和工作量
- `sse-adapter`: 验证 PydanticAI `event_stream_handler` 适配现有 SSE 事件格式的兼容性

## Impact

- **Files**: 3 new files（`pydantic_agent.py`, `search_pydantic.py`, 端点改动）
- **API**: 新增 `/api/agent/chat/pydantic` 端点用于对比测试
- **Breaking**: 无。现有端点和 agent 完全不受影响
- **Dependencies**: 新增 `pydantic-ai` pip 包
- **Risk**: 如果 PoC 失败，删除 3 个文件即可回退，零影响

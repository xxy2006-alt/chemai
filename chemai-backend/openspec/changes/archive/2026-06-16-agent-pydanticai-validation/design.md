## Context

`agent-pydanticai-poc` 已验证 pydantic-ai 0.0.10 的基础可行性但被 `stream_events()` 缺失阻塞。pydantic-ai 1.107.0 解除了这个阻塞，但 PoC 只覆盖了最简单的纯函数 skill（`search_exam_bank`）。

在全量迁移前，必须验证 pydantic-ai 1.107.0 能否正确处理"skill 自己调 LLM"的嵌套场景。`generate_questions` 是这类 skill 的代表——它内部创建 LLM provider，调 DeepSeek 出题，解析 JSON 回复，返回结构化结果。

## Goals / Non-Goals

**Goals:**
- Phase 0: 将 PoC 升级到 1.107.0 API（`run_stream_events` 替代 `stream_text`），验证完整 tool_call 事件链路
- Phase 0.5: 迁移 `generate_questions` 为 pydantic-ai tool_plain，验证嵌套 LLM 调用模式
- 如果 Phase 0.5 通过：Phase 1-4 全量迁移（见 proposal.md）
- 如果失败：记录失败原因，固化为 openspec conclusion

**Non-Goals:**
- 不做性能对比测试（Phase 1-4 完成为前提）
- 不迁移其余 9 个 skill（Phase 0.5 通过后再做）
- 不改前端 agent.js

## Decisions

### D1: stream_events 使用方式

**选择**: `agent.run_stream_events()` 替代 `agent.run_stream() + result.stream_text()`。

**理由**: 1.107.0 的 `run_stream_events()` 返回 `AgentEventStream`，yield `AgentStreamEvent` 类型（PartStartEvent, PartDeltaEvent, FunctionToolCallEvent, FunctionToolResultEvent, FinalResultEvent）。这些事件类型与 PoC 中已写的 `pydantic_event_to_sse()` 完全匹配——事件映射代码不需要大改，只需加 `PartEndEvent` 和 `AgentRunResultEvent` 的处理。

### D2: generate_questions 的 provider 策略

**选择**: tool 函数内部直接创建 `DeepSeekProvider`（不依赖 `ctx.deps`）。

**理由**: Phase 0.5 是最小验证，不等 deps 注入系统到位。tool 内部用与当前 `skills/generate.py` 相同的模式：`from agent.provider.deepseek import DeepSeekProvider` + `provider.chat()` + `provider.close()`。如果这个模式可行，Phase 1-4 再升级为 `ctx.deps.provider` 注入。

### D3: 验证端点

**选择**: 复用现有 `POST /api/agent/chat/pydantic` 端点，扩展 `create_search_agent()` 为 `create_chem_agent()` 注册双 tool。

**理由**: 不新增端点，减少验证阶段的工作量。Phase 1-4 再建 `/api/agent/chat/v2/stream`。

### D4: 成功/失败判定标准

**通过标准**:
1. curl "出3道盐类水解的题" → HTTP 200
2. SSE 事件序列包含: phase(thinking) → tool_call(generate_questions) → phase(executing) → tool_result(含3道题) → phase(reply) → text(自然语言回复) → done
3. 3 道题每题包含 content/options/answer/explanation
4. 在 60s 内完成

**失败条件**:
- tool 未触发（agent 直接回复文字而不调用 generate_questions）
- tool 触发但执行报错
- SSE 事件类型缺失（无 tool_call 或 tool_result）
- tool 结果无法被 agent 正确解读（回复与题目无关）

## Risks / Trade-offs

- **DeepSeekProvider /beta 端点**: pydantic-ai 1.107.0 的内置 DeepSeekProvider 默认指向 `/v1`，非 `/beta`。如果用内置 provider 不传 `strict` mode，tool calling 可能退化到 JSON prompt 模式。Phase 0 需要先验证。
- **Nested provider.close()**: generate_questions 内部创建 provider → 用完 close → agent 外层也有 provider。需要确保 tool 内部的 provider 生命周期不影响 agent 外层。
- **1.107.0 API 稳定性**: 从 0.0.10 跳 1.107.0 是大版本，某些 API 可能重命名。Phase 0 先做好基础连接测试。

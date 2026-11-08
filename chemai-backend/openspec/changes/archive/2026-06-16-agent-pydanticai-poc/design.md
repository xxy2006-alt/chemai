## Context

在完成 agent 稳定化（`agent-stabilization` change）后，agent 处于功能正确但架构偏重的状态。PydanticAI 调研表明它在模型支持（原生 DeepSeek）、工具装饰器模式、流式事件系统三方面与我们现有架构高度兼容。

**本 change 仅做概念验证**，不涉及全量迁移决策。

## Goals / Non-Goals

**Goals:**
- 验证 `@agent.tool` 能否直接替代 `@registry.register` 模式
- 验证 PydanticAI `event_stream_handler` 能否映射到我们现有的 14 种 SSE 事件
- 估算迁移一个 skill 的实际工作量
- 验证 DeepSeek provider 在 PydanticAI 中的稳定性

**Non-Goals:**
- 不迁移全部 10 个 skill
- 不替换前端 agent.js
- 不移除 Gateway/Planner
- 不做性能对比测试

## Decisions

### D1: PoC 范围 — 单个 skill vs 最小可用 agent

**选择**: 单个 skill（`search_exam_bank`）+ 流式对话能力。

**理由**: `search_exam_bank` 是最简单的纯函数 skill（无 LLM 调用），迁移风险最低。在此基础上验证 tool call + 流式回复的完整链路即可覆盖核心风险点。

### D2: 端点策略 — 新端点 vs 分支切换

**选择**: 新增 `/api/agent/chat/pydantic` 端点。

**理由**: 方便 A/B 对比测试。在聊天界面发同一句话给两个端点，对比响应质量、延迟、事件顺序。比在现有端点内加 `if provider == "pydantic"` 更干净。

### D3: 事件映射 — 1:1 vs 适配层

**选择**: 适配函数 `pydantic_event_to_sse(event) -> str`。

**理由**: PydanticAI 的事件类型（`PartDeltaEvent`, `FunctionToolCallEvent`, `FinalResultEvent` 等）和我们的 SSE 事件（`text`, `tool_call`, `tool_result`, `done` 等）是 M:N 映射（一个 PydanticAI 事件可能产生多个 SSE 事件，反之亦然）。用适配函数封装这个映射逻辑，方便后续调优。

### D4: skill 文件策略 — 新文件 vs 原地修改

**选择**: 新建 `skills/search_pydantic.py`，不动 `skills/search.py`。

**理由**: PoC 阶段不破坏现有代码。两个文件并存，可以对比注册方式的差异。

## Risks / Trade-offs

- **PydanticAI 版本兼容**: PoC 时锁定具体版本号，避免框架升级导致的不确定性
- **事件映射可能不完美**: 某些 SSE 事件类型（如 `navigate`, `populate`, `action`）在 PydanticAI 中没有直接等价物，需要评估是否在 PoC 阶段处理
- **新端点性能**: PydanticAI agent 的冷启动时间 vs 我们自研 agent 的对比，如果差距过大（>2x），需要在决策中考虑

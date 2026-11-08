## Context

Phase 0.5 Gate PASS。pydantic-ai 1.107.0 已验证能正确处理：
- 纯函数 tool（search_exam_bank）
- 嵌套 LLM tool（generate_questions）
- SSE 事件完整映射（thinking → tool_call → tool_result → reply → text → done）

全量迁移的风险点已被消除，执行机械的批量迁移 + 适配层建设。

## Goals / Non-Goals

**Goals:**
- 10 个 skill 全部迁移为 pydantic-ai tool_plain async 函数
- 3 个 persona 的 Agent 工厂（按 persona 过滤 tool 列表）
- 4 个 provider 统一通过 models.py 工厂函数
- 新增 `/api/agent/chat/v2/stream`（SSE 格式与旧端点一致）
- 会话持久化（conversation_id 复用）

**Non-Goals:**
- 不改变前端 agent.js
- 不改变 persona YAML 文件内容
- 不改变 audit.py, gateway.py, planner.py
- 不删除旧代码（Phase 4 最后做）

## Decisions

### D1: 新端点策略

**选择**: 新增 `/api/agent/chat/v2/stream`，旧端点 `/api/agent/chat/stream` 保持不变。

**理由**: 前端按需切换，降低风险。旧端点继续用自建 ChemAgent 作为 fallback。

### D2: tool 迁移策略

**选择**: 新建 `agent/tools.py`，每个 skill 重写为 async 函数 + type hints。旧 `skills/*.py` 保留不删。

**理由**: Phase 0.5 已证明迁移模式（签名加 type hints + str 返回值 + registry/provider 移除）。10 个 skill 中 9 个是机械操作，1 个（generate_questions）已迁移。

### D3: persona 系统

**选择**: `ChemAIAgentFactory` 预建 3 个 Agent 实例（tutor/teacher/parent），按请求参数选择。

**理由**: pydantic-ai system_prompt 在 Agent 构造时固定。3 个 persona 差异足够大（不同 tool 集合 + 不同的系统提示词），预建是合理的选择。

### D4: provider 工厂

**选择**: DeepSeek 用内置 `"deepseek:deepseek-chat"` 字符串；MiMo/Zhipu/DashScope 用 `OpenAIChatModel` + 自定义 `base_url`。

**理由**: DeepSeek 有原生支持。其余 3 个 provider 都是 OpenAI 兼容 API，OpenAIChatModel 直接能用。MiMo 的 `enable_search` 通过 web_search skill 直连 HTTP 处理。

### D5: MiMo enable_search

**选择**: web_search skill 保持直接 HTTP 调用 MiMo API（不通过 pydantic-ai model）。

**理由**: `enable_search` 是 MiMo 自定义参数，不在 OpenAI 规范中。当前实现已经绕开 provider 直连，不需要改。

## Risks / Trade-offs

- **10 skill 迁移工作量大但机械**: 每个 skill ~15 行改动（签名 + decorator 移除 + import 调整）。风险低。
- **多 provider Agent 实例的内存**: 预建 3 persona × 4 provider = 12 个 Agent 实例。每个 Agent 轻量（model + system_prompt + tool definitions），内存可控。
- **前端切换**: v2 端点 SSE 格式与 v1 一致，前端只需改 fetch URL。需要做对比测试。

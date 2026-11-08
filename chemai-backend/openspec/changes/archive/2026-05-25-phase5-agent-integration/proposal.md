## Why

ChemAgent 后端已就绪（8 Skill + 3 Persona + 3 Provider），前端 `HermesThinking.js` 已有完整 SSE 流式 UI。需要对接两者：`hermes.js` API 端点指向 `/api/agent/chat/stream`，DeepSeek Strict Mode 启用，增加 SSE 事件类型（参考 纸鸢AI 的 25 种事件），工具结果分层（llmSummary + uiPayload）。

## What Changes

### 5.1 hermes.js API 对接
- `src/services/hermes.js` — API 端点 `/api/hermes/v1/chat/completions` → `/api/agent/chat/stream`
- `HERMES_API` 常量 → `AGENT_API`
- 保持现有 SSE 事件解析兼容

### 5.2 DeepSeek Strict Mode
- `agent/provider/deepseek.py` — `chat()` 方法支持 `strict: true` + `/beta` 端点
- `agent/skill_registry.py` — `to_openai_tools()` 生成符合 Strict Mode 的 schema（`additionalProperties: false`）

### 5.3 SSE 事件类型扩展
- 新增：`phase`（阶段切换）、`tool_call`（工具调用开始）、`tool_result`（工具结果）
- 客户端解析这些事件后驱动 UI（AgentStatusBar、ToolResultCard）

### 5.4 首页改造为 Agent 界面
- 参考 `D:\求职助手升级版` 的设计模式：
  - 主界面 = Agent 聊天 + 快捷操作入口
  - AgentStatusBar（当前阶段 + 工具名 + 耗时）
  - ToolResultCard（可折叠工具结果）
  - SuggestionChips（快捷提问入口）
- `index_new.html` 的 `#app` 作为 Agent 主界面
- 侧边栏保留原有功能入口（OCR、题库、考试管理、学情面板）

### 5.5 MCP Web Search（可选）
- 调研接入 Web Search MCP 用于查询最新高考资讯

## Capabilities

### New Capabilities
- `agent-ui`: Agent 聊天主界面，替代首页
### Modified Capabilities
- `hermes-service`: API 端点切换到 ChemAgent
- `deepseek-provider`: Strict Mode 支持

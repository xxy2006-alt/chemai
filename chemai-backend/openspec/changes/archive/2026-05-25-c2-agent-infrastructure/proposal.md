## Why

ChemAI 需要统一的 Agent 调度层，让 8 个化学 Skill 可以通过装饰器注册、LLM 自动决策调用哪个 Skill、对话记忆自动管理。当前 `llm_service.py` 只做单次 LLM 调用，没有 Agent 循环，没有工具调用能力。

## What Changes

- 新增 `agent/skill_registry.py` — `@skill.register()` 装饰器，自动生成 OpenAI function calling 格式
- 新增 `agent/memory.py` — 分层记忆（工作记忆 + 情景记忆 + 学生画像）
- 新增 `agent/core.py` — `ChemAgent` 类，Think → Route → Execute 循环
- 新增 `agent/personas/tutor.yaml` — 学生端 AI 助教 system prompt
- 新增 `agent/personas/teacher.yaml` — 教师端教研助手 system prompt
- 新增 `agent/personas/parent.yaml` — 家长端周报助手 system prompt

## Capabilities

### New Capabilities
- `agent-core`: Agent 调度循环（Think → Route → Execute），支持流式/非流式
- `skill-registry`: Skill 装饰器注册，自动生成 tool definitions
- `agent-memory`: 分层对话记忆，学生画像加载

### Modified Capabilities
- (无)

## Impact

- `agent/` 目录新增 6 个文件
- 依赖 C1（`agent/provider/`）的 LLMProvider
- 不修改现有 API 路由

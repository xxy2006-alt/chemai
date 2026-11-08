## Context

C1 已完成三个 LLMProvider。C2 在 Provider 之上构建 Agent 调度层。四个核心组件：
1. SkillRegistry — 装饰器注册 Skill，生成 tool definitions
2. MemoryStack — 对话上下文管理，滑动窗口 + 学生画像
3. ChemAgent — Think(LLM决策) → Route(意图分发) → Execute(调Skill) →循环
4. Persona YAML — 角色 system prompt 配置

## Goals / Non-Goals

**Goals:**
- `@registry.register()` 一行装饰器注册 Skill
- `registry.to_openai_tools()` 自动生成 function calling 格式
- `ChemAgent.run()` 完成完整 Think→Route→Execute 循环
- `ChemAgent.run_stream()` SSE 流式输出
- 3 个 Persona 通过 yaml 配置切换

**Non-Goals:**
- 不做多 Agent 协作
- 不做 Agent 间 handoff
- 不做持久化 Session（内存级）

## Decisions

1. **Agent Loop 用简单的 while 循环，不用状态机** — 当前场景最多 2-3 轮 tool call，线性循环够用
2. **Persona 用 YAML 而非 Python 类** — 非技术人员也能改 prompt，方便迭代
3. **Memory 用 deque + dict，不引入向量数据库** — 20 轮对话 + 结构化画像对化学教学足够

## Risks / Trade-offs

- [LLM 可能返回格式错误的 JSON] → 加 try/except + fallback 直接回复
- [Tool call 可能循环超过 max_turns] → 默认 5 轮上限，超限返回"请重新提问"

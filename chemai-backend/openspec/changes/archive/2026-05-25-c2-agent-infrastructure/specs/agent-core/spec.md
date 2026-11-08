## ADDED Requirements

### Requirement: Agent 核心循环
系统 SHALL 提供 `ChemAgent` 类，执行 Think → Route → Execute 循环。Think 阶段由 LLM 决策（直接回复或调用 Skill），Execute 阶段调用对应 Skill 函数。

#### Scenario: 直接回复（无需工具）
- **WHEN** 用户问"什么是化学"（不需要调用工具的问题）
- **THEN** Agent 直接返回文本回复，不调用任何 Skill

#### Scenario: 调用工具后回复
- **WHEN** 用户问"Fe + O2 = Fe2O3 配平了吗"（需要调用 balance_equation 的问题）
- **THEN** Agent 先调用 balance_equation Skill，再将结果喂给 LLM 生成友好回复

#### Scenario: 超过最大轮数
- **WHEN** Agent 循环超过 5 轮（max_turns）
- **THEN** 返回"请重新提问"并结束循环

### Requirement: 流式输出
系统 SHALL 提供 `run_stream()` 方法，通过 `AsyncIterator[str]` 逐 chunk 输出 Agent 的回复内容。

#### Scenario: SSE 流式回复
- **WHEN** 调用 `agent.run_stream("配平 H2+O2=H2O")`
- **THEN** 逐 chunk yield 回复内容，前端可逐字显示

### Requirement: Persona 切换
系统 SHALL 支持通过 `AgentConfig.persona` 参数切换角色。支持 "tutor"、"teacher"、"parent" 三种 Persona，每种有不同的 system prompt 和可访问 Skill。

#### Scenario: 学生端不能被看班级数据
- **WHEN** 使用 persona="tutor"
- **THEN** system prompt 不包含班级统计数据访问权限

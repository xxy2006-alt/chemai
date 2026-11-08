## ADDED Requirements

### Requirement: Skill 装饰器注册
系统 SHALL 提供 `@registry.register()` 装饰器，将 async 函数注册为 Agent 可调用的 Skill。每个 Skill MUST 包含 name、description、parameters 元信息。

#### Scenario: 注册一个 Skill
- **WHEN** 使用 `@registry.register(name="test", description="测试", parameters={"x": "输入"})` 装饰一个函数
- **THEN** 该函数被注册到 registry，可通过 `registry.execute("test", {"x": "hello"})` 调用

#### Scenario: 生成 OpenAI tools 格式
- **WHEN** 调用 `registry.to_openai_tools()`
- **THEN** 返回 `[{"type": "function", "function": {"name": "...", "description": "...", "parameters": {...}}}]` 格式的列表

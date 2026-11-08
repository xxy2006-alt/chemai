## ADDED Requirements

### Requirement: 结构化 SSE 事件流
ChemAgent 的 `run_stream()` SHALL 输出结构化 JSON 事件，每个事件包含 `type` 字段标识事件类型。支持的事件类型：`phase`、`text`、`tool_call`、`tool_result`、`tool_error`、`done`。

#### Scenario: 直接回复（无工具调用）
- **WHEN** 学生问不需要工具的问题（如"什么是化学"）
- **THEN** SSE 流顺序输出: `phase: thinking` → `phase: reply` → `text` 流式块... → `done`

#### Scenario: 工具调用流程
- **WHEN** 学生问需要工具的问题（如"配平 Fe+O2=Fe2O3"）
- **THEN** SSE 流顺序输出: `phase: thinking` → `tool_call: balance_equation` → `tool_result: {...}` → `phase: reply` → `text` 流式块... → `done`

#### Scenario: 工具调用失败
- **WHEN** 工具执行抛出异常
- **THEN** 输出 `tool_error` 事件而非 `tool_result`，Agent 继续尝试回复

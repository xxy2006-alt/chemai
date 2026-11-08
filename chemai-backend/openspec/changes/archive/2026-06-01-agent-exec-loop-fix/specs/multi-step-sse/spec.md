## ADDED Requirements

### Requirement: Agent SHALL emit step SSE events during multi-step execution
During `run_stream()`, after each skill execution that is not the last step, the agent SHALL emit a `step` SSE event with the format `{"type": "step", "current": <N>, "skill": "<skill_name>"}`.

#### Scenario: Two-step execution emits one step event between skills
- **WHEN** the agent executes skill 1 and decides to continue to skill 2
- **THEN** a `step` SSE event with `current: 1, skill: "<skill_1_name>"` SHALL be emitted before re-entering the think phase

#### Scenario: Single-step execution emits no step events
- **WHEN** the agent executes one skill and the LLM chooses to reply
- **THEN** no `step` SSE event SHALL be emitted

### Requirement: Frontend SHALL display multi-step progress
The frontend `agent.js` SHALL handle the `step` SSE event type and display a progress indicator (e.g., "第 N 步：正在分析...") in the chat bubble.

#### Scenario: Step event updates the thinking status
- **WHEN** a `step` event with `current: 2, skill: "generate_questions"` is received
- **THEN** the chat bubble's think-status element SHALL display "第 2 步：正在出题..."

#### Scenario: Multiple tool cards in single response
- **WHEN** the agent calls multiple tools in one streaming response
- **THEN** the frontend SHALL append additional tool cards to the chat rather than replacing the existing one

### Requirement: Observation text SHALL be truncated for context window safety
When formatting skill results as observation text, content exceeding 2000 characters SHALL be truncated with a "（内容过长，已截断）" suffix.

#### Scenario: Short result is not truncated
- **WHEN** a skill returns a result with 500 characters
- **THEN** the full result SHALL be included in the observation

#### Scenario: Long result is truncated
- **WHEN** a skill returns a result with 3500 characters
- **THEN** only the first 2000 characters SHALL be included, followed by "（内容过长，已截断）"

### Requirement: System prompt SHALL reference episodic context
The `_build_system_prompt()` method SHALL include a line instructing the LLM to examine previous tool execution results when deciding the next action.

#### Scenario: System prompt includes episodic hint
- **WHEN** `_build_system_prompt()` is called and episodic memory is non-empty
- **THEN** the generated system prompt SHALL include a phrase equivalent to "如果上下文中包含之前的工具执行结果，请根据这些结果决定下一步行动"

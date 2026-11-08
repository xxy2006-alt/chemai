## ADDED Requirements

### Requirement: AgentError hierarchy SHALL be defined
A new `agent/errors.py` SHALL define an `AgentError` base exception and subclasses: `SkillExecutionError`, `SkillNotFoundError`, `SkillPermissionError`, `PlanError`. `ProviderError` (existing in provider/base.py) SHALL be integrated into this hierarchy.

#### Scenario: SkillExecutionError preserves original error
- **WHEN** a skill raises `ValueError("invalid input")`
- **THEN** the wrapping `SkillExecutionError` SHALL have `.skill_name`, `.original_error`, and a message combining both

#### Scenario: SkillPermissionError includes persona info
- **WHEN** a forbidden skill is called
- **THEN** `SkillPermissionError` SHALL have `.skill_name` and `.persona` fields

### Requirement: run_stream SHALL emit structured error SSE events
When an error occurs during streaming execution, the agent SHALL emit an SSE event: `{"type": "error", "code": "<error_code>", "message": "<user_friendly_message>", "recoverable": true/false}`.

#### Scenario: Recoverable error — timeout
- **WHEN** a provider call times out
- **THEN** the error SSE SHALL have `code: "PROVIDER_TIMEOUT"` and `recoverable: true`

#### Scenario: Non-recoverable error — permission denied
- **WHEN** a skill is called with insufficient persona permissions
- **THEN** the error SSE SHALL have `code: "SKILL_PERMISSION_DENIED"` and `recoverable: false`

### Requirement: skill_registry.execute SHALL wrap exceptions as SkillExecutionError
Instead of returning bare `{"error": "..."}` dict on failure, `registry.execute()` SHALL raise `SkillExecutionError(name, original_exception)` which is processed at the agent level.

#### Scenario: Skill failure raises proper exception
- **WHEN** `generate_questions` raises `ValueError`
- **THEN** execute() SHALL raise `SkillExecutionError(skill_name="generate_questions", original_error=ValueError)`

### Requirement: Frontend SHALL display error events
`agent.js` SHALL handle the `error` SSE event type and display a user-friendly error message in the chat bubble, with a retry button for recoverable errors.

#### Scenario: Recoverable error shows retry button
- **WHEN** error event with `recoverable: true` is received
- **THEN** the chat bubble SHALL show the error message with a "重试" button

#### Scenario: Non-recoverable error shows explanation only
- **WHEN** error event with `recoverable: false` is received
- **THEN** the chat bubble SHALL show the error message without a retry button

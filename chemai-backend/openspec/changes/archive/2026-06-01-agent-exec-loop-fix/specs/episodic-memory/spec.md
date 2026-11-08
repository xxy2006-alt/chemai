## ADDED Requirements

### Requirement: Skill results SHALL be written to episodic memory
After every successful skill execution in `run()` and `run_stream()`, the agent SHALL call `self.memory.add_episode(skill_name, skill_result)`. This SHALL apply to all skill execution paths including the web_search auto-retry fallback in `run_stream()`.

#### Scenario: Single skill execution writes episode
- **WHEN** `diagnose_barrier` executes successfully
- **THEN** `memory.episodic["diagnose_barrier"]` SHALL contain the skill's return value

#### Scenario: Episodic data is injected into subsequent think phases
- **WHEN** a second think phase occurs after skill execution
- **THEN** `build_context()` SHALL include episodic memory data in the messages sent to the LLM, per existing logic at `memory.py:67-69`

#### Scenario: Auto-retry path also writes episodes
- **WHEN** `search_exam_bank` returns 0 results and `web_search` is auto-triggered
- **THEN** both `search_exam_bank` and `web_search` episodes SHALL be written to episodic memory

#### Scenario: Failed skill does not pollute episodic memory
- **WHEN** a skill raises an exception during execution
- **THEN** no episode SHALL be written for that skill (the exception is handled via tool_error SSE event)

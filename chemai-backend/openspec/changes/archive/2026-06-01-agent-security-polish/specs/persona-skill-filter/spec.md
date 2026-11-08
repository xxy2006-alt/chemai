## ADDED Requirements

### Requirement: _build_system_prompt SHALL only inject allowed skills
`_build_system_prompt()` SHALL read `self._persona.get("available_skills", [])` and only include those skills in the `{tools}` placeholder. If `available_skills` is missing or empty, SHALL emit a warning and include all registered skills as fallback.

#### Scenario: Teacher persona gets only 4 skills
- **WHEN** persona is "teacher" and 10 skills are registered
- **THEN** `{tools}` in the system prompt SHALL contain only search_exam_bank, web_search, generate_questions, diagnose_barrier

#### Scenario: Parent persona gets only 2 skills
- **WHEN** persona is "parent" and 10 skills are registered
- **THEN** `{tools}` SHALL contain only weekly_report, diagnose_barrier

#### Scenario: Missing available_skills — safe fallback
- **WHEN** persona YAML has no available_skills field
- **THEN** all registered skills SHALL be included with a console warning

### Requirement: registry.execute SHALL check persona permission
Before executing a skill, `registry.execute(name, args)` SHALL check that the skill name is in the current persona's allowed list. If not, SHALL return `{"error": "Skill '{name}' not allowed for persona '{persona}'"}`.

#### Scenario: Allowed skill executes
- **WHEN** teacher persona calls `search_exam_bank` (allowed)
- **THEN** the skill SHALL execute normally

#### Scenario: Forbidden skill is blocked
- **WHEN** tutor (student) persona calls `weekly_report` (not in available_skills)
- **THEN** registry SHALL return error without executing the skill

### Requirement: _think SHALL only pass allowed tools to LLM
When calling `registry.to_openai_tools()`, the method SHALL accept an optional `allowed_skills` parameter and return only tool definitions for those skills.

#### Scenario: Teacher tools filtered for function calling
- **WHEN** persona is "teacher" and `_think()` prepares the LLM call
- **THEN** only teacher's 4 allowed skills SHALL be in the `tools` array sent to the LLM

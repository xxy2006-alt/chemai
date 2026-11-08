## ADDED Requirements

### Requirement: PlanGenerator SHALL decompose goals into structured plans
`PlanGenerator.generate(user_goal, available_skills)` SHALL make a single LLM call to decompose a complex user goal into a Plan with ordered PlanStep entries. Each step SHALL include: step number, skill name, arguments, dependency list, and Chinese description.

#### Scenario: Simple goal produces single-step plan
- **WHEN** user goal is "搜索氧化还原反应的真题"
- **THEN** Plan SHALL have 1 step: `{step:1, skill:"search_exam_bank", args:{keyword:"氧化还原反应"}}`

#### Scenario: Complex goal produces multi-step plan
- **WHEN** user goal is "准备期中考试，范围前三章"
- **THEN** Plan SHALL have at least 2 steps with appropriate skill selections

#### Scenario: Dependency chains are preserved
- **WHEN** step 3 depends on step 1 and step 2's output
- **THEN** step 3's `depends_on` SHALL be `[1, 2]` and args SHALL contain `${step_1.field}` references

#### Scenario: Invalid LLM response falls back to single-step
- **WHEN** LLM returns unparseable JSON or empty steps array
- **THEN** PlanGenerator SHALL return a single-step Plan with the best-guess skill

### Requirement: Dependency injection SHALL resolve template references
`PlanGenerator._inject_dependencies(step, prior_results)` SHALL replace `${step_N.field}` patterns in step.args with actual values from prior step results.

#### Scenario: Template resolution
- **WHEN** step.args has `knowledge_points: "${step_1.top_kp}"` and prior_results[1] has `{"top_kp": ["盐类水解", "氧化还原"]}`
- **THEN** resolved args SHALL be `knowledge_points: ["盐类水解", "氧化还原"]`

#### Scenario: Missing dependency — safe fallback
- **WHEN** `${step_5.field}` references a non-existent step
- **THEN** the placeholder SHALL be replaced with empty string

### Requirement: Planning SHALL be triggered by keyword heuristic
`ChemAgent._needs_planning(user_input)` SHALL return true when the input contains 2+ planning keywords (复习/准备/备考/期中/期末/前三章/综合/步骤/计划/安排/同时).

#### Scenario: Planning grammar triggers planning
- **WHEN** user says "准备期中考试，复习前三章"
- **THEN** `_needs_planning()` returns `true`

#### Scenario: Simple question skips planning
- **WHEN** user says "什么是氧化还原反应"
- **THEN** `_needs_planning()` returns `false`

## ADDED Requirements

### Requirement: run_with_plan_stream SHALL execute plan steps sequentially
`ChemAgent.run_with_plan_stream()` SHALL execute each PlanStep in order, resolving dependencies before execution, emitting `plan_progress` SSE events for each step transition, and yielding skill execution SSE events (tool_call/tool_result).

#### Scenario: All steps complete successfully
- **WHEN** a 3-step plan is executed
- **THEN** 3 `plan_progress` events SHALL be emitted with status "completed", and the final event SHALL trigger plan card collapse

#### Scenario: Dependency resolution before step execution
- **WHEN** step 3 depends on steps 1 and 2
- **THEN** step 3's args SHALL be resolved with step 1 and 2's results before execution

### Requirement: Replan SHALL trigger on step failure
When a step fails (exception or error in result), the agent SHALL attempt to replan the remaining steps once. Max 2 replan attempts total.

#### Scenario: Step fails, replan succeeds
- **WHEN** step 2 of 3 fails and replan_count is 0
- **THEN** PlanGenerator.generate() SHALL be called with failure context, replan_count SHALL increment to 1, and new remaining steps SHALL execute

#### Scenario: Max replans exceeded — skip remaining
- **WHEN** a step fails and replan_count is already 2
- **THEN** remaining steps SHALL be marked "skipped", and execution SHALL proceed to done with a summary of what was completed vs skipped

### Requirement: Plan execution SHALL emit SSE events
During plan execution, `plan_summary` SHALL be emitted once at start, and `plan_progress` SHALL be emitted at each step transition.

#### Scenario: Event sequence
- **WHEN** a 2-step plan executes
- **THEN** the SSE sequence SHALL be: phase:planning → plan_summary → plan_progress(running,step:1) → tool_call → tool_result → plan_progress(completed,step:1) → plan_progress(running,step:2) → tool_call → tool_result → plan_progress(completed,step:2) → done

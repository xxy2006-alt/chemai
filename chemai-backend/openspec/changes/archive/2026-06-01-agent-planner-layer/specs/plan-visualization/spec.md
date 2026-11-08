## ADDED Requirements

### Requirement: Frontend SHALL render plan summary as a card
On receiving a `plan_summary` SSE event, the frontend SHALL render a plan card in the chat bubble showing: goal title, total step count, and a list of step descriptions with status indicators.

#### Scenario: Plan card renders with 3 steps
- **WHEN** a plan_summary event with 3 steps is received
- **THEN** a card SHALL appear in the chat with 3 numbered step rows, all showing "pending" status

#### Scenario: Plan card shows running step
- **WHEN** a plan_progress event with `status: "running"` and `current_step: 2` is received
- **THEN** step 2 SHALL be highlighted with an animated pulse indicator

#### Scenario: Plan card shows completed step
- **WHEN** a plan_progress event with `status: "completed"` and `current_step: 1` is received
- **THEN** step 1 SHALL show a green checkmark

#### Scenario: Plan card collapses after completion
- **WHEN** all steps are completed and 2 seconds have elapsed
- **THEN** the plan card SHALL collapse to a summary bar showing "N/N 步骤已完成"

#### Scenario: Collapsed card re-expands on click
- **WHEN** user clicks the collapsed plan summary bar
- **THEN** the full plan card SHALL re-expand showing all step statuses

### Requirement: Phase 'planning' SHALL show in think status
When the SSE phase event is `planning`, the chat bubble's think-status SHALL display "生成计划中..." with the animated dot.

#### Scenario: Planning phase renders
- **WHEN** a phase event with `phase: "planning"` is received
- **THEN** `think-status` innerHTML SHALL be `<span class="dot"></span>生成计划中...`

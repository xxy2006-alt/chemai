## ADDED Requirements

### Requirement: Agent can generate learning plan for a student

The system SHALL provide a `generate_learning_plan` tool accessible to the Agent that accepts `student_id` and/or `student_name`, retrieves the student's actual barrier distribution and weak knowledge points from the database, calls the `/api/diagnosis/learning-plan/generate` endpoint, and returns a structured learning plan document in the chat.

#### Scenario: Teacher generates plan for named student
- **WHEN** teacher says "给张小明生成一份学习计划" in Agent Chat
- **THEN** Agent calls `generate_learning_plan(student_name="张小明")`, the tool resolves the student, generates the plan, and returns a formatted plan document with weekly goals, daily tasks, barrier interventions, and motivation tips visible in the chat

#### Scenario: Teacher generates plan for student by ID
- **WHEN** teacher says "给202610101生成学习计划"
- **THEN** Agent calls `generate_learning_plan(student_id="202610101")`, the tool retrieves the student's real barrier data and generates the plan

#### Scenario: Student has no exercise history
- **WHEN** Agent generates plan for a student with no exercises completed
- **THEN** the tool uses the student's barrier_type from database (or defaults), fetches weak knowledge points from error history (empty list if none), and still produces a reasonable plan

### Requirement: Agent can modify learning plan via natural language

The system SHALL allow the teacher to modify a generated learning plan through natural language instructions in the Agent Chat. The Agent SHALL understand modification intent and update the plan content accordingly, then re-display the updated plan.

#### Scenario: Teacher asks to change weekly content
- **WHEN** teacher says "把第二周的任务改成盐类水解专题" after a plan is generated
- **THEN** Agent updates the plan's Week 2 content to focus on salt hydrolysis and re-displays the modified plan

#### Scenario: Teacher adjusts task volume
- **WHEN** teacher says "第三天的练习太多, 改成2道"
- **THEN** Agent updates the Day 3 task to 2 exercises and re-displays

#### Scenario: Teacher confirms and sends plan
- **WHEN** teacher says "没问题了, 发给张小明"
- **THEN** Agent calls `send_learning_plan(student_id, plan_data)`, the plan is persisted to SqliteStore, and Agent returns confirmation "学习计划已发送给张小明"

### Requirement: Agent can send learning plan to student

The system SHALL provide a `send_learning_plan` tool that persists the confirmed learning plan to SqliteStore at namespace `("student", student_id, "learning_plan")` with key `"current"`, updates the `_plan_cache`, and returns a confirmation message.

#### Scenario: Plan successfully persisted
- **WHEN** Agent calls `send_learning_plan(student_id="202610101", plan_data=<valid plan>)`
- **THEN** the plan is written to SqliteStore, added to `_plan_cache`, and student can retrieve it via `GET /api/diagnosis/learning-plan/{student_id}`

#### Scenario: Plan sent without plan_data
- **WHEN** Agent calls `send_learning_plan` with `student_id` but no `plan_data`
- **THEN** the tool attempts to use the most recently generated plan from `_plan_cache` for that student, or returns an error if no plan exists

### Requirement: Learning plan tools are scoped to teacher persona only

The `generate_learning_plan` and `send_learning_plan` tools SHALL be registered in TOOL_META with personas `["teacher"]` only.

#### Scenario: Student persona cannot generate plans
- **WHEN** a student-user chats with the Agent
- **THEN** the `generate_learning_plan` and `send_learning_plan` tools are not available to the Agent

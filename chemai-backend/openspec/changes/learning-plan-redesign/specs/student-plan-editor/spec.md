## ADDED Requirements

### Requirement: Plan generation uses real student data

The student management UI's "生成学习计划" button SHALL use the student's actual barrier distribution (`student.barrier_type`) and weak knowledge points (derived from error history) when calling the plan generation API, rather than hardcoded defaults.

#### Scenario: Generate plan with real barrier data
- **WHEN** teacher clicks "生成学习计划" for student 202610101 whose barrier_type is `{concept:0.45, reading:0.30, expression:0.25}`
- **THEN** the API is called with `barrier_type` reflecting the dominant barrier (e.g. "concept") and `weak_knowledge_points` populated from the student's error history

#### Scenario: Student has no weakness data
- **WHEN** student has no error history to derive weak knowledge points from
- **THEN** the API is called with an empty `weak_knowledge_points` array, and the LLM generates a general plan based on barrier type only

### Requirement: Plan generation shows progress feedback

The system SHALL display a visible progress indicator when a learning plan is being generated, replacing the current silent 30-second wait.

#### Scenario: Plan generation starts
- **WHEN** teacher clicks "生成学习计划"
- **THEN** a spinner with the text "正在生成学习计划..." appears in the Drawer below the student info section

#### Scenario: Plan generation completes
- **WHEN** the API returns a successful plan
- **THEN** the spinner is replaced by the rendered plan card

#### Scenario: Plan generation fails
- **WHEN** the API returns an error
- **THEN** the spinner is replaced by an error message with a "重试" button

### Requirement: Plan displays as editable card in Drawer

The generated learning plan SHALL be displayed as a structured, editable card within the student detail Drawer. Each editable field SHALL switch to edit mode on click/tap, and changes SHALL be locally saveable.

#### Scenario: Plan card renders with all sections
- **WHEN** plan is successfully generated
- **THEN** the Drawer displays a plan card with sections: period, weekly goals, daily tasks, barrier interventions, and motivation tips

#### Scenario: Teacher edits a field
- **WHEN** teacher clicks on "第1周目标" field
- **THEN** the field becomes editable (contenteditable or input), teacher types new content, and on blur the change is saved to the local plan object

#### Scenario: Teacher saves modifications
- **WHEN** teacher has made edits and clicks "保存修改"
- **THEN** the updated plan is saved to localStorage and a brief "已保存" confirmation appears

### Requirement: Plan can be sent to student from the editor

The plan editor SHALL include a "发给学生" button that persists the plan to SqliteStore via `POST /api/diagnosis/learning-plan/apply/{student_id}` and notifies the teacher of success or failure.

#### Scenario: Plan sent successfully
- **WHEN** teacher clicks "发给学生" with a valid plan loaded
- **THEN** the plan is sent to the backend, persisted, and a confirmation message "已发送给XXX" is shown

#### Scenario: Send fails
- **WHEN** the apply API returns an error
- **THEN** an error message is shown with a "重试" option

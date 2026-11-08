## ADDED Requirements

### Requirement: MultiAgentState includes shared_context
The MultiAgentState SHALL extend MessagesState with a shared_context dict field.

#### Scenario: shared_context initialized as empty dict
- **WHEN** a new conversation starts
- **THEN** shared_context is an empty dict

### Requirement: Sub-agent results update shared_context
Student and class information discovered by a sub-agent SHALL be written to shared_context.

#### Scenario: Diagnosis extracts student info
- **WHEN** diagnosis_expert successfully diagnoses student "S001"
- **THEN** shared_context is updated with student_id="S001", student_name, and barrier_type

#### Scenario: Subsequent agent uses shared context
- **WHEN** shared_context contains student_id="S001" and exam_expert is invoked
- **THEN** the agent_query includes the shared context as injected preamble

### Requirement: shared_context is per-invocation isolated
Each invoke() / astream_events() SHALL create its own shared_context instance.

#### Scenario: Concurrent requests don't cross-contaminate
- **WHEN** two concurrent requests each diagnose different students
- **THEN** each request's shared_context contains only its own student info

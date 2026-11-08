# memory-tools Specification

## Purpose
TBD - created by archiving change chemai-architecture-overhaul. Update Purpose after archive.
## Requirements
### Requirement: memory_student_get tool available to Agent
The Agent SHALL have access to a `memory_student_get` tool that retrieves historical diagnosis records and learning plans for a given student from the SqliteStore.

#### Scenario: Retrieve existing student diagnosis
- **WHEN** Agent calls `memory_student_get(student_id="202610101")`
- **THEN** the tool returns the student's diagnosis history (up to 5 records) and current learning plan

#### Scenario: Student not found
- **WHEN** Agent calls `memory_student_get` for a student ID with no stored memories
- **THEN** the tool returns an empty result without error

### Requirement: memory_teacher_get tool available to Agent
The Agent SHALL have access to a `memory_teacher_get` tool that retrieves teaching preferences for a given teacher from the SqliteStore.

#### Scenario: Retrieve teacher preferences
- **WHEN** Agent calls `memory_teacher_get(teacher_id="teacher_liu")`
- **THEN** the tool returns the teacher's stored preferences (difficulty preference, teaching style, etc.)

### Requirement: Memory tools registered in TOOLS list
Both `memory_student_get` and `memory_teacher_get` SHALL be registered in the Agent's `TOOLS` list, making them available in the ReAct loop.

#### Scenario: Agent dispatches to memory tool
- **WHEN** a user asks "张三之前的学习诊断结果是什么"
- **THEN** the Agent calls `memory_student_get` as part of its ReAct loop


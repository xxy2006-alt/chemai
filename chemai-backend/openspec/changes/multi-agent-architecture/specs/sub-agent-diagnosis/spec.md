## ADDED Requirements

### Requirement: Diagnosis expert analyzes student learning barriers
The diagnosis_expert sub-agent SHALL have access to diagnose_barrier, show_diagnosis, and assign_adaptive_practice tools.

#### Scenario: Diagnose individual student
- **WHEN** diagnosis_expert is queried with "诊断张三的学习障碍"
- **THEN** it invokes diagnose_barrier with student_name="张三"

#### Scenario: Show diagnosis panel with charts
- **WHEN** diagnosis_expert is queried with "展示诊断结果"
- **THEN** it invokes show_diagnosis and returns _component with component="diagnosis"

#### Scenario: Assign adaptive practice
- **WHEN** diagnosis_expert is queried with "给张三布置针对性练习"
- **THEN** it invokes assign_adaptive_practice with the student's barrier info

### Requirement: Diagnosis expert extracts shared context
The diagnosis_expert SHALL include student_id, student_name, and barrier_type in its output JSON for shared context.

#### Scenario: Student info in output
- **WHEN** diagnose_barrier succeeds for student "S001"
- **THEN** output JSON contains student_id="S001", student_name, and barrier_type

### Requirement: Diagnosis expert requires approval for destructive actions
The diagnosis_expert SHALL have request_approval and require approval before assign_adaptive_practice.

#### Scenario: Approval required before assignment
- **WHEN** diagnosis_expert attempts assign_adaptive_practice without prior approval
- **THEN** the call is blocked with requires_approval_blocked=True

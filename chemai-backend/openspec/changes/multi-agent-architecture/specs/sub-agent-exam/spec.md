## ADDED Requirements

### Requirement: Exam expert triggers inline exam workbench
The exam_expert sub-agent SHALL have access to show_exam_workbench and save_to_bank tools.

#### Scenario: Show exam workbench with parameters
- **WHEN** exam_expert is queried with "出5道氧化还原选择题，中等难度"
- **THEN** it invokes show_exam_workbench with knowledge_points, difficulty, and question_types

#### Scenario: Save generated questions to bank
- **WHEN** user has generated questions and says "保存到题库"
- **THEN** exam_expert invokes save_to_bank with the generated questions

### Requirement: Exam expert returns _component for inline panel
The exam_expert SHALL include a _component key in its output JSON when show_exam_workbench is called.

#### Scenario: _component in output
- **WHEN** show_exam_workbench succeeds
- **THEN** the output JSON contains _component with component="exam-workbench" and params

### Requirement: Exam expert has own GuardState
The exam_expert SHALL have its own GuardState for deduplication and call limits.

#### Scenario: Duplicate save blocked
- **WHEN** exam_expert invokes save_to_bank twice with identical args
- **THEN** the second call is blocked

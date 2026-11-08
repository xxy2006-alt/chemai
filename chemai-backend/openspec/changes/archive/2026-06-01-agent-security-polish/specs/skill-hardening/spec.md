## ADDED Requirements

### Requirement: weekly_report SHALL verify student access
Before querying student data, `weekly_report` SHALL check that the current persona is "parent" and the requested student_id belongs to the authenticated parent. If the persona is not "parent", SHALL return an error.

#### Scenario: Parent accesses own child — allowed
- **WHEN** parent persona calls weekly_report with their bound student_id
- **THEN** the skill SHALL execute and return the report

#### Scenario: Teacher accesses weekly_report — denied
- **WHEN** teacher persona calls weekly_report (teacher is not in parent persona's available_skills, but this catches code-level bypass)
- **THEN** the skill SHALL return error: "每周报告仅限家长使用"

### Requirement: diagnose SHALL validate class_id in class mode
When `diagnose_barrier` is called with a class_id, the skill SHALL verify the class exists before querying. If the class does not exist, SHALL return an error rather than querying with an invalid class_id.

#### Scenario: Valid class_id
- **WHEN** diagnose_barrier is called with an existing class_id
- **THEN** the diagnosis SHALL execute normally

#### Scenario: Invalid class_id
- **WHEN** diagnose_barrier is called with a non-existent class_id
- **THEN** the skill SHALL return error: "班级不存在"

### Requirement: practice SHALL remove fragile private imports
`assign_adaptive_practice` SHALL NOT import private functions (`_calculate_zpd_difficulty`, `_get_weak_kps`, `_get_dominant_barrier`) from `app.api.practice`. Instead, it SHALL duplicate the necessary logic inline or call public API endpoints.

#### Scenario: No private function imports
- **WHEN** `app.api.practice` is refactored and private functions are renamed
- **THEN** `assign_adaptive_practice` SHALL continue to work without modification

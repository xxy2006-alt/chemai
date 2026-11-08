## ADDED Requirements

### Requirement: diagnose_barrier writes results to SqliteStore
The `diagnose_barrier` tool SHALL automatically persist diagnosis results to the SqliteStore after completing the diagnosis, with upsert semantics (max 5 entries per student).

#### Scenario: Successful diagnosis persisted
- **WHEN** `diagnose_barrier` completes a barrier diagnosis for student `202610101`
- **THEN** the result (barrier_type, weak_knowledge_points, timestamp) is written to namespace `("student", "202610101", "diagnosis")`

#### Scenario: Write failure does not block response
- **WHEN** Store write fails (e.g., connection error)
- **THEN** the diagnosis result is still returned to the caller and a warning is logged

### Requirement: weekly_report writes results to SqliteStore
The `weekly_report` tool SHALL persist report summaries to the SqliteStore after generation.

#### Scenario: Weekly report persisted
- **WHEN** `weekly_report` generates a report for a class
- **THEN** the report summary is written to SqliteStore under the class namespace

### Requirement: assign_adaptive_practice writes results to SqliteStore
The `assign_adaptive_practice` tool SHALL persist assignment records to the SqliteStore.

#### Scenario: Practice assignment persisted
- **WHEN** `assign_adaptive_practice` creates a practice task for a student
- **THEN** the assignment record is written to SqliteStore

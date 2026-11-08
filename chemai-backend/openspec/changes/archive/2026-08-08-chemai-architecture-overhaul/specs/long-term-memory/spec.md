## ADDED Requirements

### Requirement: SqliteStore initialized at application startup
The system SHALL initialize a LangGraph `AsyncSqliteStore` backed by `chemai_store.db` during FastAPI startup and make it available to agent invocations.

#### Scenario: Store created on first startup
- **WHEN** the application starts and no `chemai_store.db` exists
- **THEN** a new SqliteStore is created and ready for read/write operations

#### Scenario: Store persisted across restarts
- **WHEN** the application restarts
- **THEN** previously stored data in `chemai_store.db` is loaded and accessible

### Requirement: Namespace-based organization for long-term memory
The SqliteStore SHALL organize data using hierarchical namespaces: `("student", <id>, "diagnosis")` for diagnosis history, `("student", <id>, "learning_plan")` for learning plans, and `("teacher", <id>, "preferences")` for teacher preferences.

#### Scenario: Store student diagnosis
- **WHEN** a diagnosis result for student `202610101` is stored
- **THEN** it is accessible via namespace `("student", "202610101", "diagnosis")` with time-ordered keys

#### Scenario: Store teacher preference
- **WHEN** teacher `liu` sets their preferred difficulty to "medium"
- **THEN** it is stored under `("teacher", "liu", "preferences")` with key `"current"`

### Requirement: Upsert strategy for memory events
The system SHALL retain at most 5 entries per user per event type, deleting the oldest entry when inserting a 6th one.

#### Scenario: Sixth diagnosis triggers deletion
- **WHEN** a 6th diagnosis is written for the same student
- **THEN** the oldest diagnosis is deleted before the new one is stored

#### Scenario: Same-type update replaces latest
- **WHEN** a learning plan is updated for a student
- **THEN** the existing `"current"` key under `("student", <id>, "learning_plan")` is overwritten

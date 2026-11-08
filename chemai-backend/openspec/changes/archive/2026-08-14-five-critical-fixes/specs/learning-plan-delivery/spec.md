## MODIFIED Requirements

### Requirement: GET learning-plan reads from SqliteStore before generating

The `GET /api/diagnosis/learning-plan/{student_id}` endpoint SHALL check SqliteStore (namespace `("student", student_id, "learning_plan")`, key `"current"`) after checking `_plan_cache` and before falling back to LLM generation.

#### Scenario: Plan found in cache
- **WHEN** student requests plan and `_plan_cache` has a valid entry
- **THEN** cached plan is returned immediately

#### Scenario: Plan found in SqliteStore after cache miss
- **WHEN** student requests plan, `_plan_cache` miss, but SqliteStore has a persisted plan
- **THEN** the persisted plan is returned and added to `_plan_cache`

#### Scenario: No plan anywhere, LLM generation fallback
- **WHEN** student requests plan, cache miss, SqliteStore miss
- **THEN** a new plan is generated via LLM, stored in cache, and returned

### Requirement: POST apply writes synchronously

The `POST /api/diagnosis/learning-plan/apply/{student_id}` endpoint SHALL await the SqliteStore write before returning HTTP 200.

#### Scenario: Plan persisted before response
- **WHEN** teacher sends a learning plan
- **THEN** the SqliteStore write completes before the 200 response is returned

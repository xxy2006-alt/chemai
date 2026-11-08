## ADDED Requirements

### Requirement: Skill execution SHALL be logged to JSONL audit file
Every skill execution (success or failure) via `registry.execute()` SHALL append a JSON line to `data/audit/agent_audit.jsonl` containing: timestamp, persona, skill_name, args (sanitized), result_summary (first 200 chars), duration_ms, and error (if any).

#### Scenario: Successful skill call logged
- **WHEN** `search_exam_bank` is called with `{keyword: "盐类水解"}`
- **THEN** a JSONL line SHALL be appended with error=null and result_summary containing the truncated result

#### Scenario: Failed skill call logged
- **WHEN** `diagnose_barrier` raises an exception
- **THEN** a JSONL line SHALL be appended with error=<exception message>

### Requirement: Audit log SHALL maintain in-memory ring buffer
`AuditLogger` SHALL maintain a `collections.deque(maxlen=100)` ring buffer for the last 100 audit entries, accessible via `AuditLogger.recent()` for debugging.

#### Scenario: Ring buffer holds last 100 entries
- **WHEN** 150 skill calls are made
- **THEN** `AuditLogger.recent()` SHALL return the latest 100 entries only

### Requirement: Sensitive args SHALL be sanitized
Before writing args to the audit log, known sensitive field names (password, phone, parent_phone, token, api_key) SHALL have their values replaced with `"***"`.

#### Scenario: Password field sanitized
- **WHEN** skill args contain `{password: "secret123"}`
- **THEN** the logged args SHALL contain `{password: "***"}`

#### Scenario: Non-sensitive args preserved
- **WHEN** skill args contain `{student_id: "202610101", keyword: "盐类水解"}`
- **THEN** the logged args SHALL preserve the original values unchanged

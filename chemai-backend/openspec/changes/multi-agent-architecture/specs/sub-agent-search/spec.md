## ADDED Requirements

### Requirement: Search expert handles knowledge and exam bank queries
The search_expert sub-agent SHALL have access to search_exam_bank, web_search, and list_knowledge tools.

#### Scenario: Search exam bank by keyword
- **WHEN** search_expert is queried with "搜索氧化还原反应的真题"
- **THEN** it invokes search_exam_bank with keyword="氧化还原反应"

#### Scenario: Web search for latest info
- **WHEN** search_expert is queried with "2025年高考化学大纲有什么变化"
- **THEN** it invokes web_search to get up-to-date information

### Requirement: Search expert has GuardState for dedup and limits
The search_expert SHALL have its own GuardState instance for deduplication and call limits.

#### Scenario: Duplicate search calls are blocked
- **WHEN** search_expert invokes search_exam_bank twice with identical args
- **THEN** the second call is blocked with dedup_skipped=True

#### Scenario: Search call limit enforced
- **WHEN** search_expert invokes search_exam_bank more than 3 times
- **THEN** subsequent calls are blocked with limit_exceeded=True

### Requirement: Search expert outputs JSON with result key
The search_expert SHALL output a JSON object with at minimum a "result" key.

#### Scenario: Valid JSON output
- **WHEN** search_expert completes a search
- **THEN** the final message is parseable JSON containing "result"

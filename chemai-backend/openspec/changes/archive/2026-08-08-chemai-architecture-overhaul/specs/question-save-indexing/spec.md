## ADDED Requirements

### Requirement: save_to_bank synchronizes to exam_bank_service memory
When `save_to_bank` saves AI-generated questions to SQLite, it SHALL also add each question to `exam_bank_service.questions` in-memory list, making them searchable via `search_questions()`.

#### Scenario: Save single question to bank
- **WHEN** Agent calls `save_to_bank` with one valid question
- **THEN** the question is inserted into SQLite `questions` table AND added to `exam_bank_service.questions`

#### Scenario: Save multiple questions
- **WHEN** Agent calls `save_to_bank` with 5 questions
- **THEN** all 5 questions are available in both SQLite and exam_bank_service.questions immediately

### Requirement: save_to_bank indexes to ChromaDB
When `save_to_bank` saves questions, it SHALL incrementally add them to the ChromaDB `exam_questions` collection.

#### Scenario: Index new question for vector search
- **WHEN** Agent saves an AI-generated question about "盐类水解"
- **THEN** the question is indexed in ChromaDB and searchable via `search_similar("盐类水解")`

#### Scenario: Duplicate question idempotency
- **WHEN** the same question (by exam_id) is saved again
- **THEN** the ChromaDB entry is updated rather than duplicated

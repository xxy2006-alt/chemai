## ADDED Requirements

### Requirement: ChromaDB uses dashscope text-embedding-v3
The ChromaDB vector index SHALL use dashscope `text-embedding-v3` API (1024-dim) as the primary embedding source, replacing the MD5-based pseudo-embedding.

#### Scenario: Successful embedding generation
- **WHEN** `_get_embedding(text)` is called with chemical exam content
- **THEN** dashscope API returns a 1024-dimensional float vector

#### Scenario: API failure fallback
- **WHEN** dashscope API call fails (network error or quota exceeded)
- **THEN** the system falls back to MD5-based pseudo-embedding and logs a warning

#### Scenario: Dimension mismatch recovery
- **WHEN** the existing ChromaDB collection has a different embedding dimension than 1024
- **THEN** the collection is deleted and recreated with the correct dimension

### Requirement: search_questions supports vector semantic recall
The `ExamBankService.search_questions()` method SHALL accept a `use_vector` parameter that enables ChromaDB semantic recall before structured filtering.

#### Scenario: Vector search with keyword
- **WHEN** `search_questions(keyword="氧化还原计算", use_vector=True)` is called
- **THEN** ChromaDB returns semantically similar exam IDs first, then results are filtered by year/difficulty/source

#### Scenario: Linear scan fallback
- **WHEN** `search_questions(use_vector=False)` is called or no keyword provided
- **THEN** results use the existing linear scan with keyword substring matching

### Requirement: Agent search_exam_bank uses vector search by default
The `search_exam_bank` agent tool SHALL default to `use_vector=True` when querying the exam bank.

#### Scenario: Agent searches with natural language
- **WHEN** Agent calls `search_exam_bank(keyword="乙醇的溶解性")`
- **THEN** the underlying `search_questions` call uses vector semantic search

### Requirement: ChromaDB index built automatically on startup
The application SHALL automatically build the ChromaDB vector index from `exam_bank_service.questions` during startup.

#### Scenario: Startup with existing exam bank data
- **WHEN** the FastAPI application starts and exam_bank_service has loaded questions
- **THEN** `vector_search_service.build_index_from_exam_bank()` is called and the question count is logged

#### Scenario: Startup with empty exam bank
- **WHEN** the exam_bank_service has zero questions loaded
- **THEN** index build completes with zero indexed without error

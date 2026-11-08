## ADDED Requirements

### Requirement: MemoryStack SHALL detect when compression is needed
`MemoryStack` SHALL expose a `needs_compression()` method that returns `true` when `len(self.working) > 15`.

#### Scenario: Compression not needed for short conversations
- **WHEN** working memory has 10 turns
- **THEN** `needs_compression()` returns `false`

#### Scenario: Compression needed for long conversations
- **WHEN** working memory has 17 turns
- **THEN** `needs_compression()` returns `true`

### Requirement: MemoryStack SHALL compress oldest turns into archive
`MemoryStack` SHALL expose a `compress_oldest(n)` method that takes the oldest N turns, formats them as a text summary (format: `[role]: content[:200]`), appends to `self.episodic["conversation_archive"]`, and removes those turns from working memory.

#### Scenario: Compression reduces working memory size
- **WHEN** `compress_oldest(8)` is called on working memory with 17 turns
- **THEN** working memory SHALL have 9 turns remaining, and `episodic["conversation_archive"]` SHALL contain text summaries of the removed 8 turns

#### Scenario: Compression with n=0 is a no-op
- **WHEN** `compress_oldest(0)` is called
- **THEN** working memory SHALL be unchanged

### Requirement: Agent SHALL check compression before each run
The `ChemAgent._maybe_compress()` method SHALL be called at the start of `run()` and `run_stream()`. When compression is needed, it SHALL call `memory.compress_oldest(8)`.

#### Scenario: Auto-compression on long conversation
- **WHEN** a new message arrives and working memory has 18 turns
- **THEN** `_maybe_compress()` SHALL trigger `compress_oldest(8)` before the think phase begins

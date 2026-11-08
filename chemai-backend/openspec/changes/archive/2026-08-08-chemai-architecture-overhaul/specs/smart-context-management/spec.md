## ADDED Requirements

### Requirement: TrimMessages strategy for context management
The system SHALL replace hardcoded 30-message truncation with a TrimMessages strategy that retains the last 6 messages unconditionally and conditionally retains messages containing student/diagnosis/exam-related keywords.

#### Scenario: Conversation under threshold
- **WHEN** a conversation has fewer than 30 messages
- **THEN** no messages are removed or summarized

#### Scenario: Conversation exceeds threshold with no key content in middle
- **WHEN** a conversation has 35 messages and the middle messages contain only greetings and tool confirmation outputs
- **THEN** those middle messages are discarded, keeping the last 6 messages intact

#### Scenario: Conversation with diagnosis data in middle
- **WHEN** a conversation has 35 messages and messages 10-15 contain barrier diagnosis results (关键词: "诊断", "障碍")
- **THEN** messages 10-15 are conditionally retained alongside the last 6 messages

### Requirement: LLM summarization at 15 turns
The system SHALL trigger an LLM-based summary when the conversation reaches 30 messages (15 turns), compressing messages not retained by Trim into a SystemMessage summary.

#### Scenario: Trigger summary at 30 messages
- **WHEN** a conversation accumulates 30 messages and non-retained messages exceed 10
- **THEN** the LLM generates a Chinese summary of the non-retained messages and injects it as `SystemMessage("[对话摘要] ...")`

#### Scenario: Summary retains key information
- **WHEN** summary is generated from a conversation about student barrier diagnosis
- **THEN** the summary MUST mention the student name, diagnostic result, and weak knowledge points

### Requirement: pydantic_ai message types removed from channels
The `_conversations` dict SHALL no longer store pydantic_ai `ModelRequest`/`ModelResponse` message history. The `student_id` SHALL be sourced from `ChatRequest.student_id` only.

#### Scenario: Gateway classifier without pydantic_ai history
- **WHEN** Gateway classifier needs conversation context
- **THEN** it extracts the last 2 turns from LangGraph checkpoint messages as plain text

#### Scenario: Reset endpoint clears checkpoint
- **WHEN** `/api/agent/chat/langgraph/reset` is called
- **THEN** both the `_conversations` entry AND the LangGraph checkpoint state are cleared

### Requirement: MemoryStack dead code removed
The `to_pydantic_messages()` and `from_pydantic_messages()` methods in `MemoryStack` SHALL be removed as dead code.

#### Scenario: MemoryStack still usable
- **WHEN** `MemoryStack.add_turn("user", "hello")` is called
- **THEN** the working memory deque still operates correctly

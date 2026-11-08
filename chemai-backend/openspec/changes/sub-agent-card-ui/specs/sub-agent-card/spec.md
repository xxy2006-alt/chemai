## ADDED Requirements

### Requirement: Sub-agent result renders as collapsible card
The frontend SHALL render sub-agent output as a collapsible card in the chat, not as inline text.

#### Scenario: Card appears on subagent_start
- **WHEN** SSE event `{"type": "subagent_start", "agent": "tutor_expert"}` is received
- **THEN** a card is inserted into the chat with agent name and running indicator

#### Scenario: Card shows tool timeline in real-time
- **WHEN** subagent_tool events arrive with agent name matching the card
- **THEN** the card's timeline section appends tool call entries in real-time

#### Scenario: Card completes on subagent_end
- **WHEN** `{"type": "subagent_end", "agent": "tutor_expert", "elapsed": 5, "tool_count": 1, "result": "..."}` is received
- **THEN** card status changes to done, result text is stored in collapsible section, and card auto-collapses after 500ms

### Requirement: Card is collapsible with default collapsed state
The card SHALL be expandable/collapsible via click on the title bar.

#### Scenario: Click toggles expansion
- **WHEN** user clicks the card's title bar
- **THEN** the card body expands or collapses with animation

#### Scenario: Result section defaults to collapsed
- **WHEN** card is expanded after completion
- **THEN** the result section ("结果") is collapsed by default

### Requirement: Card handles error state
When a sub-agent fails, the card SHALL display an error state.

#### Scenario: Card shows error on subagent_end with error
- **WHEN** `{"type": "subagent_end", "error": true, "result": "{\"error\": true, ...}"}` is received
- **THEN** card title bar shows red error indicator, result section shows error message

#### Scenario: Tool failure in timeline
- **WHEN** a subagent_tool event arrives with `success: false`
- **THEN** the timeline entry shows a red failure indicator instead of green checkmark

### Requirement: Empty result is handled gracefully
When a sub-agent produces no text result, the card SHALL not show an empty result section.

#### Scenario: No result section when result is empty
- **WHEN** `subagent_end.result` is empty string or null
- **THEN** the result section is hidden, only the title bar and timeline are shown

### Requirement: Card does not block main dialog
Sub-agent cards SHALL appear inline in the chat flow without replacing or hiding other messages.

#### Scenario: Normal messages flow around card
- **WHEN** a sub-agent card is inserted
- **THEN** messages before and after the card remain visible and scrollable

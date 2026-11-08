## ADDED Requirements

### Requirement: SSE emits think markers around tool execution
The SSE stream SHALL emit `data: <think>` before tool/sub-agent execution begins and `data: </think>` after it completes.

#### Scenario: Think block wraps sub-agent execution
- **WHEN** coordinator routes to tutor_expert and sub-agent executes
- **THEN** `data: <think>` is emitted before sub-agent events, `data: </think>` after

#### Scenario: Tool events stay inside think block
- **WHEN** `tool_call` and `tool_result` events are emitted during sub-agent execution
- **THEN** they appear between `<think>` and `</think>` markers

### Requirement: Frontend renders think block as collapsible panel
The frontend SHALL render content between `<think>` and `</think>` in a collapsible panel, not inline in the dialog.

#### Scenario: Panel created on think start
- **WHEN** `data: <think>` is received
- **THEN** a collapsible panel appears with "思考过程" header and running indicator

#### Scenario: Panel collapsed on think end
- **WHEN** `data: </think>` is received
- **THEN** panel collapses to summary line showing tool count and elapsed time

### Requirement: Text events after think stream to dialog
Text events emitted after `</think>` SHALL render as streaming text in the main dialog bubble.

#### Scenario: Answer streams after think
- **WHEN** `data: </think>` has been received and `text` events follow
- **THEN** text renders character-by-character in the dialog bubble

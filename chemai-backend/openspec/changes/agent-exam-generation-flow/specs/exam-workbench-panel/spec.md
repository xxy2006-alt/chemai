## MODIFIED Requirements

### Requirement: Panel "AI 出题" button uses Agent resume

The "AI 出题" button in the exam workbench panel SHALL submit parameters to the Agent via the resume endpoint instead of calling the REST API directly.

#### Scenario: Button click submits to resume

- **WHEN** user clicks "AI 出题" in the exam workbench panel
- **THEN** the button collects all panel parameters (kps, difficulty, types, variant)
- **AND** sends them via `POST /api/agent/chat/langgraph/resume` with the current conversation_id
- **AND** the panel shows a loading state while the Agent processes the request
- **AND** SSE `component` events update the panel's question list in-place

#### Scenario: Panel update on question generation result

- **WHEN** Agent returns `generate_questions` result via SSE `component` event
- **THEN** the existing exam workbench panel is updated with the new questions
- **AND** the loading state is cleared
- **AND** save/delete buttons are bound to the new question cards

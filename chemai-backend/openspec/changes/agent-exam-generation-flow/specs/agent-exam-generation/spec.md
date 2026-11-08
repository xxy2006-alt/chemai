## ADDED Requirements

### Requirement: Agent-driven exam question generation

Agent SHALL execute exam question generation via the `generate_questions` tool within its ReAct loop, not delegate it to the frontend panel.

#### Scenario: Full parameters provided

- **WHEN** user says "出5道氧化还原选择题，中等难度"
- **THEN** Agent extracts all required parameters from the message
- **AND** Agent calls `generate_questions(knowledge_points=["氧化还原"], difficulty="medium", question_types=[{val:"single_choice", qty:5}])`
- **AND** the tool returns questions with a `_component` that renders the exam workbench panel

#### Scenario: Incomplete parameters

- **WHEN** user says "帮我出几道题" without specifying knowledge points or question types
- **THEN** Agent calls `show_exam_workbench` to open the configuration panel
- **AND** known parameters (if any) are pre-filled in the panel
- **AND** user completes parameters and clicks "AI 出题"

#### Scenario: Resume with panel parameters

- **WHEN** user clicks "AI 出题" in the exam workbench panel
- **THEN** the frontend sends parameters via `POST /api/agent/chat/langgraph/resume`
- **AND** Agent receives the resume and calls `generate_questions` with the panel-collected parameters
- **AND** the tool result updates the existing panel via `_component` SSE event

#### Scenario: Blueprint-based variant generation

- **WHEN** user selects a blueprint question AND clicks "AI 出题"
- **THEN** `variant_qid` and `variant_source` are passed in the resume message
- **AND** `generate_questions` uses the blueprint question as RAG context
- **AND** generated questions are variants derived from the blueprint

### Requirement: Tool call visibility in conversation

Every Agent tool call in the exam generation flow SHALL produce visible tool cards in the chat UI.

#### Scenario: Tool card for generate_questions

- **WHEN** Agent calls `generate_questions`
- **THEN** a tool card appears showing "generate_questions" with running state
- **AND** when the tool completes, the card shows "完成" and expands to show results

### Requirement: Conversation history preservation

Exam generation interactions SHALL be saved to conversation history, including when the exam panel is shown.

#### Scenario: History saved with panel

- **WHEN** an exam workbench panel is rendered (via `show_exam_workbench` or `generate_questions`)
- **THEN** the conversation history entry is saved with the agent response
- **AND** the sidebar shows the conversation title derived from the user's message

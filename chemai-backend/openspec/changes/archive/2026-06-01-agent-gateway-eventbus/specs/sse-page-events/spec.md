## ADDED Requirements

### Requirement: Agent SHALL emit navigate SSE event
When the intent classifier returns `intent: "page_action"` or `intent: "hybrid"` with a non-null page field, the agent SHALL emit a `navigate` SSE event: `{"type": "navigate", "page": "<page_name>", "params": {...}}`.

#### Scenario: Navigate after hybrid execution
- **WHEN** intent is "hybrid" with page "exam-v2", and all skill executions complete
- **THEN** a navigate SSE event SHALL be emitted before the `done` event

#### Scenario: Navigate without skills (page_action)
- **WHEN** intent is "page_action" with page "students" and no tools
- **THEN** a navigate SSE event SHALL be emitted immediately, followed by `done`

#### Scenario: No navigate for chat intent
- **WHEN** intent is "chat" with page null
- **THEN** no navigate SSE event SHALL be emitted

### Requirement: Agent SHALL emit populate SSE event
When skill execution results contain data relevant to the target page, the agent SHALL emit `populate` SSE events: `{"type": "populate", "target": "<element_id>", "data": {...}}`.

#### Scenario: Populate exam page with generated questions
- **WHEN** generate_questions skill returns question data and target page is "exam-v2"
- **THEN** a populate event SHALL be emitted with `target: "questionList"` and the question data

#### Scenario: Populate diagnosis page with results
- **WHEN** diagnose_barrier skill returns diagnosis data and target page is "diagnosis"
- **THEN** a populate event SHALL be emitted with `target: "diagnosisResult"` and the diagnosis data

### Requirement: Agent SHALL emit action SSE event
The agent SHALL emit `action` SSE events for post-navigation operations: `{"type": "action", "action": "<action_name>", "payload": {...}}`.

#### Scenario: Action to open student drawer
- **WHEN** intent target is a specific student
- **THEN** an action event SHALL be emitted with `action: "openStudentDrawer"` and `payload: {student_id: "..."}`

### Requirement: Frontend SHALL handle new SSE event types
The `agent.js` SSE event handler SHALL process `navigate`, `populate`, and `action` events by storing them in `sessionStorage.chemai_navigate`.

#### Scenario: Navigate event stored in sessionStorage
- **WHEN** a navigate event is received
- **THEN** `sessionStorage.chemai_navigate` SHALL contain `{page: "<page>", params: {...}, data: {}, actions: []}`

#### Scenario: Multiple populate events are merged
- **WHEN** two populate events are received for different targets
- **THEN** both targets SHALL be present in `chemai_navigate.data`

#### Scenario: Stream ends, navigate triggers page jump
- **WHEN** the SSE stream ends and `sessionStorage.chemai_navigate` is set
- **THEN** `window.location.href` SHALL navigate to the target page URL

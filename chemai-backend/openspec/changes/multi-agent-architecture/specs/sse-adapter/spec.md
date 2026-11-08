## ADDED Requirements

### Requirement: SSE adapter suppresses sub-agent internal events
The LangGraphSSEAdapter SHALL suppress on_tool_start and on_tool_end events from sub-agent internal nodes.

#### Scenario: Sub-agent internal tool call not emitted
- **WHEN** search_expert invokes search_exam_bank internally
- **THEN** no tool_call SSE event is emitted for search_exam_bank

#### Scenario: Coordinator-level tool call still emitted
- **WHEN** coordinator routes to a sub-agent
- **THEN** a properly categorized event is emitted for the routing action

### Requirement: SSE adapter reads component and route from state
The finalize() method SHALL receive last_component and last_route from MultiAgentState values, not from global variables.

#### Scenario: Component event emitted from state
- **WHEN** exam_expert returns _component in its output
- **THEN** finalize() reads last_component from state and emits a component SSE event

#### Scenario: Route event emitted from state
- **WHEN** a tool returns _route with navigate=True
- **THEN** finalize() reads last_route from state and emits navigate + populate + action SSE events

### Requirement: SSE events format backward compatible
The SSE JSON format SHALL remain compatible with the current frontend agent.js.

#### Scenario: Text events unchanged
- **WHEN** coordinator generates a text response
- **THEN** SSE emits {"type": "text", "content": "..."} events

#### Scenario: Done event unchanged
- **WHEN** stream completes
- **THEN** SSE emits {"type": "done"} followed by "[DONE]" sentinel

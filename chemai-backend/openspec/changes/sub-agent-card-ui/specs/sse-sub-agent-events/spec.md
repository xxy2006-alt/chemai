## ADDED Requirements

### Requirement: SSE emits subagent_start on sub-agent entry
The LangGraphSSEAdapter SHALL emit `subagent_start` event when a sub-agent node begins execution.

#### Scenario: subagent_start emitted
- **WHEN** the coordinator graph enters a sub-agent node (e.g., tutor_expert)
- **THEN** SSE emits `{"type": "subagent_start", "agent": "tutor_expert", "started_at": <timestamp>}`

### Requirement: SSE emits subagent_tool for sub-agent internal tools
The LangGraphSSEAdapter SHALL emit `subagent_tool` events for tool calls within a sub-agent.

#### Scenario: Tool start emitted as subagent_tool
- **WHEN** a sub-agent internally calls balance_equation
- **THEN** SSE emits `{"type": "subagent_tool", "agent": "tutor_expert", "phase": "start", "name": "balance_equation"}`

#### Scenario: Tool end emitted as subagent_tool
- **WHEN** balance_equation completes within a sub-agent
- **THEN** SSE emits `{"type": "subagent_tool", "agent": "tutor_expert", "phase": "end", "name": "balance_equation", "success": true}`

### Requirement: SSE emits subagent_end on sub-agent completion
The LangGraphSSEAdapter SHALL emit `subagent_end` when a sub-agent node completes. The event is assembled in `finalize()` from adapter's stored `_sub_agent_start`/`_active_sub_agent`/`_tool_count` plus `last_result_text` from graph state.

#### Scenario: subagent_end emitted with result
- **WHEN** the coordinator graph exits a sub-agent node
- **THEN** SSE emits `{"type": "subagent_end", "agent": "tutor_expert", "elapsed": <seconds>, "tool_count": <N>, "result": "<text>", "error": null}`

#### Scenario: subagent_end emitted with error
- **WHEN** the sub-agent raised an exception
- **THEN** SSE emits `{"type": "subagent_end", "agent": "tutor_expert", "elapsed": <seconds>, "tool_count": <N>, "result": "{\"error\": true, \"result\": \"...\"}", "error": true}`

### Requirement: No more text events from sub-agents
Sub-agent result text SHALL NOT be emitted via standard `text` SSE events. It SHALL only appear in `subagent_end.result`.

#### Scenario: No text events during sub-agent execution
- **WHEN** a sub-agent is executing
- **THEN** no `{"type": "text"}` events are emitted for that sub-agent's output

### Requirement: Existing tool_call/tool_result for coordinator tools unchanged
Coordinator-level tool events (route_to_*) SHALL continue to use standard `tool_call`/`tool_result` events.

#### Scenario: Route tool card still shows
- **WHEN** coordinator calls route_to_exam_expert
- **THEN** standard `tool_call`/`tool_result` events are emitted

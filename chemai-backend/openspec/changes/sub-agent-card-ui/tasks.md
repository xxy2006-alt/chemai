## 1. Backend: SSE Adapter — Restructure Suppression Logic

- [ ] 1.1 Replace `phase: processing`/`processing_done` with new event types `subagent_start`/`subagent_end`
- [ ] 1.2 In `on_chain_start` for sub-agent: emit `subagent_start` (agent, started_at), store `_sub_agent_start` and `_active_sub_agent`
- [ ] 1.3 In `on_tool_start`/`on_tool_end` inside sub-agent: emit `subagent_tool` events instead of suppressing (track `_tool_count`)
- [ ] 1.4 In `on_chain_end` for sub-agent: compute `elapsed` from stored `_sub_agent_start`, keep as instance var for `finalize()`; suppress text events and nested chain events
- [ ] 1.5 In `finalize()`: assemble `subagent_end` event from stored `_sub_agent_start`/`_active_sub_agent`/`_tool_count`/elapsed + `result` from graph state `last_result_text`
- [ ] 1.6 Keep `_sub_agent_start`, `_active_sub_agent`, `_tool_count` as instance vars (NOT removed — needed for elapsed/tool_count in finalize)
- [ ] 1.7 Remove text chunk loop from `finalize()` — sub-agent result goes in `subagent_end.result`, not as text events

## 2. Backend: State & Channel Cleanup

- [ ] 2.1 Remove `last_result_text` from `MultiAgentState` in `langgraph_agent.py`
- [ ] 2.2 Remove `last_result_text` assignment from both return paths in `create_sub_agent_node`
- [ ] 2.3 Remove `result_text` parameter from `LangGraphSSEAdapter.finalize()` signature
- [ ] 2.4 Remove `result_text` argument from channel finalize calls (both stream and resume)

## 3. Frontend: Collapsible Card Component

- [ ] 3.1 Add `addSubAgentCard(agent, startedAt)` — creates card DOM, inserts at current bubble position
- [ ] 3.2 Card HTML: title bar (chevron + agent display name + status indicator + elapsed + tool_count), timeline area, collapsible result area
- [ ] 3.3 CSS: `grid-template-rows: 0fr → 1fr` animation for collapse/expand, chevron rotation, status colors (green done / blue running / red error)
- [ ] 3.4 Handle `subagent_start` → create card with running spinner
- [ ] 3.5 Handle `subagent_tool` → append timeline entries to matching card (green checkmark for success, red X for failure)
- [ ] 3.6 Handle `subagent_end` → update card status line, store result, show result section (hidden if empty), auto-collapse after 500ms
- [ ] 3.7 Handle `subagent_end` with `error: true` → show red error indicator in title bar, result section shows error message

## 4. Frontend: Event Handler Updates

- [ ] 4.1 Remove `processing` / `processing_done` phase handling from switch case (lines ~299-317)
- [ ] 4.2 Add cases for `subagent_start`, `subagent_tool`, `subagent_end`
- [ ] 4.3 Card result text uses existing Markdown renderer (reuse `addText`'s markdown logic)

## 5. Version Bump

- [ ] 5.1 Bump `agent.js` version in `index.html`: v=7 → v=8

## 6. Testing

- [ ] 6.1 Test tutor_expert balance equation → card shows with result. Verify zero `type: text` SSE events during sub-agent execution window
- [ ] 6.2 Test exam_expert show_workbench → routing tool_card + sub-agent card both show correctly
- [ ] 6.3 Test collapse/expand — click title bar toggles card body
- [ ] 6.4 Test no duplicate text output in full API response
- [ ] 6.5 Test error state — trigger sub-agent failure, verify card shows red error

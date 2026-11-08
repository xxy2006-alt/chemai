## 1. Multi-Agent State

- [x] 1.1 Define `MultiAgentState(MessagesState)` with fields: shared_context, route_decision, target_agent, agent_query, last_component, last_route, reroute
- [x] 1.2 Implement `_agent_node_cache` lazy init pattern

## 2. Coordinator + Router

- [x] 2.1 Define `RoutingDecision` Pydantic model (agent: Literal[...], query, reasoning)
- [x] 2.2 Implement `coordinator_node` — with_structured_output → RoutingDecision, handle reroute
- [x] 2.3 Implement `router_node` — read RoutingDecision, set target_agent/agent_query, generate response if "respond"
- [x] 2.4 Implement `_route_after_router` conditional edge function
- [x] 2.5 Build coordinator system prompt with routing rules for all 5 sub-agents

## 3. Sub-Agent Nodes

- [x] 3.1 Implement `create_sub_agent_node` factory — wraps `create_react_agent` with GuardState, JSON output contract, error handling, context extraction
- [x] 3.2 Build search_expert node (search_exam_bank, web_search, list_knowledge)
- [x] 3.3 Build exam_expert node (show_exam_workbench, save_to_bank) — extracts _component
- [x] 3.4 Build diagnosis_expert node (diagnose_barrier, show_diagnosis, assign_adaptive_practice) — requires_approval for assign
- [x] 3.5 Build tutor_expert node (chemistry_tutor, simulate_experiment, balance_equation, weekly_report)
- [x] 3.6 Build bank_manager node (list_banks, delete_bank) — requires_approval for delete

## 4. GuardState Migration

- [x] 4.1 Move GuardState instantiation from coordinator to per-sub-agent in `create_sub_agent_node`
- [x] 4.2 Reuse `_make_guarded_tool` and `_make_request_approval_tool` per sub-agent
- [ ] 4.3 Verify `interrupt()` in sub-agent's request_approval bubbles to coordinator graph level

## 5. Graph Assembly

- [x] 5.1 Assemble StateGraph: START → coordinator → router → [5 sub-agent nodes] → coordinator
- [x] 5.2 Add conditional edges from router to all sub-agent nodes + END
- [x] 5.3 Add edges from all sub-agent nodes back to coordinator
- [x] 5.4 Compile graph with shared `_checkpointer`, update `create_chemai_agent` factory

## 6. SSE Adapter

- [x] 6.1 Update `LangGraphSSEAdapter.feed()` — suppress sub-agent internal tool events by metadata.langgraph_node prefix
- [x] 6.2 Update `LangGraphSSEAdapter.finalize()` — read route/component from parameters instead of internal collection
- [x] 6.3 Add fallback: if langgraph_node filtering fails, use config["tags"]

## 7. Channel Updates

- [x] 7.1 Update `_get_or_create_agent` to use new multi-agent factory
- [x] 7.2 Update `agent_chat_langgraph_stream` — extract state values for finalize(last_component, last_route)
- [x] 7.3 Update `agent_chat_langgraph` non-streaming endpoint
- [x] 7.4 Verify `/resume` endpoint works with shared checkpointer interrupt recovery
- [x] 7.5 Verify `/reset` endpoint clears thread checkpoint

## 8. Testing

- [ ] 8.1 Create `--multi-agent` test group: routing accuracy, sub-agent dispatch
- [ ] 8.2 Add multi-agent scenarios to `agent_eval_golden.yaml`
- [ ] 8.3 Test shared_context: diagnosis → exam flow without re-asking student info
- [ ] 8.4 Test interrupt/resume: delete_bank approval flow
- [ ] 8.5 Run all existing evals — verify no regression
- [ ] 8.6 Run 5 workflow scenarios — verify all pass

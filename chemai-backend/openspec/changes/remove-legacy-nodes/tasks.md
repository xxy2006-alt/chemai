## 1. Delete Router Node

- [x] 1.1 Delete `_router_node` function
- [x] 1.2 Delete `_route_after_router` function
- [x] 1.3 Delete `_has_exam_params` function

## 2. Delete Check Node

- [x] 2.1 Delete `_check_node` function
- [x] 2.2 Delete `_route_after_check` function
- [x] 2.3 Delete `TOOL_PREREQUISITES` dict
- [x] 2.4 Delete `VAGUE_KEYWORDS` list and `_is_keyword_too_vague` function

## 3. Delete Pre-flight Gate

- [x] 3.1 Delete `_preflight_check` function from `langgraph_channel.py`
- [x] 3.2 Delete `EXAM_INTENT_TRIGGERS` and `KP_INDICATORS` constants
- [x] 3.3 Remove `_preflight_check` call from `agent_chat_langgraph_stream`

## 4. Cleanup

- [x] 4.1 Remove unused imports (`StateGraph` node types no longer used in old pattern)
- [ ] 4.2 Run full evals to confirm nothing breaks
- [ ] 4.3 Run 5 workflow scenarios

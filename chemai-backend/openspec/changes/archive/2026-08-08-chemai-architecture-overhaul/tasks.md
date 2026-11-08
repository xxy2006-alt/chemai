## 1. Vector Search Integration

- [x] 1.1 Replace `_get_embedding()` in `vector_search.py` with dashscope `text-embedding-v3` API call, fallback to `_pseudo_embedding`
- [x] 1.2 Add dimension mismatch detection in `index_questions()` — drop and recreate ChromaDB collection if dimension ≠ 1024
- [x] 1.3 Add `use_vector` parameter to `ExamBankService.search_questions()` — when True, call `vector_search_service.search_similar()` first, then filter candidates by structured fields
- [x] 1.4 Update `search_exam_bank` in `agent/tools.py` to default `use_vector=True`
- [x] 1.5 Add `vector_search_service.build_index_from_exam_bank()` call in `app/main.py` startup event
- [x] 1.6 Verify: search "乙醇的溶解性" returns T1 via vector path; search "氧化还原计算" finds semantically related results

## 2. Question Save-to-Bank Indexing

- [x] 2.1 After `db.commit()` in `save_to_bank`, add each saved question to `exam_bank_service.questions` via `exam_bank_service.add_question()`
- [x] 2.2 After adding to exam_bank memory, incrementally index each question into ChromaDB via `vector_search_service.index_questions()` with append mode
- [x] 2.3 Add `mode` parameter to `VectorSearchService.index_questions()` — `"replace"` (existing, clears collection) and `"append"` (new, adds to existing)
- [x] 2.4 Verify: save a question via agent, then immediately search via `search_exam_bank` to confirm it appears

## 3. Clean Up pydantic_ai Remnants

- [x] 3.1 Remove `ModelRequest`, `ModelResponse`, `TextPart` imports and message_history build logic from `agent/channel/langgraph_channel.py`
- [x] 3.2 Simplify `_conversations` dict usage — keep only `student_id` metadata, remove `message_history`
- [x] 3.3 Rewrite `_extract_conversation_context()` in `agent/channel/fastapi_sse.py` to accept `list[dict]` instead of pydantic_ai types
- [x] 3.4 Delete `to_pydantic_messages()` and `from_pydantic_messages()` from `agent/memory.py`
- [x] 3.5 Update `/chat/langgraph/reset` to also clear checkpoint state via `agent.aupdate_state(config, {"messages": []})`
- [x] 3.6 Verify: Gateway classifier still works; multiple rounds of conversation maintain continuity

## 4. Smart Context Management

- [x] 4.1 Create `agent/context_manager.py` with `trim_context(agent, config)` function implementing TrimMessages strategy
- [x] 4.2 Implement conditional retention filter — keep messages containing student/diagnosis/exam-related keywords
- [x] 4.3 Implement `_llm_summarize()` for LLM-based conversation summarization at 30-message threshold
- [x] 4.4 Replace three hardcoded 30-message trim blocks in `langgraph_channel.py` with `await trim_context(agent, config)`
- [x] 4.5 Verify: send 35+ messages in a conversation, confirm summary is generated and conversation continuity maintained

## 5. Long-Term Memory (LangGraph SqliteStore)

- [x] 5.1 Initialize `AsyncSqliteStore` from `chemai_store.db` in `app/main.py` startup event, set as module-level singleton
- [x] 5.2 Add `store` parameter to `create_chemai_agent()` in `langgraph_agent_v2.py`, pass to agent invocation config
- [x] 5.3 Pass `store` in `configurable` when invoking agent in `langgraph_channel.py`
- [x] 5.4 Add shutdown hook in `app/main.py` to close SqliteStore connection
- [x] 5.5 Verify: store data persists across application restarts

## 6. Memory Tools for Agent

- [x] 6.1 Implement `memory_student_get(student_id, memory_type)` tool function in `agent/tools.py` — reads from SqliteStore namespaces
- [x] 6.2 Implement `memory_teacher_get(teacher_id)` tool function in `agent/tools.py` — reads teacher preferences from SqliteStore
- [x] 6.3 Register both tools in `TOOLS` list
- [x] 6.4 Create helper `_get_store_context()` to retrieve SqliteStore instance from runtime context in tools
- [x] 6.5 Verify: agent can call `memory_student_get` in response to "查一下张三的诊断历史"

## 7. Diagnosis Writeback

- [x] 7.1 Add Store writeback in `diagnose_barrier` — persist diagnosis results to `("student", id, "diagnosis")` namespace with upsert (max 5)
- [x] 7.2 Add Store writeback in `weekly_report` — persist report summary to `("class", id, "report")` namespace
- [x] 7.3 Add Store writeback in `assign_adaptive_practice` — persist assignment to `("student", id, "practice")` namespace
- [x] 7.4 Ensure writeback failures do not block tool response — catch and log exceptions
- [x] 7.5 Verify: run diagnosis for a student, then call `memory_student_get` to confirm result persisted

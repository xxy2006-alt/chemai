## ADDED Requirements

### Requirement: Agent SHALL iterate through max_turns in non-streaming mode
The `run()` method SHALL not return after the first skill execution. After executing a skill, it SHALL add the observation to working memory, add the episode to episodic memory, and continue the `for turn` loop to re-enter the think phase. The loop SHALL only exit when the LLM returns `action: "reply"` or when `max_turns` is exhausted.

#### Scenario: Single skill, immediate reply
- **WHEN** user asks a question that needs one tool call, and the LLM decides to reply after the first skill result
- **THEN** `run()` executes the skill, observes the result, the LLM chooses `reply` in the next think phase, and the final AgentResponse contains the skill result in content and the skill name in skill_calls

#### Scenario: Two skills chained
- **WHEN** user asks a question that requires two sequential tool calls (e.g., "diagnose Zhang San, then generate questions based on the diagnosis")
- **THEN** `run()` executes skill 1, loops back to think, the LLM observes skill 1's result and chooses to call skill 2, then finally chooses `reply`. The AgentResponse.skill_calls SHALL contain both skill names.

#### Scenario: Max turns exhausted
- **WHEN** the LLM chooses `use_skill` for `max_turns` consecutive iterations without ever choosing `reply`
- **THEN** `run()` SHALL return a fallback response: "抱歉，这个问题比较复杂。请换个方式提问，我会更好地帮助您。"

#### Scenario: Empty tool list — fast path unchanged
- **WHEN** no tools are available (intent classifier returns `tools=None`)
- **THEN** the existing fast path (direct chat_stream) SHALL execute as before, unaffected by the loop fix

### Requirement: Agent SHALL iterate through max_turns in streaming mode
The `run_stream()` method SHALL wrap the tool execution path in a while loop. After executing a skill and receiving its result, it SHALL yield `step` SSE events and return to the think phase instead of immediately entering the reply phase.

#### Scenario: Multi-step streaming with SSE events
- **WHEN** user asks a question requiring two tool calls
- **THEN** the SSE stream SHALL emit: phase:thinking → tool_call:skill1 → tool_result:skill1 → step:{current:1} → phase:thinking → tool_call:skill2 → tool_result:skill2 → step:{current:2} → phase:reply → text chunks → done

#### Scenario: Step counter does not exceed max_turns
- **WHEN** the while loop reaches max_turns iterations
- **THEN** the loop SHALL exit and emit a fallback text message followed by `done`

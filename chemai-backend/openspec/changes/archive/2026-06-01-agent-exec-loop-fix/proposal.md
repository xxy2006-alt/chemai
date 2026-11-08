## Why

ChemAI agent 的 execute loop 有三个 bug 导致它实质上是一个"单步 skill 调用器"：max_turns 循环从未真正迭代、episodic memory 从未被写入、对话上下文无压缩。用户无法说"先诊断张三、再根据诊断出题"——agent 每次只执行一个 skill 就结束。这是 agent 从"聊天工具"升级为"能串联多步工作的 agent"必须首先修复的底盘。

## What Changes

### Bug Fixes

- **Fix multi-turn loop** (`agent/core.py:196-213`): `run()` 方法 skill 执行后不再立即生成 final reply + return，改为 `continue` 回 think phase。skill 结果写入 memory 后被下一轮 think 使用。`run_stream()` 的 tool path 同样改为循环。
- **Fix episodic memory** (`agent/core.py:188,321`): skill 执行成功后调用 `memory.add_episode(skill_name, skill_result)`，使 `build_context()` 自动将前序 skill 结果注入后续 LLM 上下文。
- **Fix context compression** (`agent/memory.py`): 新增 `needs_compression()` 和 `compress_oldest()` 方法。长对话（>15 轮）自动压缩早期轮次为文本摘要存入 episodic memory，防止上下文窗口溢出。

### New Features

- **Multi-step SSE events**: `run_stream()` 支持 think→execute→observe→think 循环。新增 `step` SSE 事件类型，前端可展示多步执行进度。
- **Skill result truncation**: observation 超过 2000 字符时安全截断，防止上下文窗口溢出。
- **System prompt enhancement**: `_build_system_prompt()` 提示 LLM 关注前序 skill 的执行结果。

### Implementation Order

Bug 2 → Bug 3 → Bug 1 → Feature 1 → Feature 2（简单先行，降低冲突风险）

## Capabilities

### New Capabilities

- `multi-turn-exec-loop`: Agent 支持多步 skill 串联执行，think→execute→observe→replan 循环，最多 max_turns 步
- `episodic-memory`: Skill 执行结果自动写入 episodic memory，后续 skill 可通过 `build_context()` 获取前序结果
- `context-compression`: 长对话自动压缩早期轮次，防止上下文丢失
- `multi-step-sse`: 流式模式下支持多步执行，前端可展示步骤进度

## Impact

- **Files changed**: `agent/core.py` (~40 lines), `agent/memory.py` (~25 lines), `frontend/js/agent.js` (~10 lines for step event handling)
- **API**: 新增 SSE 事件类型 `step`；`/api/agent/chat` 和 `/api/agent/chat/stream` 行为改变（可返回多次 tool_call 后再 reply），**但响应格式向后兼容**
- **Breaking**: 无。现有的单步 skill 调用行为不变（执行一次 skill 后 LLM 选择 reply 即可）。非流式 `/api/agent/chat` 的 `skill_calls` 数组从最多 1 项变为可能 >1 项
- **Dependencies**: 无新依赖

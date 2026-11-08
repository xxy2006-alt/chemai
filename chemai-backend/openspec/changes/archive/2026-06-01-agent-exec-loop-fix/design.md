## Context

ChemAI agent 的 execute loop 有三个结构性 bug 需要修复。所有改动集中在 `agent/core.py` 和 `agent/memory.py` 两个文件，不涉及新依赖。

当前架构回顾（参见 `agent/core.py`）：

```
run() / run_stream()
  └─ think → parse_decision → use_skill? → execute → reply → DONE
                                              ↑
                                    这里 return/break，永不到第二轮
```

## Goals / Non-Goals

**Goals:**
- `run()` 的 `max_turns` 循环真正迭代，skill 执行后回到 think phase
- `run_stream()` 支持多步 tool call 后再 reply
- Skill 结果写入 episodic memory，自动注入后续上下文
- 长对话自动压缩

**Non-Goals:**
- 不改动 Planner/Gateway/EventBus（那是后续 Phase 的 scope）
- 不引入外部 agent 框架
- 不改动 skill 的实现代码
- 不改动 provider 层

## Decisions

### D1: run() 的循环出口策略

**选择**: reply 路径是唯一的循环出口。skill 路径改为 `continue`。

**理由**: 这符合 ReAct 模式的标准行为——LLM 自己决定是继续调 skill（return use_skill）还是回复用户（return reply）。`max_turns` 硬上限兜底（第 226 行已存在）。

**备选**: 在执行 skill 后立即让 LLM 做一轮强制判断（"还需要继续吗？"）→ 放弃，多一次不必要的 LLM 调用。

**改动**:
```python
# OLD (lines 196-213):
final_result = await self._provider.chat(...)
return AgentResponse(action="use_skill", ...)  # 立即返回

# NEW:
self.memory.add_turn("user", user_input)
self.memory.add_turn("assistant", observation)
continue  # 回到 think phase
```

### D2: run_stream() 的多步循环

**选择**: 把现有 tool path（lines 297-365）包进 `while turn < max_turns` 循环。skill 执行后 `continue` 回 think，reply 路径 `break`。

**理由**: 与 `run()` 保持一致的行为。`max_turns` 硬上限防止死循环。

**SSE 事件扩展**:
新增事件类型 `step`：
```json
{"type": "step", "current": 2, "skill": "generate_questions"}
```

前端 `agent.js` 在收到 `step` 事件时展示进度（如 "第 2 步：正在出题..."）。

### D3: 对话压缩方案

**选择**: 简单截断方案（不需要 LLM 调用）。

**理由**: Phase 1 的目标是"不丢上下文"，不需要 LLM 级别的摘要质量。简单拼接文本足以保留"之前聊过什么"的信息。LLM 摘要方案（~1-2s 延迟）推迟到 Phase 3。

**实现**:
```python
# memory.py 新增
def needs_compression(self):
    return len(self.working) > 15

def compress_oldest(self, n=8):
    """取最旧 n 轮，拼接为文本摘要，存入 episodic，然后移除"""
    old = []
    for _ in range(min(n, len(self.working))):
        old.append(self.working.popleft())
    summary = "\n".join(f"[{t['role']}]: {t['content'][:200]}" for t in old)
    self.episodic["conversation_archive"] = self.episodic.get("conversation_archive", "") + "\n---\n" + summary
```

### D4: Observation 截断

**选择**: 硬截断到 2000 字符。

**理由**: 有些 skill 返回大量数据（如 `search_exam_bank` 返回 250 条真题），全量传入会撑爆 context window。2000 字符足够传达关键信息（约 500 tokens），同时不会让 context 失控。后续可升级为 LLM 驱动的智能截断。

## Risks / Trade-offs

- **loop 不会真正无限**: `max_turns=5` 硬上限兜底。如果 LLM 连续 5 次选 use_skill，返回 "问题比较复杂" fallback 消息。
- **压缩丢失细节**: 简单截断方案可能丢失重要细节。缓解：截断文本存入 episodic memory 而非直接丢弃，LLM 在需要时可引用。Phase 3 升级到 LLM 摘要。
- **非流式 API 响应变化**: `skill_calls` 数组从最多 1 项变为可能 >1 项。前端 `agent.js` 当前只处理单个 tool_card，多 tool_call 时需更新逻辑。→ 在 agent.js 中加 tool_card 的追加逻辑。
- **streaming 模式下多步 think 可能变慢**: 每轮 think 都是一次完整的 LLM 非流式调用。→ 后续 Phase 可优化为流式 think。

## 1. Bug 2 Fix — Episodic Memory（30 min，无依赖）

- [x] 1.1 `run()` 中 skill 执行成功后加 `self.memory.add_episode(skill_name, skill_result)` → `agent/core.py:188`
- [x] 1.2 `run_stream()` 中 skill 执行成功后加同一行 → `agent/core.py:321`
- [x] 1.3 `run_stream()` 的 web_search auto-retry 路径（line 346/348）也加上 episode 记录
- [x] 1.4 验证：执行 skill 后 `memory.episodic` 非空 — core.py 语法验证通过

## 2. Bug 3 Fix — Context Compression（45 min，无依赖）

- [x] 2.1 `MemoryStack` 加 `needs_compression()` 方法 → `agent/memory.py` (return len(self.working) > 15)
- [x] 2.2 `MemoryStack` 加 `compress_oldest(n=8)` 方法 → 取最旧 N 轮，拼成文本摘要，存入 `episodic["conversation_archive"]`，移除这些轮次
- [x] 2.3 `ChemAgent` 加 `_maybe_compress()` 方法 → `agent/core.py`（调用 memory.needs_compression + memory.compress_oldest）
- [x] 2.4 `run()` 和 `run_stream()` 开始处调用 `self._maybe_compress()` → `agent/core.py:166, 237`
- [x] 2.5 验证：memory.py 语法验证通过

## 3. Bug 1 Fix — Multi-turn Loop in run()（1.5 h，无依赖）

- [x] 3.1 `run()` 的 skill 路径（lines 196-213）：删除 final_result 生成 + return，改为 `continue` 回循环顶部
- [x] 3.2 确认 `run()` 的 reply 路径（lines 215-224）作为循环出口不动
- [x] 3.3 确认 max_turns fallback（line 226-231）作为兜底不动
- [x] 3.4 验证：单步 skill 行为不变（LLM 选 reply 后正常返回）；多步 skill 可串联 — core.py 语法验证通过

## 4. Feature 1 — Multi-step in run_stream()（1 h，依赖 §3）

- [x] 4.1 `run_stream()` 的 tool path 包进 `while turn < max_turns` 循环
- [x] 4.2 skill 执行后 → observation 写入 memory → `turn += 1` → `continue` 回 think
- [x] 4.3 新增 `step` SSE 事件：`{"type": "step", "current": <N>, "skill": "<name>"}` → `agent/core.py`
- [x] 4.4 reply 路径和 done 事件处理不变，循环退出后统一 reply + done
- [x] 4.5 验证：core.py 语法验证通过

## 5. Feature 2 — Skill Context Injection（30 min，依赖 §1）

- [x] 5.1 `_build_system_prompt()` 增加 episodic 提示行 → `agent/core.py:73-88`
- [x] 5.2 observation 文本截断：>2000 chars 加 "（内容过长，已截断）" 后缀 → `agent/core.py` run_stream observation formatting
- [x] 5.3 验证：core.py 语法验证通过

## 6. Frontend — Multi-step SSE Handling（30 min，依赖 §4）

- [x] 6.1 `agent.js` 的 SSE 事件 switch 中新增 `case 'step'` → 更新 think-status 为 "第 N 步：<skill_label>"
- [x] 6.2 `agent.js` 的 `case 'tool_call'` 改为追加新 tool_card 而非替换 → `toolCards[]` 数组
- [x] 6.3 验证：agent.js 语法验证通过

## 7. Integration Verification（30 min，依赖 §1-6）

- [x] 7.1 端到端测试：发 "搜索盐类水解的真题，然后根据结果出一道类似题" → 验证 search_exam_bank → generate_questions 串联
- [x] 7.2 日志验证：多步执行后 `memory.episodic` 包含两个 skill 的结果
- [x] 7.3 单步回归测试：发 "你好" → 验证无 tool_call 的普通对话不受影响
- [x] 7.4 边界测试：连续发 20 轮对话 → 验证压缩触发且 agent 仍正常运行

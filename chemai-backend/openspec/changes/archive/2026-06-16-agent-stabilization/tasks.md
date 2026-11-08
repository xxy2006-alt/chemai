## 1. Batch 1: 消息重复 + 会话持久化（45 min，无依赖）

- [x] 1.1 `core.py:386` — `add_turn("user", user_input)` 移到 `while` 循环前
- [x] 1.2 `core.py:448` — 删除循环内的重复 `add_turn("user", user_input)`
- [x] 1.3 `core.py:464` — 删除 reply phase 前的重复 `add_turn("user", user_input)`
- [x] 1.4 `memory.py` — 添加 `to_dict()` 和 `from_dict()` 序列化方法
- [x] 1.5 `fastapi_sse.py` — `ChatRequest` 增加 `conversation_id: Optional[str]` 字段
- [x] 1.6 `fastapi_sse.py` — 模块级 `_conversations: dict[str, ChemAgent]` + 复用逻辑
- [x] 1.7 `fastapi_sse.py` — 新增 `POST /api/agent/chat/reset` 端点
- [x] 1.8 `fastapi_sse.py` — stream `generate()` 中去掉 `finally: agent.close()`
- [x] 1.9 验证：发送消息 → 刷新页面 → 再次发送 → 检查上下文是否保留

## 2. Batch 2: Skill 超时（15 min，依赖 §1）

- [x] 2.1 `skill_registry.py` — `execute()` 中 `await func(**args)` 改 `asyncio.wait_for(..., timeout=30)`
- [x] 2.2 `skill_registry.py` — `asyncio.TimeoutError` 捕获，返回结构化错误
- [x] 2.3 验证：手动构造长时间 skill 调用，确认 30s 超时返回

## 3. Batch 3: Skill Provider 注入（30 min，依赖 §1-2）

- [x] 3.1 `skill_registry.py` — 添加 `_provider` 属性 + `set_provider()` 方法
- [x] 3.2 `core.py` — `ChemAgent.__init__()` 中 `registry.set_provider(self._provider)`
- [x] 3.3 `skills/generate.py` — `DeepSeekProvider()` → `registry._provider or DeepSeekProvider()`
- [x] 3.4 `skills/tutor.py` — 同上
- [x] 3.5 `skills/experiment.py` — 同上
- [x] 3.6 `skills/weekly_report.py` — 同上
- [x] 3.7 验证：走 agent 请求"出几道盐类水解的题"，确认 generate skill 使用 agent 的 provider

## 4. Batch 4: SSE 清理（15 min，依赖 §1-3）

- [x] 4.1 `fastapi_sse.py` — `generate()` finally 块中区分处理持久化/非持久化 agent
- [x] 4.2 非持久化 agent（无 conversation_id）：调 `agent.close()`
- [x] 4.3 持久化 agent：跳过 close
- [x] 4.4 验证：在 AI 回复过程中关闭浏览器页面，检查后端进程无连接堆积

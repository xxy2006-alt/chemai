# ChemAI Agent 改进计划

状态：已讨论通过，等待执行
创建：2026-06-13
路径：修补现有架构（A 路线），分四批推进

---

## 背景

Agent 系统代码审查发现以下核心问题（详见 agent 探索报告）：

| # | 问题 | 严重度 | 文件 |
|---|------|--------|------|
| 1 | 流式循环中 `user_input` 重复追加到记忆 | 高 | core.py:448 |
| 2 | 每次请求新建 agent 实例，无跨请求记忆持久化 | 高 | fastapi_sse.py |
| 3 | 4 个 skill 自己创建 `DeepSeekProvider()` 绕过 agent | 中 | generate.py, tutor.py, experiment.py, weekly_report.py |
| 4 | 技能执行无超时，挂起会阻塞整个管道 | 中 | skill_registry.py |
| 5 | Gateway prompt 虽然列出了所有 10 个技能（实际不缺） | - | 已验证无此问题 |
| 6 | SSE 断连后 httpx 连接无显式清理 | 低 | fastapi_sse.py, core.py |

---

## 执行策略

- 每批独立可测，改完验证通过才进入下一批
- 每批 2-3 个文件，不跨批次修改同一文件
- 不重写 `core.py`（保持 550 行现有架构）
- 不改动前端 `agent.js`

---

## 批次 1：消息重复 + 会话持久化

**目标**：修复最严重的内存正确性 bug，让 agent 记得对话上下文

### 1a. 修复消息重复 bug（core.py）

**位置**：`agent/core.py:386-448`

**问题**：
```python
while turn < self.config.max_turns:
    # ... think → tool_call → execute ...
    self.memory.add_turn("user", user_input)   # ← 每次工具调用都加！
    self.memory.add_turn("assistant", observation)
    # ...
# Reply phase
self.memory.add_turn("user", user_input)       # ← 又加一次！
```

**修复**：
- `add_turn("user", user_input)` 移到 `while` 循环前（只加一次）
- 删除循环内的 `add_turn("user", user_input)`
- 删除 Reply phase 前的重复 `add_turn("user", user_input)`

### 1b. 会话持久化（fastapi_sse.py + memory.py）

**方案**：
- `ChatRequest` 增加可选 `conversation_id: Optional[str]` 字段
- `memory.py` 的 `MemoryStack` 加 `to_dict()` / `from_dict()` 序列化方法
- `fastapi_sse.py` 维护模块级 `_conversations: dict[str, ChemAgent]`
- 提供 `conversation_id` 时复用已有 agent 实例，不提供时创建新的
- 新增 `POST /api/agent/chat/reset?conversation_id=xxx` 重置端点
- stream 端点去掉 `finally: agent.close()`（复用 agent 时不关连接）

**涉及文件**：
- `agent/core.py`（1a）
- `agent/memory.py`（1b）
- `agent/channel/fastapi_sse.py`（1b）

---

## 批次 2：技能超时

**目标**：防止技能挂起阻塞整个 agent 管道

**修复**：
- `skill_registry.py:execute()` 中 `await func(**args)` 包装 `asyncio.wait_for(..., timeout=30)`
- 超时后返回 `{"error": "Skill 'xxx' timed out after 30s"}`，不抛异常

**涉及文件**：
- `agent/skill_registry.py`

---

## 批次 3：裸 LLM 技能改为 registry 注入 provider

**目标**：4 个技能不再自己 `DeepSeekProvider()`，统一走 agent 的 provider

**方案**：
- `SkillRegistry` 加 `_provider` 属性 + `set_provider()` 方法
- `ChemAgent.__init__()` 初始化 provider 后调用 `registry.set_provider(self._provider)`
- 4 个技能的 `provider = DeepSeekProvider()` 替换为 `provider = registry._provider or DeepSeekProvider()`

**影响技能**：

| 文件 | 当前行为 | 改为 |
|------|---------|------|
| `skills/generate.py` | `provider = DeepSeekProvider()` | `from agent.skill_registry import registry; provider = registry._provider or DeepSeekProvider()` |
| `skills/tutor.py` | 同上 | 同上 |
| `skills/experiment.py` | 同上 | 同上 |
| `skills/weekly_report.py` | 同上 | 同上 |

**为什么用 `or DeepSeekProvider()` 兜底**：技能可能被独立导入测试，没有 agent 上下文时自动 fallback

**涉及文件**：
- `agent/skill_registry.py`
- `agent/core.py`
- `agent/skills/generate.py`
- `agent/skills/tutor.py`
- `agent/skills/experiment.py`
- `agent/skills/weekly_report.py`

---

## 批次 4：SSE 取消清理

**目标**：浏览器端断连后，后端连接不泄漏

**修复**：
- `fastapi_sse.py` 的 `generate()` 协程 `finally` 块中显式清理
- 如果是非持久化 agent（无 conversation_id），调 `agent.close()` 关 provider 连接
- 如果是持久化 agent，只标记当前请求结束，不关 provider

**涉及文件**：
- `agent/channel/fastapi_sse.py`

---

## 不做的事

以下问题评估后不在此次计划中处理：

| 问题 | 原因 |
|------|------|
| Gateway/Planner 增加额外 LLM 延迟 | 大部分请求走 fast path，不走 Planner |
| Planner 只匹配特定关键词才触发 | 符合设计意图 |
| Provider 切换逻辑大部分是死代码 | 留着不影响功能，未来可能用 |
| `_parse_decision()` JSON 脆弱解析 | 用 function-calling 格式后自然解决 |
| `compress_oldest(8)` 可能丢上下文 | 需要验证实际场景再优化 |

---

## 验证方法

每批完成后：
1. 启动服务 `python -m uvicorn app.main:app --port 8000`
2. 打开 `http://localhost:8000`
3. 在 AI 教研助手聊天框发送测试消息
4. 检查浏览器 console 无错误
5. 批次 1：刷新页面后重新对话，验证 agent 记得之前的上下文
6. 批次 2：手动构造长时间运行的 LLM 请求，验证 30s 超时生效
7. 批次 3：请求"帮我出几道盐类水解的题"，验证生成过程不报错
8. 批次 4：在 AI 回复过程中关闭页面，检查后端进程无连接堆积

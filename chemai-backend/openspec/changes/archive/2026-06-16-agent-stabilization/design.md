## Context

ChemAI agent 在 Phase 1-5 开发完成后处于功能可用但存在已知 bug 的状态。代码审查见 `docs/agent-改进计划.md`。修补策略选择"A 路线"——在现有架构上逐步修复，不重写 `core.py`。

## Goals / Non-Goals

**Goals:**
- 修复流式循环中消息重复累积的 bug
- 让 agent 记住跨请求的对话上下文
- 防止 skill 执行超时阻塞管道
- 消除 skill 中各自创建 DeepSeekProvider 的重复实例化
- 修复 SSE 断连后连接泄漏

**Non-Goals:**
- 不改动 `core.py` 的核心循环架构（Think→Execute→Reply 三阶段不变）
- 不改动 10 个 skill 的业务逻辑
- 不改动前端 `agent.js` 和 SSE 事件格式
- 不引入新的外部依赖

## Decisions

### D1: 会话持久化 — 进程内存 dict vs 数据库/Redis

**选择**: 进程内存 dict `_conversations: dict[str, ChemAgent]`。

**理由**: MVP 阶段单进程部署，不需要分布式会话。agent 实例在内存中保持 httpx 连接活性，切换数据库/Redis 需要序列化 provider 状态反而复杂。进程重启丢失对话是可接受的（开发阶段）。未来生产化时改为 Redis。

### D2: Provider 注入 — registry 属性 vs 函数参数

**选择**: `registry._provider` 属性 + `set_provider()` setter。

**理由**: 10 个 skill 通过 LLM function_call 的 args dict 调用，无法在 args 中传递 Python 对象。通过 registry 共享 provider 是最简单的路径。`or DeepSeekProvider()` 兜底保证 skill 独立导入测试不报错。

### D3: Skill 超时 — 固定 30s vs 可配置

**选择**: 固定 30s。

**理由**: 当前 10 个 skill 中最慢的是 `generate_questions`（LLM 调用 ~5-15s）和 `web_search`（网络请求 ~3-10s），30s 足够覆盖所有正常场景。未来需要时改为 Skill 注册时声明 `timeout` 参数。

### D4: SSE 清理 — 区分持久化/非持久化 agent

**选择**: 仅对非持久化 agent（无 conversation_id）调用 `agent.close()`。

**理由**: 持久化 agent 需要保持 provider 连接以支持后续对话。非持久化 agent 在请求结束后应立即释放连接。

## Risks / Trade-offs

- **进程重启丢对话**: 可接受——开发阶段，且前端 localStorage 保留了对话 UI 记录
- **内存 dict 无限增长**: 需要后续加 LRU 淘汰或 TTL。当前规模（单教师使用）不会触发
- **provider 注入的隐含耦合**: skill 通过 `registry._provider` 获取 provider 是一种隐含依赖，不如函数参数显式。但在 function_call args dict 的限制下，这是最简单的可行方案

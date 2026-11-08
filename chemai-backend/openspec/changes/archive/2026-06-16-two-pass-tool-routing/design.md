## Context

ChemAI 当前架构（A 路线后）：Agent 创建时把 persona 的所有 available_skills 全量注册为 pydantic-ai tools，LLM 在单次推理中从 6-7 个 tools 中选择。测试显示 DeepSeek V4 在这个规模上有 ~30% 的误判率。V4 不支持 `tool_choice="required"`，无法像 GPT-4 一样强制调用正确 tool。

项目已有 `agent/gateway.py` 的 `IntentClassifier`——用 LLM 做意图分类+tool 推荐——但未被 Agent 管道消费。

## Goals / Non-Goals

**Goals:**
- 在 Agent 执行前，用 LLM 分类器将 tool 候选集从 6-7 缩小到 3-5
- 分类器感知当前 persona 的 available_skills，不推荐 persona 外的 tool
- 分类器失败时优雅降级，不影响对话可用性
- 多轮对话中传递会话上下文给分类器，避免"再出5题"失去语义
- 复用现有 `gateway.py` 和 `provider/deepseek.py`，不引入新基础设施

**Non-Goals:**
- 不改变 pydantic-ai Agent 的 tool calling 机制
- 不改变工具函数的签名和行为
- 不改变前端 SSE 事件格式
- 不引入 MCP server、Agent 图或多 Agent 编排

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    /chat  & /chat/stream                 │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  1. ChatRequest 到达                                     │
│       │                                                  │
│       ▼                                                  │
│  2. 构建分类器上下文                                       │
│     │  ├─ 当前 message                                   │
│     │  └─ 最近 2 轮 conversation history（如有）          │
│       │                                                  │
│       ▼                                                  │
│  3. IntentClassifier.classify(ctx, available_skills)     │
│     │  ├─ 用 DeepSeekProvider 做轻量 LLM 调用             │
│     │  ├─ asyncio.wait_for(..., timeout=5.0) 超时保护    │
│     │  ├─ temperature=0.1, max_tokens=512                │
│     │  └─ 返回: {intent, page, tools: [...], params}     │
│     │                                                    │
│     ├─ 成功 + type 校验 (isinstance(tools, list))        │
│     │    → narrowed = intersect(tools, persona)          │
│     │    → 交集为空? → narrowed = None (全量回退)         │
│     └─ 失败/超时/校验失败 → narrowed = None (全量退化)     │
│       │                                                  │
│       ▼                                                  │
│  4. factory.create_agent(persona, provider,               │
│         tool_names=narrowed)                             │
│     │  ├─ narrowed=None → 全量 available_skills          │
│     │  └─ narrowed=[...] → intersect(传入 ∩ persona)    │
│       │                                                  │
│       ▼                                                  │
│  5. agent.run() / agent.run_stream_events()              │
│     └─ LLM 从 3-5 个 tools 中选择（误判率大幅降低）       │
│                                                          │
│  6. 请求结束 → provider.close() 释放连接                  │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

## Decisions

### D1: 分类器用哪个 LLM？

**选择**: 恒用 DeepSeek（`DeepSeekProvider`），不跟随 request.provider。

**理由**: 意图分类是简单任务（"这条消息该用哪个 tool"），不需要 MiMo/Zhipu/Qwen 的差异化能力。DeepSeek 是主力 provider，延迟和成本都已验证。恒用 DeepSeek 也避免了为其他 provider 维护分类器适配层。

### D2: 分类器 prompt 注入 available_skills vs 后过滤

**选择**: 两者都做。prompt 里告诉分类器当前 persona 有哪些 tools，执行后在代码层再做一次交集过滤。

**理由**: Prompt 注入减少"分类器选了 persona 外 tool"的概率。代码层交集是安全兜底——即使 prompt 注入失效（LLM 不听话），返回的 tools 列表也不会包含 persona 不支持的 skill。

### D3: 分类器失败策略

**选择**: 任何异常（网络超时、HTTP 错误、JSON 解析失败）→ 返回 `IntentResult(tools=None)` → Agent 用全量 tools。同时在流式端点 yield 一个 `phase: "thinking"` 事件保持前端兼容。

**理由**: 分类器是优化，不是命脉。用户的对话不能因为分类器挂了就中断。"None = all tools" 语义已存在于 `IntentResult` 的默认值，无需改动。

### D4: 分类器在流式端点中的时序

**选择**: 分类器在 `async def generate()` 外部 `await`，完成后才进入 generator。第一个 SSE 事件（`phase: thinking`）在分类完成后才发送。

**理由**: 分类器结果（narrowed_tools）需要在创建 Agent 之前确定。如果在 generator 内部做分类，需要在 yield 之前做 async 操作，逻辑上可行但代码结构更复杂。外部 await 更清晰，且 ~1-2s 分类延迟在对话场景中用户无感。

### D5: 分类器超时保护

**选择**: 在端点层用 `asyncio.wait_for(classifier.classify(), timeout=5.0)` 包装分类器调用。

**理由**: `DeepSeekProvider.chat()` 内置 3 次重试 + 指数退避（最坏 60s×3+6s=186s），不加超时会导致用户在分类阶段等 3 分钟。5 秒对意图分类足够了——temperature=0.1、max_tokens=512 的简单 prompt 正常在 1-2 秒完成。超时后走 D3 退化路径（tools=None）。

### D6: 分类器返回值类型校验

**选择**: 在 `IntentResult._parse()` 中增加 `isinstance(tools, list)` 校验，不通过时退回 `tools=None`。

**理由**: LLM 可能返回 `"tools": "chemistry_tutor"`（字符串而非列表）或 `"tools": null`。Python 的 `set("chemistry_tutor")` 会迭代字符导致交集始终为空，Agent 获得零 tools。显式校验消除此风险。

### D7: 空交集回退

**选择**: `factory.create_agent()` 中，当传入 `tool_names` 与 persona `available_skills` 的交集为空列表时，回退为 `tool_names=None`（全量 tools）。

**理由**: 分类器可能全部推荐了 persona 外的 tools（如 tutor persona 下分类器返回 `["weekly_report", "diagnose_barrier"]`，但二者都不在 tutor 的 6 个 skills 中）。交集为空产生零 tool Agent，比全量 tools 的 ~30% 误判率更差。

### D8: 分类器 Provider 生命周期

**选择**: `DeepSeekProvider` 实例在应用启动时创建一次（模块级单例），所有分类请求共享同一个 provider 实例。不每次 new。

**理由**: 每次请求 new `DeepSeekProvider()` 会创建新的 `httpx.AsyncClient`，但没有代码调用 `close()`，导致连接泄漏。共享单例复用连接池，避免泄漏且减少连接建立开销。10 个 tool skill 已经这样做了（各自 new + close），分类器应该做得更好。

### D9: 会话历史注入分类器

**选择**: 将最近 2 轮对话历史作为分类器 prompt 的上下文传入。历史消息以 `用户: ...\n助手: ...` 格式追加到 prompt 中。

**理由**: 多轮对话中，用户说"再出5题"时，分类器需要知道上一轮是"给张三出5道盐类水解的题"才能正确路由到 `generate_questions`。只看当前消息会分类为纯 chat。2 轮上下文是精度和 prompt 长度的平衡点——1 轮不够（"对，第二题"），3 轮以上 token 浪费。

## Risks / Trade-offs

- **延迟增加**: 每个对话回合 +1-2s（正常）或最多 +5s（超时）。对于"出题"类长任务（Agent 内部 LLM 调用需要 5-15s），1-2s 占比很小。对于"你好"类短任务，分类器可能会被 LLM 判定为 `tools=[]`（无需工具），Agent 直接回复，总延迟增加不明显。超时保护保证最坏情况不超过 5s。
- **分类器自身也会选错**: LLM 分类器也有误判率，但两段式架构的容错性比单段好——第一段选错 2 个 tools，第二段仍能在 3-5 个候选中找到正确的；单段选错 1 个 tool 就是全错。注意：分类器和 Agent 都用 DeepSeek V4，可能在相同类型的歧义上同时失败（共享失败模式）。不应假设两段误差独立。
- **分类器 prompt 长度**: 当前 CLASSIFY_PROMPT ~400 tokens，注入 available_skills ~50 tokens，注入会话历史 ~100 tokens。总计 ~550 tokens，仍远在安全范围内。
- **Provider 连接管理**: D8 用模块级单例避免了 httpx 连接泄漏，但单例的 `httpx.AsyncClient` 在进程退出时依赖 GC 清理。后续可在 FastAPI 的 lifespan 事件中显式 close。
- **多轮对话上下文**: D9 只传 2 轮历史。超过 2 轮前的上下文（如"参考第一题的做法"当第一题在 3 轮前）分类器无法感知。2 轮是精度和 prompt 长度的平衡点，覆盖大多数对话场景。
- **single-provider 风险**: D1 恒用 DeepSeek 做分类。如果 DeepSeek 服务降级（涨价、延迟飙升、审查变更），分类器延迟会拖慢所有请求。超时保护（D5）提供了硬上限，但 degraded 状态下所有请求都退化到全量 tools。可接受的 tradeoff——分类是简单任务，DeepSeek 稳定性已经过验证。

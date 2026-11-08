## Why

Agent 走 A 路线后（全量 tools 给 LLM），10 次测试 9 次调用了 tool，但 3-4 次选错。根因：DeepSeek V4 不支持 `tool_choice="required"`，在 6-7 个 tools 中做"一 shot 选择"有 ~30% 的误判率。

业界标准解法是两段式：先用轻量 LLM 缩小候选集（10→3-5），再让 Agent 精判。项目里 `agent/gateway.py` 的 `IntentClassifier` 已经实现了第一段——LLM 意图分类+tool 推荐——但完全未被消费。

## What Changes

### 核心：Gateway LLM 分类器接入 Agent 管道

```
用户消息 → IntentClassifier.classify() → narrowed_tools (3-5个)
         → factory.create_agent(tools=narrowed_tools) → Agent 执行
```

改 4 个文件，~90 行：

| 文件 | 改动 |
|------|------|
| `agent/gateway.py` | `classify()` 新增 `available_skills` + `conversation_context` 参数；`_parse()` 加 type 校验；加 error logging |
| `agent/agents.py` | `create_agent()` 新增 `tool_names` 可选参数；空交集回退逻辑 |
| `agent/provider/deepseek.py` | 模块级单例 `classifier_provider`（复用连接池） |
| `agent/channel/fastapi_sse.py` | `/chat` 和 `/chat/stream` 在 Agent 创建前调用分类器（含 5s 超时、会话历史注入、空交集回退） |

### 失败回退

分类器失败（网络/超时/JSON 解析失败）→ `IntentResult(tools=None)` → 退化为全量 tools，不影响对话可用性。

## Capabilities

### New Capabilities
- `llm-tool-routing`: Gateway LLM 在 Agent 执行前缩小 tool 候选集，降低 DeepSeek V4 的 tool 选择误判率

## Impact

- **Files changed**: 4 files, ~90 lines added
- **API**: `create_agent()` 新增可选 `tool_names: list[str]` 参数。`classify()` 新增可选 `available_skills`, `conversation_context` 参数。**向后兼容**
- **Breaking**: 无
- **Latency**: 每个对话回合增加 1-2s 分类延迟（5s 硬超时）。p95 < 3s。对长任务（出题 5-15s）占比小
- **Dependencies**: 复用现有 `agent/provider/deepseek.py`，无新增依赖
- **Safety guards**: 5s 超时、type 校验、空交集回退、异常 logging、provider 连接复用

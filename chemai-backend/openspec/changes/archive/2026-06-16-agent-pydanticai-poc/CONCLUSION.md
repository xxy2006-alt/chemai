# PydanticAI PoC 结论报告

日期：2026-06-13
版本：pydantic-ai 0.0.10 (PyPI 可用版本)

## 已验证可工作的

### 1. DeepSeek 连接 ✓
```python
from pydantic_ai.models.openai import OpenAIModel
from openai import AsyncOpenAI
client = AsyncOpenAI(api_key=ds_key, base_url='https://api.deepseek.com/v1')
model = OpenAIModel('deepseek-chat', openai_client=client)
```
通过 `AsyncOpenAI` 客户端包装 DeepSeek API，工作正常。`agent.run()` 返回 `RunResult`，中文输出正常。

### 2. 文本流式输出 ✓
`result.stream_text(delta=True)` 逐 chunk 输出文本，映射到 SSE `text` 事件可行。测试通过。

### 3. Skill 迁移模式 ✓
`@registry.register(...)` → `@agent.tool_plain` 的迁移是机械的：
- 装饰器差异：`@registry.register(name, desc, params)` vs `@agent.tool_plain`（参数从函数签名自动推断）
- 参考 `search.py` (44 行) vs `search_pydantic.py` (44 行)，迁移费用 1:1
- 业务逻辑完全复用，只需改装饰器和类型注解

### 4. 端点集成 ✓
`POST /api/agent/chat/pydantic` 端点创建成功，接受 `ChatRequest` 格式，返回 `StreamingResponse`，与前端兼容。

## 阻塞问题

### stream_events() 缺失 — 严重阻塞
pydantic-ai 0.0.10 版 `StreamedRunResult` 没有 `stream_events()` 方法。只有：
- `stream_text(delta=True)` — 纯文本流式
- `stream()` — 低层级原始流

**没有途径获取 tool_call/tool_result 事件**，这意味着无法实现 `agent-stabilization` 中定义的 SSE 事件映射。

完整的事件映射需要以下方法（在 pydantic-ai >= 0.1.0 或最新版本中存在）：
- `result.stream_events()` → `PartDeltaEvent`, `FunctionToolCallEvent`, `FunctionToolResultEvent`, `FinalResultEvent`

### 解决方案
需要安装更新版本的 pydantic-ai。当前 pip 默认安装 0.0.10，可能因为 Python 3.11 兼容性限制。

```bash
pip install pydantic-ai>=0.1.0  # 或最新版本
```

如果最新版本也未提供 `stream_events()`，可能需要用 `agent.iter()` 替代方案。

## 迁移工作量估算（假设 stream_events() 可用）

| 组件 | 当前 | PydanticAI 版本 | 行数变化 |
|------|------|----------------|---------|
| search.py | 44 行 | search_pydantic.py | 44 行（一致） |
| core.py | 427 行 | 被 Agent 替代 | 删除，由 agent.run_stream() 替代 |
| gateway.py | - | 不再需要 | 删除 |
| planner.py | - | 不再需要 | 删除 |
| fastapi_sse.py | ~140 行 | 减至 ~60 行（适配层） | -80 行 |
| 其余 9 个 skill | ~300 行 | ~300 行（机械迁移） | 0 |
| pydantic_agent.py | - | ~100 行（新增） | +100 |
| **总计** | **~900 行** | **~500 行** | **-400 行** |

## 建议

1. **短期**：找到支持 `stream_events()` 的 pydantic-ai 版本（>=0.1.0），完成完整的事件映射测试
2. **中期**：在确认事件映射可行后，迁移其余 9 个 skill，替换 core.py
3. **不推荐**：在当前 0.0.10 版本上进行全量迁移——缺少 tool_call 事件是致命缺陷

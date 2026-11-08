## Why

当前 Gateway 用 LLM 一次性输出五个决策维度（intent、page、params、tools、provider），误判面大。路由决策（跳不跳页）和 tool 筛选耦合在同一个 LLM 调用里，`hybrid` 和 `chat` 的边界靠自然语言描述，分类器经常在"查张梦琪"这类单人查询上犹豫。

两个核心认知纠偏：

1. **路由应该由 tool 自己决定，不是 Gateway。** Tool 最清楚自己产生了什么数据、数据该在哪里展示。Gateway 只需要回答"调哪个 tool？"和"是不是纯跳页？"两个问题。

2. **路由判断依据应该是参数语义，不是数据条数。** 查 2 个人和查 34 个人在意图上可能相同（都是点名查），参数中是否有 `student_name/student_id` 才是正确的语义边界。

## What Changes

三分类（chat/page_action/hybrid）简化为两分类（chat/navigate）：

```
Gateway 只输出 {type: "chat"|"navigate", tools: [...], provider: "deepseek"}

type=chat      → Agent 执行 tool → tool 返回值带 _route 字段决定跳不跳
type=navigate  → 直接发送 navigate 事件（纯页面跳转，不调 tool）
```

**路由逻辑下放到 tool 层：**

```python
# tool 返回 _route 字段
{ "data": {...}, "_route": { "navigate": True, "page": "diagnosis", ... } }

# 判断规则：参数中有 student_name/student_id → 不跳；只有 class_name/class_id → 跳
```

改 5 个文件，删 >100 行旧代码：

| 文件 | 改动 |
|------|------|
| `agent/gateway.py` | 重写 CLASSIFY_PROMPT（三分类→两分类）；简化为 type+tools+provider 三字段；增强 `_keyword_fallback`；删除 `build_navigate_events()`、`_PAGE_ACTIONS`、`_TOOL_POPULATE_TARGET` |
| `agent/tools.py` | 涉及页面展示的 tool（diagnose_barrier、generate_questions、weekly_report、search_exam_bank、assign_adaptive_practice）返回值加 `_route` 字段 |
| `agent/channel/fastapi_sse.py` | Phase 3 改为读 tool 返回值的 `_route`；`navigate` 类型直接发送跳页事件 |
| `agent/sse_adapter.py` | 适配 `_route` 事件的 SSE 输出 |
| `agent/agents.py` | 无改动（tool 交集逻辑不变） |

## Capabilities

### New Capabilities
- `tool-self-routing`: tool 函数自行决定执行结果是否需要页面跳转，依据参数语义（student_name → 单人 → 不跳；class_name → 班级 → 跳）
- `gateway-two-class`: Gateway 简化为 chat/navigate 两分类，只回答"调哪个 tool"和"纯跳页"两个问题

### Removed Capabilities
- `gateway-hybrid-intent`: 删除 hybrid 意图分类
- `gateway-navigate-events`: 删除 `build_navigate_events()` 集中式路由工厂

## Impact

- **Files changed**: 5 files, +80/-120 lines (净删 ~40 行)
- **API**: SSE 事件格式不变（navigate/populate/action 字段名保持一致），`_route` 只在 tool 返回值内部新增，前端无感
- **Breaking**: LLM 分类器 prompt 重构，需要跑 `evals/test_classifier.py` 验证分类准确率
- **Latency**: Gateway 输出字段减少（5→3），prompt 更短，分类延迟降低
- **Dependencies**: 无新增依赖

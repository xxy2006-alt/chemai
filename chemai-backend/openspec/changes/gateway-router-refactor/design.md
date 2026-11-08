## Context

当前 Gateway 采用三分类（chat/page_action/hybrid）LLM 方案。分类器一次输出 intent、page、params、tools、provider 五个字段。`hybrid` 和 `chat` 的边界在 prompt 里靠大段自然语言描述（"查单个学生的既有记录不是 hybrid，是 chat"），分类器经常在此处犹豫。

经过子 Agent 审核，三个前提已确认：

1. **Gateway 只保留 tool 筛选** — 通过，但需加关键词兜底
2. **路由由 tool 返回值决定** — 方向对，但规则应从"数据条数"改为"参数中是否有 student_name"
3. **砍掉 hybrid，两分类** — 前提 2 的自然结果

## Goals / Non-Goals

**Goals:**
- Gateway 输出从 5 字段缩减为 3 字段（type, tools, provider）
- 路由决策分散到各 tool 函数，依据参数语义（非数据条数）
- 三分类→两分类，消除 hybrid 分类的歧义
- 删除 `build_navigate_events()` 集中式路由工厂
- 关键词规则增强，作为 LLM 分类器兜底

**Non-Goals:**
- 不改变 pydantic-ai Agent 的 tool calling 机制
- 不改变前端 SSE 事件格式（navigate/populate/action 字段名保持一致）
- 不改变 tool 函数的核心逻辑（只改返回值结构）
- 不引入新的基础设施或依赖

## Architecture

### 新架构流程

```
用户消息
  │
  ▼
┌──────────────────────────────────────┐
│  Gateway (IntentClassifier)          │
│                                      │
│  输入：用户消息 + 对话上下文           │
│  输出：{                              │
│    type: "chat" | "navigate",        │
│    tools: [...],           // chat时  │
│    page: "exam-v2",        // navigate时 │
│    provider: "deepseek"              │
│  }                                   │
│                                      │
│  兜底：增强的关键词规则               │
└──────────────────────────────────────┘
  │
  ├─ type=navigate → 直接发送 navigate 事件，不走 Agent
  │
  └─ type=chat → Agent 执行
       │
       ▼
  ┌──────────────────────────────────────┐
  │  Agent (pydantic-ai)                 │
  │  注册 Gateway 推荐的 tool 子集        │
  │  执行 tool，收集返回值                │
  └──────────────────────────────────────┘
       │
       ▼
  ┌──────────────────────────────────────┐
  │  路由决策（tool 返回值中的 _route）   │
  │                                      │
  │  _route.navigate == true  →  发送    │
  │    navigate + populate + action 事件  │
  │  _route.navigate == false →  只返回   │
  │    文本回复                           │
  └──────────────────────────────────────┘
```

### 关键边界场景

| 用户输入 | Gateway 输出 | Tool 路由 |
|---------|-------------|----------|
| "张梦琪最近错题多吗" | chat, tools=[diagnose_barrier] | student_name 存在 → 不跳 |
| "高三1班诊断情况" | chat, tools=[diagnose_barrier] | 只有 class_name → 跳 diagnosis |
| "给张三出5道盐类水解" | chat, tools=[generate_questions] | student_name 存在 → 不跳 |
| "出一份期中试卷" | chat, tools=[generate_questions] | 无 student → 跳 exam-v2 |
| "打开考试工作台" | navigate, page=exam-v2 | 不走 Agent |
| "什么是氧化还原" | chat, tools=[chemistry_tutor] | 纯知识 → 不跳 |

## Decisions

### D1: 路由判断依据——参数语义 vs 数据条数

**选择**: 参数中是否有 `student_name` / `student_id`。

**理由**: 用户说"查张梦琪和李明的错题"是点名查 2 个人，"查高三1班诊断"是查全班 34 人。数据条数可能不同（2 vs 34），但用户意图的语义边界在参数层就很清晰——有 student 标识就是单人查询，不跳页。数据条数是 tool 执行的偶然结果，参数才是用户意图的直接体现。

### D2: 路由逻辑放在 tool 里还是管道里

**选择**: 放在 tool 函数里。tool 返回 `_route` 字段，管道层只读取。

**理由**:
- tool 最清楚自己的参数语义——`diagnose_barrier` 知道 `student_name` 参数是否被传入
- 分散决策比集中式 switch-case 更容易维护——新增 tool 不需要改管道代码
- 每个 tool 可以有不同的路由规则（不是所有 tool 都会触发跳页）

### D3: Gateway 两分类 vs 三分类

**选择**: `chat`（需要调 tool）和 `navigate`（不需要调 tool，纯跳页）。

**理由**: `hybrid`（先调 tool 再跳页）和 `chat`（只调 tool 不跳页）的区别不需要 LLM 提前判断——tool 执行后自己决定。Gateway 只需要区分"要不要调 tool"——不要调就是 navigate，要调就是 chat。

### D4: navigate 类型的范围

**选择**: 缩小到无参页面跳转（"打开考试工作台""去首页"）。

**理由**: 如果 navigate 允许带参数（如"打开张三的诊断页面"），就和 tool 路由的职责重叠了。带参查询应该走 tool，让 tool 判断是否需要跳页。navigate 只处理最纯粹的"打开 X 页面"场景。

### D5: Gateway 两分类 prompt 设计

**选择**: 简化为判断"需要调 tool 吗？"

```
你是化学教研助手的意图分类器。回答两个问题：
1. 用户消息是否需要调用工具？需要→type="chat"，不需要（纯页面跳转）→type="navigate"
2. 如果是 navigate，目标页面是什么？

返回 JSON：
{"type": "chat"|"navigate", "tools": [...], "page": null|"exam-v2"|"diagnosis"|"students"|"teacher", "provider": "deepseek"|"mimo"}
```

**理由**: 去掉了 intent/page/params 的复杂描述，分类器只需要做一个二元决策。prompt 更短，LLM 更快更准。

### D6: 关键词兜底增强

**选择**: 在现有 `_keyword_fallback` 基础上，增加"出题/考试→generate_questions"、"诊断→diagnose_barrier"、"周报→weekly_report"的精确 tool 推荐。

**理由**: 当前 `_keyword_fallback` 只返回 `intent` 和 `page`，不推荐 tool（`tools=None` → Agent 得全量 tools）。增强后在 LLM 失败时也能做 tool 筛选，减少退化影响。

### D7: _route 字段格式统一

**选择**: 所有 tool 共用 RouteHint 结构：

```python
{"_route": {"navigate": bool, "page": Optional[str], "actions": [...], "populate": {"target": str, "data": dict}}}
```

**理由**: 管道层只需要读一个统一结构，不需要 per-tool 的 switch-case。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| tool 返回 `_route` 格式不统一 | 定义 `RouteHint` TypedDict 或 Pydantic model，tool 必须遵守 |
| LLM 选 tool 仍可能出错 | 关键词规则兜底增强（`_keyword_fallback` 现在推荐 tool） |
| navigate 和 chat 边界模糊（"帮我打开诊断页面看看"） | 这种表述本身就是 navigate（用户要打开页面），LLM 能正确识别；模糊时默认走 chat（让 tool 决定更安全） |
| 旧前端依赖特定事件格式 | `_route` 中的字段名与现有 SSE 事件（navigate/populate/action）保持一致，前端无感 |
| 两分类后分类器误判率未知 | 需跑 `evals/test_classifier.py` 对比改前改后准确率 |

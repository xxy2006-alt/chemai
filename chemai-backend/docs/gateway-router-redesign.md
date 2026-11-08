# Gateway 路由架构重构设计

> 状态：待评审 | 日期：2026-06-18

## 1. 现状

当前架构是三阶段的 LLM 分类 + Agent 执行管道：

```
用户消息
  → [Phase 1] IntentClassifier (LLM) 输出 {intent, page, params, tools, provider}
      intent ∈ {chat, page_action, hybrid}
  → [Phase 2] Agent 工厂按 tools 交集注册工具，执行
  → [Phase 3] build_navigate_events() 按 intent 类型决定是否跳页
```

**三类 intent 的语义：**

| intent | 含义 | 触发条件（当前） |
|--------|------|-----------------|
| `chat` | 纯对话，不跳页 | 问答、查单个学生 |
| `page_action` | 直接跳页，不调 tool | "打开考试工作台" |
| `hybrid` | 先调 tool 生成数据，再跳页展示 | "给张三出5道盐水解题" |

**问题：**

1. LLM 分类器承担了太多决策——intent、page、params、tools、provider 五个维度全由一个 prompt 输出，出错面大
2. `hybrid` 和 `chat` 的边界在 prompt 里靠自然语言描述，容易误判（"查张梦琪"到底是 chat 还是 hybrid？）
3. 路由决策（跳不跳页）和 tool 筛选耦合在同一个 LLM 调用里
4. `page_action` 里"不调 tool 只跳页"和"跳页 + 调 tool"的区分不够清晰

---

## 2. 新架构：三大前提（已审核）

### 前提 1：Gateway 只保留 tool 筛选，不再管页面路由

**结论：通过。**

Gateway（IntentClassifier）的职责收缩为一项：根据用户消息推荐候选 tool 列表。不再输出 `intent`、`page`、`params`。

- 保留 LLM 分类器的 tool 推荐能力
- **新增关键词规则兜底**——LLM 可能选错 tool，关键词匹配作为最后一道防线（如"出题"→`generate_questions`，"诊断"→`diagnose_barrier`）
- 去掉 prompt 中的 intent/page/params/provider 字段

**Gateway 新输出格式：**

```json
{
  "tools": ["generate_questions"],
  "provider": "deepseek"
}
```

### 前提 2：路由决策由 tool 返回值决定，依据参数语义而非数据条数

**结论：方向通过，规则修正。**

子 Agent 审核发现：原始方案"按返回数据条数判断"有缺陷——查 2 个人和查 34 个人在意图上可能相同（都是点名查），不应因条数不同而产生不同路由行为。

**修正后的判断规则：**

```
用户参数中有 student_name / student_id  →  单人查询  →  不跳页（chat）
用户参数中只有 class_id / class_name    →  班级查询  →  跳页
无参数（纯知识问答）                      →  不跳页（chat）
```

这比"数据条数"更可靠，因为判断依据是**用户意图的语义边界**，而非 tool 执行的偶然结果。

路由逻辑放在 tool 函数内部——tool 执行完后检查自己的参数，返回时带上 `_route` 字段：

```python
# 示例：diagnose_barrier 的返回值
{
  "data": {...},
  "_route": {
    "navigate": True,            # 是否需要跳页
    "page": "diagnosis",          # 目标页面
    "actions": [                  # 前端 UI 操作
      {"action": "selectClass", "payload": "高三1班"}
    ],
    "populate": {                 # 填充到页面的数据
      "target": "diagnosis",
      "data": {...}
    }
  }
}
```

**谁负责路由：tool 自己。** Gateway 不再参与路由决策。

### 前提 3：砍掉 hybrid，简化为 chat / navigate 两分类

**结论：通过。** 这是前提 2 的自然结果。

既然路由由 tool 返回值决定，"先调 tool 再跳页"（hybrid）和"只 chat 不跳页"的区别就不需要 LLM 提前判断了。LLM 只需要选 tool，tool 执行后自己决定是否跳页。

`navigate` 缩小到**唯一的无参页面跳转**场景——用户说"去首页""打开考试工作台"，不需要调任何 tool。

| 新分类 | 含义 | Gateway 行为 |
|--------|------|-------------|
| `chat` | 需要调 tool（可能跳也可能不跳，tool 自己决定） | 输出 tool 列表 |
| `navigate` | 不需要调 tool，直接跳页 | 输出 page，不输出 tool |

**Gateway 新 prompt 核心逻辑：**

```
用户消息是否需要调用工具？
  - 需要 → chat，输出 tools
  - 不需要（纯页面跳转，如"打开考试工作台""去首页"）→ navigate，输出 page
```

**一句话总结：Gateway 只回答两个问题——"调哪个 tool？"和"是不是纯跳页？"。路由交给 tool。**

---

## 3. 新架构全貌

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
│  兜底：关键词规则（LLM 失败时）        │
└──────────────────────────────────────┘
  │
  ├─ type=navigate → 直接发送 navigate 事件，不走 Agent
  │
  └─ type=chat → Agent 执行
       │
       ▼
  ┌──────────────────────────────────────┐
  │  Agent (pydantic-ai)                 │
  │                                      │
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

---

## 4. 需要修改的文件

| 文件 | 改动 |
|------|------|
| `agent/gateway.py` | 重写 `CLASSIFY_PROMPT`，去掉 intent/page/params 字段，改为 `type` + `tools` 两字段；重写 `_keyword_fallback`；删除 `build_navigate_events()` 和 `_PAGE_ACTIONS` 映射 |
| `agent/agents.py` | 无改动（tool 交集逻辑不变） |
| `agent/channel/fastapi_sse.py` | 简化 Phase 3：不再调用 `build_navigate_events`，改为读取 tool 返回值的 `_route` 字段；`navigate` 类型直接发送跳页事件 |
| `agent/tools.py` | 各 tool 函数返回值加上 `_route` 字段（diagnose_barrier、generate_questions、weekly_report 等涉及页面展示的 tool） |
| `agent/sse_adapter.py` | 可能需要适配 `_route` 事件的 SSE 输出 |

---

## 5. 迁移步骤

1. **tool 层加 `_route`**：给 `diagnose_barrier`、`generate_questions`、`weekly_report`、`search_exam_bank` 等 tool 的返回值加 `_route` 字段，按"参数中是否有 student_name"判断 navigate
2. **Gateway 改 prompt**：将三分类 prompt 改为两分类（chat/navigate），去掉 page/params/intent 输出
3. **管道层适配**：`fastapi_sse.py` 读 `_route` 替代 `build_navigate_events()`
4. **删除旧代码**：移除 `build_navigate_events()`、`_PAGE_ACTIONS`、`_TOOL_POPULATE_TARGET`
5. **回归测试**：跑 `evals/test_classifier.py`，确保分类准确率不降

---

## 6. 关键边界场景

| 用户输入 | Gateway 输出 | Tool 路由 |
|---------|-------------|----------|
| "张梦琪最近错题多吗" | chat, tools=[diagnose_barrier] | student_name 存在 → 不跳 |
| "高三1班诊断情况" | chat, tools=[diagnose_barrier] | 只有 class_name → 跳 diagnosis |
| "给张三出5道盐类水解" | chat, tools=[generate_questions] | student_name 存在 → 不跳（题在 chat 里展示即可） |
| "出一份期中试卷" | chat, tools=[generate_questions] | 无 student → 跳 exam-v2 |
| "打开考试工作台" | navigate, page=exam-v2 | 不走 Agent |
| "什么是氧化还原" | chat, tools=[chemistry_tutor] | 纯知识 → 不跳 |

---

## 7. 风险与缓解

| 风险 | 缓解 |
|------|------|
| tool 返回 `_route` 格式不统一 | 定义 `RouteHint` TypedDict，所有 tool 共用 |
| LLM 选 tool 仍可能出错 | 关键词规则兜底（已有 `_keyword_fallback`，增强即可） |
| navigate 和 chat 边界模糊（"帮我打开诊断页面看看"） | 这种表述本身就是 navigate，LLM 能正确识别；模糊时默认走 chat（让 tool 决定） |
| 旧前端依赖 `populate`/`actions` 字段格式 | `_route` 中的字段名与现有 SSE 事件格式保持一致 |

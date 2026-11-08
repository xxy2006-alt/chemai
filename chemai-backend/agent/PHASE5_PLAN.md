# Phase 5: Agent 界面改造 — 详细设计

> 参考: 纸鸢AI (`D:\求职助手升级版`) 的 Agent 聊天 UI 模式

---

## 一、当前状态 vs 目标状态

```
当前 (index_new.html)              目标
──────────────────────────       ──────────────────────────
<div id="app"></div>             Agent 聊天主界面
侧边栏: 导航菜单                  侧边栏: 对话历史 + 功能快捷入口
主区域: 功能页面 (page-home等)    主区域: 聊天消息流
底部: 无                          底部: 输入框 + 快捷提问 + 文件上传
无状态栏                          底部状态栏: 当前Skill + 耗时
```

## 二、架构设计

```
┌──────────────────────────────────────────────────────────┐
│ index_new.html                                           │
│ ┌──────────┐ ┌─────────────────────────────────────────┐ │
│ │ 侧边栏    │ │ Agent 聊天区                             │ │
│ │          │ │                                        │ │
│ │ 📝 新对话 │ │ ┌────────────────────────────────────┐ │ │
│ │ ──────── │ │ │ 消息流（滚动）                      │ │ │
│ │ 对话历史  │ │ │                                    │ │ │
│ │ · 配平.. │ │ │  学生: 帮我配平 Fe + O2 = Fe2O3    │ │ │
│ │ · 盐类.. │ │ │                                    │ │ │
│ │ · 有机.. │ │ │  Agent: 好的，让我看看这个方程式... │ │ │
│ │          │ │ │  ┌─ ToolResultCard ──────────────┐ │ │
│ │ ──────── │ │ │  │ balance_equation  0.3s  ✅    │ │ │
│ │ 功能入口  │ │ │  │ Fe: 左1右2, O: 左2右3        │ │ │
│ │ 📋 题库  │ │ │  └──────────────────────────────┘ │ │
│ │ 📊 学情  │ │ │  这个方程式没有配平哦...           │ │
│ │ 📝 考试  │ │ │                                    │ │
│ │ ⚙️ 设置  │ │ └────────────────────────────────────┘ │
│ │          │ │ ┌────────────────────────────────────┐ │
│ │          │ │ │ 快捷提问: [出3道题] [模拟实验] ...  │ │
│ │          │ │ │ [📎 上传试卷]                       │ │
│ │          │ │ │ [输入框________________] [发送]     │ │
│ │          │ │ └────────────────────────────────────┘ │
│ │          │ │ ┌─ AgentStatusBar ──────────────────┐ │
│ │          │ │ │ 🔍 search_exam_bank · 1.2s        │ │
│ │          │ │ └───────────────────────────────────┘ │
│ └──────────┘ └─────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

## 三、需要新建/修改的文件

### 3.1 新建文件

| 文件 | 行数 | 作用 |
|------|------|------|
| `src/components/AgentChat.js` | ~400 | 主聊天组件（替代 HermesThinking.js 成为新UI） |
| `src/styles/agent.css` | ~200 | Agent 界面专用样式 |
| `src/modules/agent/index.js` | ~150 | Agent 模块初始化 + 消息管理 + SSE 连接 |

### 3.2 修改文件

| 文件 | 改动 |
|------|------|
| `index_new.html` | 首页改为 Agent 聊天布局 |
| `src/main.js` | 添加 `initAgentPage`，作为默认首页 |

### 3.3 不复用（删除/归档）

| 文件 | 原因 |
|------|------|
| `src/components/HermesThinking.js` (741行) | 被 AgentChat.js 替代，但保留作为模块内嵌组件 |
| `src/components/AgentThinking.js` (465行) | 同上 |

## 四、AgentChat 组件接口

```javascript
// src/components/AgentChat.js

/**
 * AgentChat — 化学 AI 聊天主界面
 *
 * 功能:
 * - SSE 流式消息渲染（rAF 动画）
 * - 快捷提问芯片（SuggestionChips）
 * - 文件上传（试卷 PDF/答题卡图片）
 * - 工具结果卡片（ToolResultCard）
 * - 状态栏（AgentStatusBar: 当前 Skill + 耗时）
 * - 对话历史侧边栏
 */

// 事件类型（参考纸鸢AI 的 25 种 SSE 事件，精简为 10 种）
const AgentEventType = {
  PHASE: 'phase',               // 阶段切换（thinking/executing/reply）
  TEXT: 'text',                 // 流式文本块
  TOOL_CALL: 'tool_call',       // 工具调用开始
  TOOL_RESULT: 'tool_result',   // 工具执行结果
  TOOL_ERROR: 'tool_error',     // 工具错误
  SUGGESTION: 'suggestion',     // AI 建议的下一步
  DONE: 'done',                 // 完成
  ERROR: 'error',               // 错误
}
```

## 五、SSE 事件流协议

ChemAgent 返回的 SSE 需要加入新的事件类型。修改 `agent/core.py` 的 `run_stream()`：

```python
async def run_stream(self, user_input, history=None):
    # Phase 1: Think
    yield f"data: {json.dumps({'type': 'phase', 'phase': 'thinking'})}\n\n"

    # Phase 2: 决定调用 Skill
    if decision["action"] == "use_skill":
        yield f"data: {json.dumps({'type': 'tool_call', 'name': skill_name, 'args': skill_args})}\n\n"

        # Phase 3: 执行
        result = await registry.execute(skill_name, skill_args)
        yield f"data: {json.dumps({'type': 'tool_result', 'name': skill_name, 'result': result})}\n\n"

    # Phase 4: 流式回复
    yield f"data: {json.dumps({'type': 'phase', 'phase': 'reply'})}\n\n"
    async for chunk in self._provider.chat_stream(messages):
        yield f"data: {json.dumps({'type': 'text', 'content': extract_delta(chunk)})}\n\n"

    # Phase 5: 完成
    yield f"data: {json.dumps({'type': 'done'})}\n\n"
```

## 六、前端接收逻辑

```javascript
// src/modules/agent/index.js

async function sendMessage(text) {
  const response = await fetch('/api/agent/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      persona: currentPersona,
      message: text,
      provider: 'deepseek',
      history: conversationHistory,
    }),
  })

  const reader = response.body.getReader()
  const decoder = new TextDecoder()

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    for (const line of decoder.decode(value).split('\n')) {
      if (line.startsWith('data: ')) {
        const event = JSON.parse(line.slice(6))
        handleEvent(event)  // 分发到 UI
      }
    }
  }
}

function handleEvent(event) {
  switch (event.type) {
    case 'phase':
      statusBar.setPhase(event.phase)
      break
    case 'text':
      messageBubble.appendText(event.content)  // rAF 动画
      break
    case 'tool_call':
      toolCard = showToolCard(event.name, 'running')
      statusBar.setTool(event.name)
      break
    case 'tool_result':
      toolCard.setResult(event.result)
      statusBar.clearTool()
      break
    case 'done':
      finalizeMessage()
      break
  }
}
```

## 七、SuggestionChips（快捷提问）

```javascript
// 根据当前 context 动态生成快捷提问
const DEFAULT_CHIPS = [
  { icon: '⚖️', label: '配平方程式', prompt: '帮我配平 Fe + O2 = Fe2O3' },
  { icon: '📝', label: '出3道题', prompt: '出3道关于盐类水解的练习题' },
  { icon: '🔬', label: '模拟实验', prompt: '模拟钠与水的反应实验' },
  { icon: '📖', label: '讲概念', prompt: '请讲解氧化还原反应的基本概念' },
  { icon: '🔍', label: '查真题', prompt: '搜索关于化学平衡的高考真题' },
]
```

## 八、Sidebar 设计

```
┌─────────────┐
│ 🆕 新对话    │
├─────────────┤
│ 📜 历史对话  │
│ · 配平练习   │
│ · 盐类水解   │
│ · 有机物命名  │
├─────────────┤
│ 📋 题库管理  │  ← 跳转到原功能页面
│ 📊 学情面板  │
│ 📝 考试管理  │
│ 🎓 学生管理  │
│ ⚙️ 系统设置  │
└─────────────┘
```

对话历史存储在 `sessionStorage`（单会话内），不引入 IndexedDB。

## 九、实施步骤

### Step 1: 后端 SSE 事件扩展 (~15min)
- `agent/core.py` — `run_stream()` 加入 phase/tool_call/tool_result/text/done 事件
- `agent/channel/fastapi_sse.py` — 保持兼容

### Step 2: Agent 聊天组件 (~30min)
- `src/components/AgentChat.js` — 消息渲染 + SuggestionChips + ToolResultCard + StatusBar
- `src/styles/agent.css` — 聊天界面样式

### Step 3: Agent 模块初始化 (~15min)
- `src/modules/agent/index.js` — SSE 连接 + 事件处理 + 消息管理

### Step 4: 首页改造 (~10min)
- `index_new.html` — 改为 Agent 布局
- `src/main.js` — `initAgentPage()` 作为默认首页

### Step 5: 侧边栏整合 (~10min)
- 保留现有功能入口（题库、学情、考试管理），作为侧边栏导航项

---

总预估: ~80min

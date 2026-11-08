## Why

当前 agent 是一个聊天框——用户说"给张三出5道盐类水解的题"，agent 在聊天框里生成文字回复，然后用户必须手动打开考试工作台、手动复制粘贴题目。agent 和前端各页面之间有完全的断层：意图识别靠 6 个中文 keyword 匹配，前端页面各自独立调用 REST API 绕过 agent，agent 不知道页面能做什么、页面不知道 agent 做了什么。

Phase 1（agent-exec-loop-fix）修好了底盘让 agent 能多步执行。Phase 2 要让 agent 成为真正的中央协调器——能理解用户意图、提取参数、执行 skills、然后**驱动前端页面**自动跳转和填充数据。

## What Changes

### New: `agent/gateway.py` (~80 lines)
- `IntentClassifier` 类，用 LLM 做语义意图分类，替代 `core.py:246-261` 的 25 行 keyword matcher
- 单次轻量 LLM 调用（~500ms）返回结构化 `IntentResult`：`{intent, page, params, tools, provider}`
- 三种意图类型：`chat`（纯对话）、`page_action`（导航+填充）、`hybrid`（先执行 skills 再导航）
- 同时完成参数提取（学生姓名、知识点、难度等），之前完全没做

### Changed: `agent/core.py` (~25 lines)
- `run_stream()` 和 `run()` 中用 `self.gateway.classify()` 替换内联 `_classify()`
- `run_stream()` 根据 intent 在 tool 执行完成后 emit 新的 SSE 事件类型

### Changed: `frontend/js/agent.js` (~30 lines)
- SSE 事件 switch 中新增 `navigate`、`populate`、`action` 三个 case
- `navigate` → 写入 `sessionStorage.chemai_navigate`
- stream 结束后检查 sessionStorage，有 navigate 数据就 `window.location.href` 跳转

### Changed: 4 个页面（各 ~15 lines）
- `exam-v2.html`、`diagnosis.html`、`students.html`、`teacher.html`：`DOMContentLoaded` 时读取 `chemai_navigate`，自动填充数据/执行操作

### New SSE event types
- `navigate`: `{type:"navigate", page:"exam-v2", params:{...}}`
- `populate`: `{type:"populate", target:"questionList", data:[...]}`
- `action`: `{type:"action", action:"publishExam", payload:{...}}`

## Capabilities

### New Capabilities
- `llm-intent-classifier`: LLM 驱动的语义意图分类 + 参数提取，替代 keyword 匹配
- `sse-page-events`: SSE 协议扩展，agent 可指挥前端跳转页面/填充数据/触发操作
- `sessionstorage-bridge`: 跨页面数据传输通道，通过 sessionStorage 在页面间传递 agent 执行结果

### Modified Capabilities
<!-- 无现有 spec 需修改 -->

## Impact

- **Files changed**: `agent/gateway.py` (new, ~80 lines), `agent/core.py` (~25 lines), `frontend/js/agent.js` (~30 lines), `exam-v2.html` (~15 lines), `diagnosis.html` (~15 lines), `students.html` (~15 lines), `teacher.html` (~15 lines)
- **API**: `/api/agent/chat` 和 `/api/agent/chat/stream` 响应中新增 `navigate`/`populate`/`action` SSE 事件类型。**向后兼容**——旧前端忽略未知事件类型
- **Breaking**: 无。旧版 agent.js 的 switch 用 default 忽略未知事件，不受影响
- **Dependencies**: 依赖 Phase 1（agent-exec-loop-fix）完成后的多步执行能力

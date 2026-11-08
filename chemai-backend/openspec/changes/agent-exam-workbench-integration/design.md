## Context

ChemAI 的考试工作台 (`exam-v2.html`) 是一个完整的题目生成 UI：5 种题型（选择/填空/计算/实验/推断）每种独立数量、知识点多选、难度选择、变种蓝本（基于真题出变种题）、题库文件夹管理。`generate_questions` 工具在 Agent 侧独立实现了题目生成——调 LLM 出题、返回 JSON、在聊天里展示——完全绕过了考试工作台。

问题是 Agent 的工具参数边界比 UI 窄得多：没有题型参数、没有变种蓝本、没有文件夹选择。用户在聊天里看到不完整的结果，Agent 编造进度，跳转后页面空白。

## Goals / Non-Goals

**Goals:**
- Agent 不再在聊天里生成题目——只收集参数、导航、预填
- 考试工作台成为题目生成的唯一入口
- 用户从聊天→考试工作台的往返不丢失对话上下文
- 预填后自动触发生成，用户只需确认和保存

**Non-Goals:**
- 不改考试工作台页面本身的生成逻辑（`aiGenerate` 不变）
- 不改 `POST /api/question/generate` API
- 不改 LangGraph ReAct loop 架构
- 不删除 `generate_questions` 函数（考试工作台页面可能仍需要它）

## Decisions

### D1: Agent 不再生成题目

**选择**: `generate_questions` 从 `TOOLS` 列表移除。新增 `navigate_to_exam_workbench` 作为替代。

**理由**: Agent 调用 LLM 内部出题有两个不可修复的问题：LLM 诚信（结果不完整时编造解释）和能力边界（工具参数无法覆盖 UI 的 5 种题型×数量）。将题目生成移到考试工作台页面后，这两个问题消失——`aiGenerate()` 是确定性代码，不会编造；每个题型的 API 调用是独立的，数量精确。

**替代方案被拒绝**: 保持 `generate_questions` 并扩展参数。仍存在 LLM 诚信问题，且维护两套出题逻辑。

### D2: Bridge 自动触发 vs 用户手动触发

**选择**: Bridge pre-fill 后自动调用 `this.aiGenerate()`。

**理由**: Agent 已经通过对话收集了所有参数。再让用户点一次"AI 出题"是多余的——参数是用户亲口确认的。如果生成失败（API 错误等），页面展示错误 toast，用户可以调整后重试。

### D3: sessionStorage 持久化 conversation_id

**选择**: `agent.js` 在导航前 `sessionStorage.setItem('chemai_active_cid', cid)`，聊天页加载时读取。

**理由**: `conversation_id` 已经正确映射到 `thread_id`（`langgraph_channel.py` line 103）。问题只是前端切页面时丢了 `cid`。`sessionStorage` 是浏览器原生能力，零后端改动。关闭标签页自动清理，不泄漏。

### D4: `generate_questions` 函数保留

**选择**: 函数定义保留在 `tools.py` 中，但从 `TOOLS` 列表和 `TOOL_PREREQUISITES` 中移除。docstring 加 `[DEPRECATED for agent use]` 标记。

**理由**: 考试工作台页面的 `POST /api/question/generate` API 可能内部调用了相同的逻辑。保留函数定义避免破坏现有 API。Agent 只是不再能调用它。

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| 用户习惯在聊天里看到题目预览，改为跳转后体验不同 | 一旦跳转并生成完成，Agent 可在聊天里发一条摘要"已在考试工作台生成5道氧化还原选择题，请查看" |
| Bridge 自动生成失败时用户体验差 | `aiGenerate()` 本身有 toast 错误处理；Bridge 在 `$nextTick` 中调用，页面已渲染 |
| sessionStorage 在用户手动清除浏览器数据时丢失 | 这是预期行为——等同于新会话。MemorySaver 中的旧对话在超时后自动清理 |

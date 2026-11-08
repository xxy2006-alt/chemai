## Why

Agent 在聊天里直接调 LLM 出题——不问题型组成、结果不完整时编造"正在生成中"、跳转后页面空白、切页面丢失上下文。根因是 Agent 被设计成"对话式出题器"，但 ChemAI 已经有完整的考试工作台 UI（5 种题型、变种蓝本、题库文件夹、配平审核）。Agent 应该是"表单填写导航器"——收集参数、跳转预填、自动生成——而不是重复实现题目生成逻辑。

## What Changes

- **废弃 Agent 侧题目生成**：`generate_questions` 从 Agent 工具集中移除，不再在聊天里调 LLM 出题。消除 LLM 编造生成进度的诚信问题。
- **新增导航工具**：`navigate_to_exam_workbench` 收集完整参数（知识点、难度、题型×数量、变种蓝本、文件夹）后跳转考试工作台，预填所有字段并自动触发生成。
- **前端 Bridge 扩展**：`exam-v2.html` 新增 `exam-config` populate handler，接收 Agent 传来的预填参数并调用 `aiGenerate()`。
- **跨页面记忆**：`agent.js` 将 `conversation_id` 持久化到 `sessionStorage`，切页面不丢对话上下文。
- **LangGraph 架构零改动**：`create_react_agent`、`MemorySaver`、SSE、channel 端点全部不变。

## Capabilities

### New Capabilities
- `exam-workbench-navigation`: Agent 通过对话收集出题所需全部参数，调用 `navigate_to_exam_workbench` 跳转考试工作台并预填所有字段，自动触发题目生成
- `exam-config-bridge`: 前端 `exam-v2.html` 接收 Agent 传来的 `exam-config` populate 数据，预填知识点/难度/题型/变种蓝本/文件夹，自动调用 `aiGenerate()`
- `cross-page-memory`: `conversation_id` 通过 `sessionStorage` 在页面切换间持久化，Agent 对话上下文不丢失

### Modified Capabilities
<!-- No existing specs to modify -->

## Impact

- `agent/tools.py` — 废弃 `generate_questions`（保留函数供考试工作台页面调用，但从 Agent TOOLS 列表移除），新增 `navigate_to_exam_workbench` 工具（~60 行）
- `agent/langgraph_agent.py` — 从 `TOOL_PREREQUISITES` 移除 `generate_questions`（1 行）
- `frontend/pages/exam-v2.html` — 新增 `exam-config` bridge handler（~40 行）
- `frontend/js/agent.js` — `conversation_id` 持久化到 `sessionStorage`（~10 行）

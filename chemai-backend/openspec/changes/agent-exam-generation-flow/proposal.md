## Why

出题流程当前是两段式架构：Agent 触发 `show_exam_workbench` 打开面板后，面板绕开 Agent 直接调 `/api/question/generate` REST API。导致：工具卡片不显示、对话历史不保存到侧边栏、GuardState 护栏不生效、Agent 对出题结果毫不知情。出题是 ChemAI 最核心的教师工作流——它必须完整运行在 Agent 的 ReAct 循环内。

## What Changes

- `generate_questions` 工具复活并扩展参数（question_types、variant_qid、variant_source），返回 `_component` 更新面板
- 面板"AI 出题"按钮改为调 `/chat/langgraph/resume`，将参数发给 Agent
- `renderExamWorkbench` 支持更新模式（检测已有面板 → 原地更新题目列表）
- Agent 通过 LLM 判断参数齐全度：齐全则直接调 `generate_questions` 出题，不全则调 `show_exam_workbench` 开面板让用户补全

## Capabilities

### New Capabilities
- `agent-exam-generation`: Agent 作为出题流程的唯一执行路径，参数收集 → 工具调用 → 结果渲染全在 ReAct 循环内

### Modified Capabilities
- `exam-workbench-panel`: 面板"AI 出题"按钮不再直接调 REST API，改为通过 Agent resume 机制发起出题请求

## Impact

- 受影响的代码：`agent/tools.py`（generate_questions 复活）、`frontend/js/agent.js`（resume 替代 fetch、面板更新模式）
- 受影响的测试：`evals/agent_eval_golden.yaml`（恢复 generate_questions 用例）、`evals/test_langgraph_agent.py --inline-panel`
- 不受影响：`show_exam_workbench` 工具、SSE adapter、v2 agent core、REST `/api/question/generate`（保留兼容）

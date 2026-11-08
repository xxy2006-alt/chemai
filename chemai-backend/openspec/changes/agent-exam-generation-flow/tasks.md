## 1. generate_questions 工具复活

- [x] 1.1 移除 `[DEPRECATED for agent use]` 标记
- [x] 1.2 扩展参数：添加 `question_types` (list[dict])、`variant_qid`、`variant_source`
- [x] 1.3 工具描述重写为"何时用 / 会发生什么 / 下一步 / NOT for"格式
- [x] 1.4 支持 `_component` 返回（component="exam-workbench"，带题目列表）
- [x] 1.5 支持蓝本题作为 RAG 上下文（variant_qid 非空时跳过向量检索，直接用指定题）
- [x] 1.6 注册到 `TOOLS` 列表（已在列表中，确认没有被排除）
- [x] 1.7 设置 `TOOL_CALL_LIMITS["generate_questions"] = 3`

## 2. 面板"AI 出题"按钮改为 resume

- [x] 2.1 收集面板当前所有参数（kps、diff、types、variant）
- [x] 2.2 构造 resume 消息体（conversation_id + 结构化参数）
- [x] 2.3 替换 `fetch('/api/question/generate', ...)` 为 `fetch('/api/agent/chat/langgraph/resume', ...)`
- [x] 2.4 resume 的 SSE 流中收到 component 事件时更新面板题目

## 3. renderExamWorkbench 更新模式

- [x] 3.1 检测 DOM 中是否已有 `.inline-exam-panel`
- [x] 3.2 已有面板时：更新 `.exam-qcards` 题目列表，不重复创建面板
- [x] 3.3 首次调用时：正常创建面板（现有逻辑不变）

## 4. Agent system prompt 更新

- [x] 4.1 添加出题决策指引：参数齐全→generate_questions，不全→show_exam_workbench
- [x] 4.2 明确 generate_questions 所需参数：knowledge_points + question_types + difficulty

## 5. 测试更新

- [x] 5.1 `evals/agent_eval_golden.yaml`：恢复 `generate_questions` 测试用例
- [x] 5.2 `evals/agent_eval_golden.yaml`：添加"参数不全→show_exam_workbench"用例
- [x] 5.3 boundary 测试通过 (20/20)
- [ ] 5.4 端到端手动测试：路径 A（参数齐全直接出题）—— 待用户测试
- [ ] 5.5 端到端手动测试：路径 B（参数不全→面板补全→resume→出题）—— 待用户测试

## Context

出题流程是 ChemAI 最核心的教师工作流。当前架构中，Agent 和前端面板各自为政，出题面板直接调 REST API 绕过了 Agent 的 ReAct 循环。本设计将出题流程完整纳入 Agent 控制。

## Goals / Non-Goals

**Goals:**
- Agent 是出题的唯一执行路径，所有出题请求经过工具调用
- 工具卡片（tool_call/tool_result）正常渲染在对话中
- 对话历史自动保存（包括当出题面板展示时）
- GuardState 护栏对出题请求生效（去重、调用上限）
- 两种路径：参数齐全→直接出题；参数不全→面板补全→resume→出题

**Non-Goals:**
- 不改变 `show_exam_workbench` 工具的职责（仍然只是打开面板）
- 不改变蓝本题浏览、知识点搜索等纯 UI 交互（仍走前端直接 fetch）
- 不在 generate_questions 内部自动保存（用户保留决策权）
- 不改变 SSE 事件格式或 adapter

## Decisions

### D1: "AI 出题"按钮走 resume，不走新 endpoint

面板收集完参数后通过 `POST /chat/langgraph/resume` 发给 Agent，Agent 在 ReAct 循环内调 `generate_questions`。不在 `langgraph_channel.py` 加新端点。

**理由:** resume 是 LangGraph 原生机制，复用现有 endpoint 和 SSE 流；Agent 状态（thread_id、checkpoint）自然保留。

### D2: generate_questions 返回 _component 而非纯文本

工具执行完返回 `{questions: [...], _component: {component: "exam-workbench", params: {...}}}`。前端收到 `component` SSE 事件后调用 `renderExamWorkbench` 渲染。

**理由:** _component 是现有机制（show_exam_workbench 已在用），前端有完整的处理管道。不走 `navigate`（那会导致页面跳转，破坏对话上下文）。

### D3: renderExamWorkbench 支持"更新模式"

首次调：创建面板 DOM。后续调（收到 generate_questions 的 _component）：检测到已有面板 → 更新题目列表和状态栏，不重复创建。

**理由:** 如果每次 _component 都新建面板，用户会看到面板堆叠。更新已有面板保持 UI 连贯。

### D4: Agent LLM 自行判断参数齐全度

不设硬编码规则（"有知识点+有题型+有数量=齐全"）。Agent 的 system prompt 告诉它 `generate_questions` 需要哪些参数，LLM 自己判断消息中是否足够。

**理由:** ADR-0001 的核心原则："信任工具描述，不写手写规则列表"。LLM 判断比硬编码更灵活（比如"出点关于有机的题"虽然是模糊需求，但 Agent 可以根据上下文决定是否直接出）。

### D5: 参数不全时 Agent 调 show_exam_workbench

不追问。直接打开面板，能预填的参数预填上（如用户说了"氧化还原"，预填知识点字段）。让用户在 UI 里补全，比对话式追问快。

**理由:** 当前面板已支持全部参数配置（知识点搜索、题型×数量、难度、蓝本题），用户一次全选完比多轮对话高效。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| Agent LLM 误判参数齐全度（以为够了实际不够） | 用户可以不在面板里点"AI 出题"而是直接补充文字消息；面板始终显示当前参数，用户可见可改 |
| resume 的 thread_id 丢失导致 Agent 找不到上下文 | 前端已有 currentConvId 机制，resume 重用它 |
| generate_questions 内部调 LLM 超时，ReAct 循环卡住 | TOOL_CALL_LIMITS["generate_questions"] = 3 限制重试；超时返回 error，Agent 告知用户 |

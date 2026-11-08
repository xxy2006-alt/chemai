# OCR Agent Tools

Agent 对话页面的答题卡批改交互——查进度、触发批改、保存结果。

## ADDED Requirements

### REQ-AGENT-001: Query Progress Tool
新增 `query_ocr_progress` tool，加入 teacher persona。

**Acceptance:**
- 老师问"识别进度" → Agent 调 tool → 返回每批每张的状态和百分比
- 示例输出：`批1: 5/10 完成, 1张处理中(83%), 4张排队中`
- Tool docstring 描述何时用、返回什么

### REQ-AGENT-002: Grading Trigger Tool
新增 `grade_answer_sheets` tool，加入 teacher persona。

**Acceptance:**
- 老师确认批改 → Agent 调 tool → 触发 LLM 对已完成识别的答题卡逐张批改
- Tool 接受 `batch_id` 或 `task_ids[]`
- 返回逐学生的结果卡片数据
- 老师可以在 Chat 中看到卡片预览

### REQ-AGENT-003: Save Results Tool
新增 `save_grading_results` tool，加入 teacher persona。

**Acceptance:**
- 老师确认结果 → Agent 调 tool → 批量写入 StudentAnswer
- Tool 接受 `batch_id`，读取已批改但在确认的 OCR 任务数据
- 触发 barrier 诊断 pipeline
- 返回班级统计汇总

### REQ-AGENT-004: Teacher Persona Integration
3 个新 tool 的 TOOL_META 注册为 `"personas": ["teacher"]`。

**Acceptance:**
- `teacher.yaml` 的 available_skills 自动包含 3 个新 tool
- Test: `test_tool_filtering.py` 验证 teacher 有 3 个 tool

## ADDED Requirements

### Requirement: SSE adapter emits component event
系统 SHALL 在 `LangGraphSSEAdapter.finalize()` 中，当 `guard_state.last_component` 存在时，发射 `component` SSE 事件。

#### Scenario: Component event emitted before done
- **WHEN** `guard_state.last_component` 包含 `{"component": "exam-workbench", "params": {...}}`
- **THEN** `finalize()` 返回的事件列表第一个为 `{"type": "component", "component": "exam-workbench", "params": {...}}`

#### Scenario: No component event when last_component is None
- **WHEN** `guard_state.last_component` 为 `None`
- **THEN** `finalize()` 不包含 `component` 类型事件

### Requirement: Frontend renders inline panel for component event
系统 SHALL 在 `agent.js` 中处理 `component` SSE 事件，构建内联 HTML 考试工作台面板。

#### Scenario: Panel renders with pre-filled params
- **WHEN** 前端收到 `{"type": "component", "component": "exam-workbench", "params": {"knowledge_points": ["氧化还原"], "difficulty": "medium", "types": [{"val": "single_choice", "active": true, "qty": 3}]}}`
- **THEN** 在 Agent 消息气泡下方插入内联面板
- **AND** 面板显示"知识点: 氧化还原 ✓"
- **AND** 面板显示"难度: 中等 ✓"
- **AND** 面板显示"题型: 选择题×3 ✓"
- **AND** 面板包含"生成题目"按钮

#### Scenario: Generate button calls question API
- **WHEN** 用户点击"生成题目"按钮
- **THEN** 面板调用 `POST /api/question/generate` 传入预填参数
- **AND** 生成的题目渲染在面板的题目展示区

#### Scenario: Question save/edit/delete works in panel
- **WHEN** 题目展示在面板中
- **THEN** 每道题有"编辑"、"保存"、"删除"操作按钮
- **AND** "保存"调用 `POST /api/exam-bank/import-questions`
- **AND** "删除"从面板中移除该题

#### Scenario: Panel is dismissible
- **WHEN** 用户点击面板的"完成"按钮
- **THEN** 面板从聊天界面中移除
- **AND** 系统发送一条总结消息到 Agent（"已在考试工作台生成3道氧化还原选择题"）

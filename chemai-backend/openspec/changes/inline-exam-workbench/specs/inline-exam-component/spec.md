## ADDED Requirements

### Requirement: show_exam_workbench returns component directive
系统 SHALL 提供 `show_exam_workbench` 工具，接受知识点、难度、题型及数量、变种蓝本、目标文件夹参数，返回 `_component` 指令而非 `_route` 导航指令。

#### Scenario: Tool returns component with all params
- **WHEN** `show_exam_workbench(knowledge_points="氧化还原,电化学", difficulty="medium", question_types="single_choice:5,fill_blank:2", variant_source="2024全国卷", set_name="期中复习")` 被调用
- **THEN** 返回 JSON 包含 `_component.component = "exam-workbench"`
- **AND** `_component.params` 包含 `knowledge_points: ["氧化还原", "电化学"]`, `difficulty: "medium"`, `types: [{val: "single_choice", active: true, qty: 5}, {val: "fill_blank", active: true, qty: 2}]`, `variant_source: "2024全国卷"`, `set_name: "期中复习"`
- **AND** 不包含 `_route` 字段

#### Scenario: Knowledge points and question types are required
- **WHEN** `show_exam_workbench(knowledge_points="")` 被调用
- **THEN** `GuardState.check_prerequisites` 拦截调用，返回 `knowledge_points` 缺失错误
- **WHEN** `show_exam_workbench(question_types="")` 被调用
- **THEN** `GuardState.check_prerequisites` 拦截调用，返回 `question_types` 缺失错误

### Requirement: Component is stripped from LLM context
系统 SHALL 在 `_guarded` 包装器中剥离 `_component` 字段并存储到 `GuardState.last_component`，确保 LLM 看不到 `_component` 指令。

#### Scenario: _component stored, not leaked to LLM
- **WHEN** `show_exam_workbench` 返回 `{"_component": {...}}`
- **THEN** `guard_state.last_component` 包含完整的 `_component` 数据
- **AND** LLM 收到的 ToolMessage content 不包含 `_component` 字段

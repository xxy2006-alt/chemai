## ADDED Requirements

### Requirement: navigate_to_exam_workbench tool exists
系统 SHALL 提供 `navigate_to_exam_workbench` 工具，接受知识点、难度、题型及数量、变种蓝本、目标文件夹参数，生成 `_route` 数据跳转到考试工作台并预填所有字段。

#### Scenario: Tool accepts all exam workbench parameters
- **WHEN** Agent 调用 `navigate_to_exam_workbench(knowledge_points="氧化还原,电化学", difficulty="medium", question_types="single_choice:5,fill_blank:2", variant_source="2024全国卷", set_name="期中复习")`
- **THEN** 返回 `_route` 包含 `navigate: True, page: "exam-v2"`
- **AND** `populate.target` 为 `"exam-config"`
- **AND** `populate.data` 包含 `knowledge_points: ["氧化还原", "电化学"]`, `difficulty: "medium"`, `types: [{val: "single_choice", active: true, qty: 5}, {val: "fill_blank", active: true, qty: 2}]`, `variant_source_id`, `selectedFolder`

#### Scenario: Minimal parameters still work
- **WHEN** Agent 调用 `navigate_to_exam_workbench(knowledge_points="氧化还原")`
- **THEN** 返回有效的 `_route` 数据
- **AND** 未提供的字段（difficulty, types 等）使用默认值或省略

### Requirement: generate_questions removed from agent tool set
系统 SHALL 从 `TOOLS` 列表和 `TOOL_PREREQUISITES` 字典中移除 `generate_questions`。函数定义保留但 Agent 无法调用。

#### Scenario: Agent cannot call generate_questions
- **WHEN** Agent 使用 persona="tutor" 创建
- **THEN** 可用工具列表中不包含 `generate_questions`
- **AND** 包含 `navigate_to_exam_workbench`

#### Scenario: generate_questions function still exists
- **WHEN** 导入 `from agent.tools import generate_questions`
- **THEN** 函数可正常导入和调用
- **AND** docstring 包含 `[DEPRECATED for agent use]` 标记

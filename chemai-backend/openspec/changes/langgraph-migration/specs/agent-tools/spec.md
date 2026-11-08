# Spec: Agent Tools

## ADDED Requirements

### Requirement: Tool 注册
系统 SHALL 将 persona YAML 的 available_skills 映射为 LangChain @tool 列表。

#### Scenario: 批量包装
- **GIVEN** persona="tutor", available_skills=["chemistry_tutor", "search_exam_bank", "web_search", "generate_questions", "simulate_experiment", "balance_equation"]
- **WHEN** 调用 `get_tools_for_persona("tutor")`
- **THEN** 返回 6 个 LangChain BaseTool 实例
- **AND** 每个 tool 的 func 属性为 tools.py 中的原始 async 函数
- **AND** 不创建 per-tool wrapper 文件

#### Scenario: 追加 request_approval
- **GIVEN** 任意 persona
- **WHEN** 调用 `get_tools_for_persona(persona)`
- **THEN** 返回的 tool 列表包含 request_approval

### Requirement: request_approval Tool
系统 SHALL 提供 `request_approval` tool，供 LLM 在需要人为确认时调用。

#### Scenario: 正常调用
- **GIVEN** LLM 决定需要老师确认
- **WHEN** LLM 调用 request_approval(message="请确认这5道题是否可以？", context="5道氧化还原选择题, 中等难度")
- **THEN** 函数内部调用 `interrupt({"type": "approval", "message": "...", "context": "..."})`
- **AND** graph 暂停, state checkpointed
- **AND** resume 时 interrupt() 返回用户输入

#### Scenario: 描述信息指引 LLM 不过度使用
- **GIVEN** tool 的 description 文本
- **WHEN** LLM 阅读 tool 列表
- **THEN** description 应包含 "只在真正需要人为判断时调用，不要每步都问"
- **AND** description 应包含 "例如：出完题后请老师预览、导入试卷前确认来源、布置练习前确认班级"

### Requirement: requires_approval 标记
系统 SHALL 标记破坏性操作为 requires_approval，并在执行层强制检查。

#### Scenario: 标记 destructive tools
- **GIVEN** 所有注册的 tool
- **WHEN** 检查 tool metadata
- **THEN** assign_adaptive_practice 标记为 requires_approval=True
- **AND** import_exam_paper 标记为 requires_approval=True
- **AND** generate_questions 标记为 requires_approval=False
- **AND** search_exam_bank 标记为 requires_approval=False
- **AND** chemistry_tutor 标记为 requires_approval=False

#### Scenario: 跳过审批直接调用被拒绝
- **GIVEN** LLM 尝试在当前 turn 未调用 request_approval 的情况下直接调用 assign_adaptive_practice
- **WHEN** tool 执行前检查
- **THEN** tool 被阻止执行
- **AND** 返回 error 消息: "此操作需要老师确认。请先调用 request_approval。"
- **AND** LLM 收到 error 后可以调 request_approval 或改变策略

#### Scenario: 审批后允许调用
- **GIVEN** 同一 turn 内已经调用过 request_approval 并获得批准
- **WHEN** LLM 调用 assign_adaptive_practice
- **THEN** tool 正常执行

### Requirement: _route 字段保留
系统 SHALL 保留所有现有 tool 返回值中的 `_route` 字段不变。

#### Scenario: generate_questions _route
- **GIVEN** 调用 generate_questions(..., student_name="张三")
- **WHEN** 检查返回值
- **THEN** `_route.navigate=False`

#### Scenario: generate_questions _route (无 student, 跳页)
- **GIVEN** 调用 generate_questions(..., student_name="")
- **WHEN** 检查返回值
- **THEN** `_route.navigate=True, page="exam-v2"`

#### Scenario: diagnose_barrier _route (单人)
- **GIVEN** 调用 diagnose_barrier(student_id="S001")
- **WHEN** 检查返回值
- **THEN** `_route.navigate=False`

#### Scenario: diagnose_barrier _route (班级)
- **GIVEN** 调用 diagnose_barrier(class_id="C001")
- **WHEN** 检查返回值
- **THEN** `_route.navigate=True, page="diagnosis"`

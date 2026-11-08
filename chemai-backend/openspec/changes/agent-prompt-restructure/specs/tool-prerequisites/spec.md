## ADDED Requirements

### Requirement: Tools declare required context fields
系统 SHALL 定义 `TOOL_PREREQUISITES` 字典，为每个需要上下文的工具声明必填字段。当前声明：`generate_questions: ["knowledge_points"]`、`diagnose_barrier: ["student_id_or_class_id"]`、`weekly_report: ["student_id_or_class_id"]`、`assign_adaptive_practice: ["student_id_or_class_id"]`。

#### Scenario: Prerequisites defined for generate_questions
- **WHEN** 查看 `TOOL_PREREQUISITES["generate_questions"]`
- **THEN** 返回 `["knowledge_points"]`

#### Scenario: Tools without prerequisites are not listed
- **WHEN** 查看 `TOOL_PREREQUISITES["search_exam_bank"]`
- **THEN** 返回空或不存在（搜索工具无前置条件）

### Requirement: GuardState checks prerequisites before tool execution
系统 SHALL 在 `GuardState.check_prerequisites(name, kwargs)` 中检查工具的必填字段。如果任何必填字段为空或仅含空白字符，返回错误消息；否则返回 None。

#### Scenario: Prerequisites met — tool executes normally
- **WHEN** `check_prerequisites("generate_questions", {"knowledge_points": "氧化还原", "difficulty": "medium"})` 被调用
- **THEN** 返回 None（所有必填字段有值）

#### Scenario: Prerequisites not met — tool blocked
- **WHEN** `check_prerequisites("generate_questions", {"knowledge_points": "", "difficulty": "medium"})` 被调用
- **THEN** 返回 `"缺少必要信息: knowledge_points。请先向用户确认。"`

#### Scenario: No prerequisites for tool — passes through
- **WHEN** `check_prerequisites("search_exam_bank", {"keyword": "氧化还原"})` 被调用
- **THEN** 返回 None

### Requirement: Prerequisite check runs before all other guardrails
系统 SHALL 在 `_make_guarded_tool` 的 guarded wrapper 中，最优先执行 `check_prerequisites()`。只有通过前置条件检查后，才继续执行 call limit 检查、dedup 检查和工具执行。

#### Scenario: Prerequisites checked before call limit
- **WHEN** `generate_questions` 第 4 次被调用，且 knowledge_points 为空
- **THEN** 返回的是前置条件错误消息（"缺少必要信息"）
- **AND** 不是调用次数超限错误消息

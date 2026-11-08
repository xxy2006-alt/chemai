## MODIFIED Requirements

### Requirement: diagnose_barrier 班级级返回 _component 而非 _route
系统 SHALL 在 `diagnose_barrier` 传入 `class_id` 时返回 `_component: {component: "diagnosis", params: {...}}` 而非 `_route: {navigate: True, page: "diagnosis"}`。

#### Scenario: 班级诊断不跳转
- **WHEN** Agent 调用 `diagnose_barrier(class_id="C001")`
- **THEN** 返回 JSON 包含 `_component: {component: "diagnosis", params: {student_name: ..., barrier_distribution: ..., exercises_completed: ...}}`
- **AND** 不包含 `_route: {navigate: True}`

#### Scenario: 单学生诊断不变
- **WHEN** Agent 调用 `diagnose_barrier(student_id="S001")`
- **THEN** 返回 JSON 包含诊断数据
- **AND** 不包含 `_route` 或 `_component`
- **AND** `navigate` 为 `False`

### Requirement: weekly_report 班级级不跳转
系统 SHALL 在 `weekly_report` 班级级调用时不返回 `_route: {navigate: True}`。

#### Scenario: 班级周报不导航
- **WHEN** `class_name` 有值且无 student_id/student_name（`_is_class = True`）
- **THEN** 返回 JSON 包含 `student_name`, `report`, `exam_count`
- **AND** 不包含 `_route` 字段

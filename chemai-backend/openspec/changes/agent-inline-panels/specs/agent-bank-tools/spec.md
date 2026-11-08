## ADDED Requirements

### Requirement: list_banks tool lists question banks
系统 SHALL 提供 `list_banks` 工具，列出当前已有的题库文件夹供 Agent 告知用户。

#### Scenario: List all banks
- **WHEN** Agent 调用 `list_banks()`
- **THEN** 返回题库列表（set_id、name、question_count）
- **AND** 结果在聊天中展示为列表

### Requirement: delete_bank tool removes a question bank
系统 SHALL 提供 `delete_bank` 工具，删除指定题库文件夹。需 `request_approval` 确认。

#### Scenario: Delete bank requires approval
- **WHEN** Agent 调用 `delete_bank(set_id="...")`
- **THEN** `GuardState` 阻止调用（requires_approval 标记）
- **AND** 提示 Agent 先调 `request_approval`

#### Scenario: Delete bank after approval
- **WHEN** `request_approval` 已调用且用户确认
- **THEN** `delete_bank` 执行成功
- **AND** 返回被删除的题库名称和题目数量

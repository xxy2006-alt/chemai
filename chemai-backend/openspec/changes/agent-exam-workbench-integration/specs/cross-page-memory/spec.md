## ADDED Requirements

### Requirement: conversation_id survives page navigation
系统 SHALL 确保 Agent 对话上下文在用户从聊天页切换到考试工作台再返回聊天页时完整保留。

#### Scenario: Agent remembers previous context after page round-trip
- **WHEN** 用户在聊天中说"出3道氧化还原选择题"
- **AND** Agent 反问确认参数后导航到 exam-v2
- **AND** 用户在 exam-v2 完成操作后返回聊天
- **THEN** 用户发送"把难度改成困难"
- **AND** Agent 理解"难度"指的是之前讨论的氧化还原题目
- **AND** Agent 使用同一个 `conversation_id` 对应的 `thread_id` 恢复对话状态

#### Scenario: New browser tab is independent
- **WHEN** 用户在新标签页打开聊天
- **THEN** 新标签页有独立的 `conversation_id`
- **AND** 不受其他标签页的对话上下文影响

#### Scenario: sessionStorage cleared on tab close
- **WHEN** 用户关闭浏览器标签页
- **THEN** `sessionStorage` 中的 `chemai_active_cid` 被自动清除
- **AND** 新打开的标签页不携带旧对话上下文

## ADDED Requirements

### Requirement: 分层记忆管理
系统 SHALL 提供 `MemoryStack` 类管理对话上下文，包含工作记忆（最近 20 轮对话）和情景记忆（关键事件如诊断结果）。

#### Scenario: 滑动窗口自动淘汰
- **WHEN** 对话超过 20 轮
- **THEN** 最早的对话自动被移除，保持上下文在 20 轮以内

#### Scenario: 加载学生画像
- **WHEN** 调用 `memory.load_student("202610101")`
- **THEN** 从数据库加载该学生的障碍类型、薄弱知识点信息，注入到上下文中

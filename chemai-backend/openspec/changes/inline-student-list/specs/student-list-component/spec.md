## ADDED Requirements

### Requirement: show_students 工具返回 _component 指令
系统 SHALL 提供 `show_students` 工具，查询班级学生列表，返回 `_component` 指令触发前端渲染学生列表面板。

#### Scenario: 按班级查询学生列表
- **WHEN** Agent 调用 `show_students(class_id="C001", class_name="高三1班")`
- **THEN** 返回 JSON 包含 `_component: {component: "student-list", params: {students: [...], class_name: "高三1班"}}`
- **AND** students 数组每项包含 `student_id`, `name`, `dominant_barrier`, `barrier_score`, `exercises_completed`

#### Scenario: 按障碍类型筛选
- **WHEN** Agent 调用 `show_students(class_id="C001", filter_barrier="计算能力")`
- **THEN** 仅返回 dominant_barrier 为"计算能力"的学生

#### Scenario: 空班级
- **WHEN** 班级无学生
- **THEN** 返回 `{"message": "该班级暂无学生", "_component": null}`

### Requirement: Frontend renders student list panel
系统 SHALL 在 `agent.js` 中处理 `component: "student-list"` 事件，渲染内联学生列表面板。

#### Scenario: 面板渲染学生卡片
- **WHEN** 前端收到 `{type: "component", component: "student-list", params: {students: [...], class_name: "高三1班"}}`
- **THEN** 在 Agent 消息气泡内渲染学生列表面板
- **AND** 面板标题为"高三1班 · N名学生"
- **AND** 每张卡片显示：姓名、学号、障碍标签（带颜色编码）、练习完成数

#### Scenario: 障碍颜色编码
- **WHEN** barrier_score ≥ 0.7 → 红色标签（高障碍）
- **WHEN** 0.3 ≤ barrier_score < 0.7 → 黄色标签（中障碍）
- **WHEN** barrier_score < 0.3 → 绿色标签（低障碍）

#### Scenario: 点击学生卡片触发诊断
- **WHEN** 用户点击某学生卡片
- **THEN** 卡片高亮选中态
- **AND** 自动发送消息"诊断 [学生姓名]"到 Agent

#### Scenario: 超过20名学生显示截断
- **WHEN** students 数组长度 > 20
- **THEN** 仅展示前 20 张卡片
- **AND** 底部显示"查看全部 (N名学生)"按钮，点击跳转到 /pages/students.html

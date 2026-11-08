## ADDED Requirements

### Requirement: show_diagnosis tool triggers diagnosis panel
系统 SHALL 提供 `show_diagnosis` 工具，接收诊断结果数据并触发内联诊断面板渲染。

#### Scenario: Tool returns component with diagnosis data
- **WHEN** Agent 调用 `show_diagnosis` 传入 `diagnose_barrier` 的输出
- **THEN** 返回 `_component.component = "diagnosis"`
- **AND** `_component.params` 包含障碍分布、关键指标等数据

### Requirement: Diagnosis panel renders ECharts chart
系统 SHALL 在诊断面板中使用 ECharts 渲染障碍分布图。

#### Scenario: Bar chart shows barrier distribution
- **WHEN** 诊断数据包含 `{"concept": 0.7, "reading": 0.4, "expression": 0.2}`
- **THEN** 面板渲染 ECharts 柱状图
- **AND** 图表显示三个障碍维度的分布值

#### Scenario: Fallback when ECharts unavailable
- **WHEN** ECharts CDN 加载失败
- **THEN** 面板降级为纯文本指标卡片
- **AND** 不抛出异常

### Requirement: Quick action button links to exam panel
系统 SHALL 在诊断面板中提供"针对障碍出题"按钮，点击后发送消息给 Agent 请求出题。

#### Scenario: Quick exam button sends message
- **WHEN** 用户点击"针对概念障碍出题练习"
- **THEN** 系统发送消息 `sendMessage("针对概念理解障碍出题练习")`
- **AND** Agent 处理后调 `show_exam_workbench` 预填对应知识点

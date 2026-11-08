## Spec: Agent Error Display

### 需求
- 工具调用失败时，AI 气泡内展示具体错误信息
- 错误文案以红色显示

### 验收
- 模拟 tool_error 事件：气泡中出现 "工具调用失败: <error>" 文字
- 错误消息可见且可读

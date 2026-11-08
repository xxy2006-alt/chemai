## Why

Agent 聊天存在并发发送漏洞（可触发多条 SSE 连接）、工具调用失败时气泡为空不展示错误、学生管理页 barrier_type 类型判断缺防护导致排序崩溃、SVG 折线图 Y 轴标签硬编码与实际数据范围不匹配。这些问题直接影响核心使用体验，必须先修再进入设计重构。

## What Changes

- `agent.js`: 新增发送锁（isSending 标志 + 按钮/输入框禁用），防止并发 SSE 连接；tool_error 事件在气泡中展示红色错误信息，不再留空气泡
- `students.js`: barrier_type 增加 typeof 类型防护，防止后端返回字符串时 Object.keys() 排序崩溃；SVG 趋势图 Y 轴标签从 minVal/maxVal 动态计算，不再硬编码 0-100
- `app.js`: 删除 questions/report/panel 三个已删除页面的路由引用

## Capabilities

### New Capabilities
- `agent-send-guard`: Agent 消息发送互斥锁 + visual feedback
- `agent-error-display`: 工具调用失败时气泡内展示错误信息
- `student-barrier-guard`: barrier_type 类型安全防护
- `student-chart-fix`: SVG 趋势图 Y 轴动态标签

### Modified Capabilities
- (none — 纯 bug 修复，不改变 spec 级行为)

## Impact

- `frontend/js/agent.js` — 新增 isSending flag + tool_error 展示逻辑
- `frontend/js/students.js` — barrier_type 类型防护 + SVG Y 轴计算修正
- `frontend/app.js` — 删除 3 行过期路由引用

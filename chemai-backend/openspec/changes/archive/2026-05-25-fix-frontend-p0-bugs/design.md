## Design: 前端 P0 Bug 修复

### 1. agent.js Send Guard

**方案**: 发送期间禁用按钮 + 输入框 + 视觉反馈（opacity .5），流式完成后恢复。

**实现**:
- 新增全局变量 `isSending`
- `sendMessage()` 开头检查 `isSending`，为 true 则直接 return
- 发送前：`isSending = true`，按钮 disabled + opacity .5，输入框 disabled
- `streamResponse()` 末尾（无论成功/失败）：恢复按钮和输入框，`isSending = false`

### 2. agent.js Tool Error Display

**方案**: `tool_error` 事件触发时，在气泡中追加红色错误文字。

**实现**:
- 在 `switch(evt.type)` 的 `case 'tool_error':` 分支中
- 将 `bubble.innerHTML` 设为包含错误信息的 HTML：`'<span style="color:#C53030">工具调用失败: ' + evt.error + '</span>'`

### 3. students.js Barrier Type Guard

**方案**: 加 `typeof b === 'object' && b !== null` 检查，非对象时降级为默认值。

**实现**:
- `studentCard()` 第 65 行：`var b = s.barrier_type || {}` 改为先检查类型
- 不是 object 时：`b = {}`
- `openDetail()` 第 89 行同样加防护

### 4. students.js SVG Y-Axis Fix

**方案**: Y 轴步长从 `(maxVal - minVal) / 4` 动态计算，标签值从 `minVal` 到 `maxVal` 均匀取 5 个。

**实现**:
- 第 140 行 `for (var y = 0; y <= 100; y += 25)` 改为基于 range 的步长
- `var step = Math.ceil(range / 4)` 或类似，确保步长合理

### 5. app.js Stale Route Cleanup

**方案**: 删除 3 行 `else if` 分支。

**实现**:
- 删除第 115-117 行：`questions`、`report`、`panel` 的路径匹配分支

## Why

Agent 的 tool calling 已经能跑通（90% 准确率），但用户说"打开考试工作台"或"看看张三的诊断"时，Agent 只是用文字回复——它不会真的导航过去。

前端 `agent.js` 已经实现了一套完整的导航协议（`navigate` / `populate` / `action` SSE 事件 + sessionStorage bridge），四个目标页面也都接了 `__chemai_bridge`。但两端都没真正工作：

- **后端**：gateway `IntentClassifier` 输出了 `intent`/`page`/`params`，但 SSE 流从不发导航事件
- **前端**：四个页面读了 `__chemai_bridge` 但不消费它来驱动界面

补上这两个缺口，Agent 就能真正驱动界面。

## What Changes

### 后端（2 个文件）

| 文件 | 改动 |
|------|------|
| `agent/channel/fastapi_sse.py` | 分类器返回 `page_action`/`hybrid` 时，在 SSE 流中插入 `navigate` + `populate` + `action` 事件 |
| `agent/gateway.py` | 导航事件工厂函数：根据 `page` + `intent` + tool results 生成正确的 action 序列 |

### 前端（exam-v2 优先，其余后续）

| 文件 | 改动 |
|------|------|
| `frontend/pages/exam-v2.html` | `__chemai_bridge` 消费者：驱动 Vue app 切换 tab、预填数据、触发搜索 |
| `frontend/js/diagnosis.js` | `__chemai_bridge` 消费者：驱动诊断页面选中学生/班级、展示结果 |

### 协议设计

```
SSE 事件流（hybrid 场景）:
  thinking → tool_call → tool_result → populate → navigate → action → done

SSE 事件流（page_action 场景，无需 tool）:
  thinking → navigate → action → done

navigate:  {type:"navigate", page:"exam-v2", params:{kp:"盐类水解"}}
populate:  {type:"populate", target:"data", data:{questions:[...]}}
action:    {type:"action", action:"openTab", payload:"generate"}
```

## Capabilities

- `agent-page-navigation`: Agent 根据用户意图自动导航到目标页面
- `agent-data-populate`: Agent 执行 tool 后，结果预填到目标页面的对应组件
- `agent-ui-actions`: Agent 在目标页面上自动执行 UI 操作（切 tab、选中学生等）

## Impact

- **Files changed**: 4 files, ~120 lines
- **API**: SSE 事件流新增 3 个事件类型（`navigate`/`populate`/`action`），前端已兼容
- **Breaking**: 无。不回 `page` 时行为不变
- **Dependencies**: 无新增依赖

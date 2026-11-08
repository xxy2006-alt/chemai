## Context

ChemAI 前端已实现一套"Agent 驱动界面"的协议栈：
- `agent.js` 解析 3 种导航 SSE 事件（navigate/populate/action），写入 sessionStorage
- 四个目标页面读取 `__chemai_bridge`（但未消费）
- SSE 流结束后 500ms 自动跳转

后端 gateway `IntentClassifier` 已输出 `intent`/`page`/`params`，但 SSE 流从不发送导航事件。两端管道已铺好，需要接通。

## Goals / Non-Goals

**Goals:**
- 后端根据分类器输出发送 navigate/populate/action SSE 事件
- exam-v2 和 diagnosis 两个页面消费 `__chemai_bridge` 驱动界面
- 增量优先——先打通最高频的两个页面

**Non-Goals:**
- students 和 teacher 页面不做（后续单独做）
- 不改变现有 SSE 事件格式的兼容性
- 不改变前端路由机制（继续用 `window.location.href` + sessionStorage）

## Architecture

```
用户输入: "给张三出5道盐类水解的题"
          │
          ▼
┌─────────────────────────────────────────────────────┐
│                 fastapi_sse.py                       │
├─────────────────────────────────────────────────────┤
│                                                      │
│  1. IntentClassifier.classify(msg, skills, ctx)     │
│     → intent=hybrid, page=exam-v2                   │
│     → tools=["generate_questions"]                   │
│     → params={student_name:"张三",                   │
│                knowledge_points:"盐类水解"}           │
│                                                      │
│  2. Agent 执行 generate_questions → result           │
│                                                      │
│  3. build_navigate_events(intent, [result])          │
│     → {                                             │
│         navigate: {page:"exam-v2",                   │
│                    params:{kp:"盐类水解"}},          │
│         populate: [{target:"data",                   │
│                     data:{questions:[...]}}],        │
│         actions: [{action:"openTab",                 │
│                     payload:"generate"}]             │
│       }                                             │
│                                                      │
│  4. SSE 事件流                                       │
│     thinking → tool_call → tool_result →             │
│     populate → navigate → action → reply → done       │
│                                                      │
└──────────────────────┬──────────────────────────────┘
                       │
          sessionStorage("chemai_navigate")
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│              exam-v2.html (Vue app)                  │
├─────────────────────────────────────────────────────┤
│                                                      │
│  mounted():                                          │
│    bridge = window.__chemai_bridge                   │
│    bridge.actions.forEach(handleAction)              │
│    bridge.data → populate components                 │
│    bridge.params → pre-fill filters                  │
│    window.__chemai_bridge = null                     │
│                                                      │
└─────────────────────────────────────────────────────┘
```

## Decisions

### D1: 导航事件插入的时序

**选择**: tool_result 之后、reply text 之前发送 populate → navigate → action。

**理由**:
- 前端 `agent.js` 只在收到 `done` 事件后才跳转，提前发送 navigate 不会中断当前 SSE 流
- populate 在 navigate 之前发送确保跳转前数据已就绪
- action 紧跟 navigate 让页面明确知道该做什么

### D2: `page_action` 场景无 tool 执行

**选择**: 直接发送 navigate + action，跳过 tool_call/tool_result。

**理由**: "打开考试工作台"不需要任何 tool 执行。Gateway 分类器输出 `intent=page_action` 时，Agent 的第一段判断已经完成了。节省一次 tool round-trip。

### D3: 前端 bridge 消费模式

**选择**: 每个页面在初始化时检查 `__chemai_bridge`，消费后置 null。

**理由**:
- Bridge 是一次性的——页面跳转后不会再被消费
- 置 null 防止 SPA 内重复触发
- 不依赖 Vue 生命周期的事件顺序（`mounted` 时 sessionStorage 已经写入）

### D4: populate 数据映射

**选择**: tool 的返回 JSON 直接作为 populate data，前端按 target 字段分发。

**理由**: Tool 函数返回的是结构化 JSON。后端不需要重新解析——直接透传。前端页面知道自己需要什么格式。减少耦合。

```python
# populate 事件结构
{"type": "populate", "target": "data", "data": {"questions": [...], "total": 5}}
```

## Risks / Trade-offs

- **sessionStorage 容量**: 单次导航数据 < 100KB（5道题+元数据），sessionStorage 5MB 限制绰绰有余
- **跨域/跨标签**: sessionStorage 同源隔离，不影响其他标签页
- **Vue 应用外部驱动**: exam-v2 是 Vue app，bridge 消费者需要直接操作 Vue 实例的 data。用 `document.querySelector('#app-root').__vue_app__` 访问内部状态，或通过全局事件 bus

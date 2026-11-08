## Context

Phase 1 修好了 agent 的多步执行底盘。Phase 2 在此之上让 agent 成为前端页面的中央协调器。当前前端 5 个页面（chat/ocr/exam/diagnosis/students/teacher）各自独立调用 REST API，agent 只管 chat 页面。需要拆掉这堵墙。

## Goals / Non-Goals

**Goals:**
- LLM 语义意图分类替代 keyword 匹配
- agent 能通过 SSE 指挥前端跳转页面和填充数据
- 跨页面数据传输（sessionStorage bridge）

**Non-Goals:**
- 不改造 OCR 页面（静态功能，不需要 agent 驱动）
- 不改动 skill 实现代码
- 不改动 provider 层

## Decisions

### D1: 分类器架构 — 独立文件还是 inline

**选择**: 新建 `agent/gateway.py` 为独立模块。

**理由**: 意图分类是独立关注点。Phase 3 的 Planner 需要复用 Gateway 的参数提取结果（如用户说的"张三"→ student_id）。抽出来避免 core.py 继续膨胀（已经在 450+ 行）。

### D2: 分类 LLM 调用 — 复用 provider 还是新建

**选择**: 复用 agent 的 `self._provider`，不加新连接。

**理由**: DeepSeek API 每次调用的 token 成本很低（分类 prompt ~200 tokens）。新建 provider 意味着新的 HTTP 连接池和 API key 管理，不划算。

### D3: 跨页面数据传输 — sessionStorage vs URL params vs iframe

**选择**: `sessionStorage.chemai_navigate` JSON 对象。

**理由**:
- URL params 有长度限制（~2000 chars），skill 结果可能很大
- iframe 方案需要改造整个前端架构，工作量太大
- sessionStorage 同一浏览器 session 内跨页面可用，容量 ~5MB

**流程**:
```
agent.js 收到 navigate SSE event
  → sessionStorage.setItem('chemai_navigate', JSON.stringify({page, params, data, actions}))
  → window.location.href = '/pages/' + page + '.html'

Target page loads
  → DOMContentLoaded: var nav = JSON.parse(sessionStorage.getItem('chemai_navigate'))
  → if (nav) { executeActions(nav); sessionStorage.removeItem('chemai_navigate') }
```

### D4: navigate 时机 — 立即跳转还是等 done

**选择**: 等 `done` 事件后再跳转。

**理由**: 流式过程中跳转会中断 SSE 连接。等 `done` 保证所有 skill 执行完毕、数据完整。用户也可能想在 chat 页面先看完 agent 的回复再跳转。

## Risks / Trade-offs

- **分类 LLM 调用增加 ~500ms 延迟**: 在 keyword 匹配时是瞬时的。缓解：分类 prompt 很短（~200 tokens），实际延迟 <1s，用户可接受
- **sessionStorage 大小限制**: 如果 skill 返回大量数据（如 50 道题），可能超 5MB。缓解：只传必要数据（题目 ID 列表），详细数据由目标页面自己的 API 调用获取
- **页面跳转打断用户**: 如果用户正在看聊天记录，突然跳转体验不好。缓解：Phase 2 先做自动跳转，后续加用户确认（"agent 已完成出题，要打开考试工作台吗？"）

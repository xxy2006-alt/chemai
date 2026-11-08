# Chat Pipeline — Evals

> 多轮对话持久化、历史加载、SSE 流、dedup

## 基线

| 编号 | 测试 | 位置 | 断言 |
|------|------|------|------|
| CP-B01 | AsyncSqliteSaver 共享 checkpointer | `test_langgraph_agent.py` | 多轮状态持久化 |
| CP-B02 | SSE text/tool_call/tool_result/done 事件 | `test_sse_streaming.py` | 事件类型正确 |
| CP-B03 | version:v2 单 Agent | `test_langgraph_agent.py` | ReAct agent + persona filter |
| CP-B04 | 对话历史 API | `test_langgraph_agent.py` | GET /chat/history/{tid} 返回消息 |
| CP-B05 | 对话列表 API | `test_langgraph_agent.py` | GET /chat/conversations 返回列表 |

## 边界

| 编号 | 场景 | 预期 |
|------|------|------|
| CP-E01 | 空 thread_id 查询历史 | 返回空列表 |
| CP-E02 | 并发两个请求同 thread_id | 各自独立，不丢消息 |
| CP-E03 | SSE 流中断 | 前端显示错误，不崩溃 |
| CP-E04 | trim_context 超 30 条消息 | 触发 LLM 摘要 |

## 回归

| 编号 | 历史 Bug | 防止措施 |
|------|---------|---------|
| CP-R01 | ReAct 循环重复回复 | SSE dedup: tool 返回 guidance 后 LLM 文本跳过 |
| CP-R02 | "你是学生还是老师" | Persona prompt + output rules 禁止 |
| CP-R03 | No checkpointer set | InMemorySaver 改为 AsyncSqliteSaver |
| CP-R04 | 多进程抢 8000 端口 | Docker 单进程 + 端口切换 8001 |

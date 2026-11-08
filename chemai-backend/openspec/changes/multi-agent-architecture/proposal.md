## Why

ChemAI 当前是单体 ReAct agent 绑了 14 个工具。LangGraph 的 router / check / pre-flight 节点是补丁不是解法——根因是 LLM 在 14 个工具定义里找不到正确的。需要拆成多 agent 架构，每个 sub-agent 只绑 2-4 个工具。

## What Changes

- **Multi-agent StateGraph**: Coordinator + Router + 5 个 sub-agent node，替代当前单体 ReAct
- **GuardState 下沉**: 去重/限流/审批从 coordinator 层移到 sub-agent 层
- **Shared context**: 学生/班级信息通过 `MultiAgentState.shared_context` 跨 agent 共享
- **SSE adapter 更新**: 抑制 sub-agent 内部 tool_call 事件，component/route 通过 state 传递
- 不改 `tools.py` 中的工具函数签名
- 不改前端 `agent.js` / `index.html`
- 现有 4 个 API 端点保持兼容

## Capabilities

### New Capabilities
- `multi-agent-coordinator`: Coordinator + Router 节点，用 structured_output 做意图路由到 5 个 sub-agent
- `sub-agent-search`: 搜索专家 sub-agent（search_exam_bank, web_search, list_knowledge）
- `sub-agent-exam`: 出题专家 sub-agent（show_exam_workbench, save_to_bank）
- `sub-agent-diagnosis`: 诊断专家 sub-agent（diagnose_barrier, show_diagnosis, assign_adaptive_practice）
- `sub-agent-tutor`: 辅导专家 sub-agent（chemistry_tutor, simulate_experiment, balance_equation, weekly_report）
- `sub-agent-bank`: 题库管理 sub-agent（list_banks, delete_bank）
- `shared-context`: 跨 agent 状态共享（MultiAgentState.shared_context）
- `sse-adapter`: LangGraphSSEAdapter 更新（sub-agent 事件抑制 + state 传递 component/route）

### Modified Capabilities
<!-- No existing specs to modify -->


## Impact

- `agent/langgraph_agent.py` — 重写（~350 行）
- `agent/tools.py` — 不改
- `agent/langgraph_sse.py` — 修改 feed() + finalize()（~40 行）
- `agent/channel/langgraph_channel.py` — 修改 agent 工厂 + finalize 调用（~50 行）
- `agent/memory.py` — 不改
- `frontend/js/agent.js` — 不改
- `frontend/index.html` — 不改

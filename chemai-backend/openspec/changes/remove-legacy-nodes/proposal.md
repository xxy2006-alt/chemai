## Why

新的 multi-agent 架构中 router/check/pre-flight 节点已被 Coordinator + Router 替代。旧代码应该删除——死代码增加维护负担，router 和 check 的拦截逻辑已经内化到 sub-agent 的 GuardState 中。

**依赖**: `multi-agent-architecture` change 必须先完成。

## What Changes

- 删除 `_router_node` 和 `_route_after_router`
- 删除 `_check_node` 和 `_route_after_check`
- 删除 `TOOL_PREREQUISITES` dict
- 删除 `VAGUE_KEYWORDS` list 和 `_is_keyword_too_vague`
- 删除 `_has_exam_params`
- 删除 `_preflight_check`（langgraph_channel.py）
- 清理 `langgraph_agent.py` 中不再使用的 import（如 graph 旧节点相关）

## Capabilities

### Modified Capabilities
<!-- No specs to modify — this is pure deletion -->


## Impact

- `agent/langgraph_agent.py` — 删除 ~120 行
- `agent/channel/langgraph_channel.py` — 删除 `_preflight_check` ~40 行

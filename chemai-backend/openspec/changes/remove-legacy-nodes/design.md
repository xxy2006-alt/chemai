## Context

`multi-agent-architecture` change 引入新的 Coordinator + Router 后，以下旧代码变为 dead code：

1. `_router_node` — 拦截 search_exam_bank 调用，改为 redirect 到 show_exam_workbench。新架构中 coordinator 直接路由到 exam_expert。
2. `_check_node` — 检查 TOOL_PREREQUISITES。新架构中 sub-agent 的 GuardState 做前置检查。
3. `_preflight_check` — 检查用户消息是否有足够参数。新架构中 coordinator 做意图判断。

## Goals / Non-Goals

**Goals:**
- 删除所有被 multi-agent 架构替代的旧节点代码
- 清理不再使用的 import 和常量

**Non-Goals:**
- 不改 `tools.py` 中的业务逻辑
- 不改前端或 API 端点

## Decisions

### D1: 只删不改

只做删除操作，不做任何"改进"。被删除的代码已经被新架构替代，不需要胶水代码。

**Why:** 降低风险。删除比修改安全——如果新架构有问题，git revert 一步到位。

### D2: 在 regression test 通过后执行

这个 change 在 `multi-agent-architecture` 的全量测试通过之后才能执行。

**Why:** 旧节点最后一次活着的证据是测试通过。先验证新架构能跑所有场景，再删旧代码。

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| 删除了仍在引用的代码 | 先跑全量测试，确认旧节点不再被调用 |
| 后续发现需要旧节点的某个逻辑 | 从 git history 恢复，但更可能应该在新架构中实现等价逻辑 |

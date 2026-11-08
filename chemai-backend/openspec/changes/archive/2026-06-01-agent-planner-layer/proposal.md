## Why

Phase 1 让 agent 能多步执行 skills，Phase 2 让 agent 能驱动前端页面。但 agent 仍然不知道如何把复杂目标拆成步骤——"准备期中考试，范围前三章"这类需要跨多个知识点的组合操作，LLM 每次只能猜下一步，没有全局视角。需要加一个 Planner 层：LLM 先规划全部步骤，再逐步执行，过程中观察结果必要时重新规划。

## What Changes

### New: `agent/planner.py` (~120 lines)
- `PlanStep` 和 `Plan` dataclass 定义计划结构
- `PlanGenerator` 类：LLM 驱动的目标拆解 → 结构化步骤 DAG
- 依赖注入：`${step_N.field}` 模板解析，让后续步骤引用前序结果
- 安全校验：检测循环依赖、步骤数上限(6)、多余依赖

### Changed: `agent/core.py` (~70 lines)
- `_needs_planning()`: keyword 启发式检测（命中 2+ 规划关键词才激活）
- `run_with_plan_stream()`: 新方法，generate plan → emit plan_summary → 逐步执行 → emit plan_progress → replan（最多 2 次）
- `run_stream()`: 增加早期分支，检测到规划需求时走 plan 路径
- SSE: 新增 `plan_summary`、`plan_progress` 事件，`phase` 新增 `planning` 值

### Changed: `frontend/js/agent.js` (~65 lines)
- `case 'plan_summary'`: 渲染计划卡片（步骤列表 + 当前高亮）
- `case 'plan_progress'`: 更新步骤状态 + 动画
- `case 'phase': 'planning'`: 展示"生成计划中..."
- 计划卡片完成 2 秒后自动折叠为 "3/3 步骤已完成"
- 点击可重新展开

## Capabilities

### New Capabilities
- `goal-decomposition`: LLM 将复杂教学目标拆解为结构化步骤 DAG
- `plan-execution`: 按计划逐步执行 skills，依赖步骤自动注入前序结果
- `plan-visualization`: 前端实时展示计划执行进度（步骤卡片 + 状态动画）

## Impact

- **Files changed**: `agent/planner.py` (new), `agent/core.py` (~70 lines), `frontend/js/agent.js` (~65 lines)
- **API**: `/api/agent/chat/stream` 新增 `plan_summary`、`plan_progress` 事件类型。**向后兼容**
- **Breaking**: 无。无计划时走原路径
- **Dependencies**: 依赖 Phase 1（多步执行循环）+ Phase 2（SSE 事件扩展模式）

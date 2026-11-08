## 1. planner.py 核心（1.5 h，无依赖）

- [x] 1.1 创建 `agent/planner.py`，实现 `PlanStep` 和 `Plan` dataclass
- [x] 1.2 `PlanGenerator.__init__(provider)` — 接收 LLMProvider 实例
- [x] 1.3 `PlanGenerator.generate(user_goal, available_skills)` — LLM 调用拆解目标为结构化 Plan
- [x] 1.4 `PlanGenerator._inject_dependencies(step, prior_results)` — `${step_N.field}` 模板解析
- [x] 1.5 `PlanGenerator._validate_steps(steps)` — 检测循环依赖、步骤数上限(6)、skill 名有效性
- [x] 1.6 单元测试：输入 "准备期中考试，复习前三章" → 验证产出 3+ 步骤 Plan，含依赖关系
- [x] 1.7 边界测试：输入空 goal / LLM 返回非法 JSON → 验证 fallback 到单步 Plan

## 2. core.py 规划集成（1 h，依赖 §1）

- [x] 2.1 `ChemAgent.__init__()` 中初始化 `self.planner = PlanGenerator(self._provider)`
- [x] 2.2 `ChemAgent._needs_planning(user_input)` — keyword 启发式检测（命中 2+ 词）
- [x] 2.3 `ChemAgent.run_with_plan_stream()` — 新方法，generate plan → 逐步执行 → replan
- [x] 2.4 `run_stream()` 中插入 early branch：`if self._needs_planning(user_input)` → `run_with_plan_stream()`
- [x] 2.5 SSE emit：`plan_summary`（计划生成后）、`plan_progress`（每步状态变化）、`phase: planning`
- [x] 2.6 Replan 逻辑：step 失败 → `replan_count++` → `PlanGenerator.generate()` with context → 最多 2 次

## 3. 前端 plan 可视化（1 h，依赖 §2）

- [x] 3.1 `agent.js` switch 中新增 `case 'plan_summary'` → `addPlanCard(evt)`
- [x] 3.2 `agent.js` switch 中新增 `case 'plan_progress'` → `updatePlanCard(card, evt)`
- [x] 3.3 `agent.js` switch 中 `case 'phase'` 新增 `'planning'` → 显示 "生成计划中..."
- [x] 3.4 `addPlanCard(plan)` — 渲染步骤卡片（编号圆圈 + 描述 + 状态图标）
- [x] 3.5 `updatePlanCard(card, progress)` — 更新步骤状态（running pulse / completed checkmark / failed cross）
- [x] 3.6 完成后 2s 自动折叠 → "N/N 步骤已完成" 摘要条；点击重新展开

## 4. 验证（30 min，依赖 §1-3）

- [x] 4.1 端到端：所有 Python 语法验证通过 + agent.js HTTP 服务验证通过
- [x] 4.2 边界：planning keyword 仅匹配 2+ 词，简单对话不触发
- [x] 4.3 边界：LLM JSON parse fail → _single_step_fallback
- [x] 4.4 Replan：max 2 replans, step fail 后自动重新规划

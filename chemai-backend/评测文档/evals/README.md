# ChemAI Agent v2.0 评测体系

## 概述

本目录为 ChemAI 化学教学 Agent 的形式化评测套件。评测体系采用三层架构：**基线层 (Baseline)** 验证核心功能正确性，**边界层 (Boundary)** 探测系统的鲁棒性极限，**回归层 (Regression)** 防止已判定正确的行为退化。

## 三层架构

| 层级 | 目标 | 通过标准 | 场景数 |
|------|------|----------|--------|
| **Baseline 基线层** | 验证核心功能的正确性 — 路由、工具调用、工作流、行为约束 | 100% | 35 |
| **Boundary 边界层** | 探测系统在异常输入、错误条件、资源缺失下的鲁棒性极限 | >=75-85% | 29 |
| **Regression 回归层** | 防止已知缺陷复现、跨角色越权、SSE 异常、一致性退化 | >=80-100% | 47 |
| **合计** | | | **~111** |

## 14 维度 -> 三层映射

| # | 维度 | 层级 | 目录 | 场景文件 | 场景数 | CI warning | CI critical |
|---|------|------|------|----------|--------|------------|-------------|
| 1 | 路由准确性 | Baseline | `baseline/routing/` | `golden_routing.yaml` + `gateway_routing.yaml` | 32 | 0.90 | 0.80 |
| 2 | 工具调用准确性 | Baseline | `baseline/tool_call/` | `golden_tool_call.yaml` | 8 | 0.85 | 0.75 |
| 3 | 工作流完整性 | Baseline | `baseline/workflow/` | `golden_workflow.yaml` | 12 | 0.80 | 0.70 |
| 4 | 行为约束 | Baseline | `baseline/constraint/` | `golden_constraint.yaml` | 7 | 0.85 | 0.75 |
| 5 | 边界情况 | Boundary | `boundary/edge_case/` | `edge_scenarios.yaml` | 12 | 0.80 | 0.65 |
| 6 | 错误恢复 | Boundary | `boundary/error_recovery/` | `error_scenarios.yaml` | 8 | 0.75 | 0.60 |
| 7 | 工具结果利用 | Boundary | `boundary/result_utilization/` | `result_scenarios.yaml` | 2 | 0.80 | 0.65 |
| 8 | 计划连贯性 | Boundary | `boundary/plan_coherence/` | `plan_scenarios.yaml` | 4 | 0.80 | 0.65 |
| 9 | 状态转换 | Boundary | `boundary/state_transition/` | `checkpoint_replay.yaml` | 3 | 0.85 | 0.70 |
| 10 | 跨角色权限 | Regression | `regression/cross_role/` | `role_scenarios.yaml` | 6 | 0.85 | 0.70 |
| 11 | SSE流式传输 | Regression | `regression/sse/` | `sse_scenarios.yaml` | 5 | 1.00 | 0.90 |
| 12 | 一致性 (Pass@k) | Regression | `regression/consistency/` | `passk_scenarios.yaml` | 7 | 0.80 | 0.65 |
| 13 | 性能基线 | Regression | `regression/performance/` | `performance_baseline.yaml` | 9 metrics | 0.85 | 0.70 |
| 14 | 已知缺陷回归 | Regression | `regression/monitoring/` | `known_defects.yaml` + `ci_gates.yaml` | 5 | 1.00 | 0.95 |

## 场景总数统计

| 层级 | 维度数 | YAML 场景数 | CI 门禁数 |
|------|--------|------------|----------|
| Baseline | 4 | 35 + 24(gateway) = 59 | 4 |
| Boundary | 5 | 29 | 5 |
| Regression | 5 | 23 + 9(metrics) + 14(gates) | 5 |
| **总计** | **14** | **~111** | **14** |

## CI 门禁说明

CI 门禁定义在 `regression/monitoring/ci_gates.yaml`，为每个维度设定了 **warning** 和 **critical** 两道阈值：

- **warning**: 通过但发出告警，允许合入代码
- **critical**: 阻断合入，必须修复后方可继续
- **测量方式**: 每维度通过率 = 通过场景数 / 总场景数
- **聚合方式**: 所有场景等权，无加权平均

性能基线定义在 `regression/performance/performance_baseline.yaml`，包含 9 项指标（任务成功率、P95延迟、错误率、升级率、虚假信心率、路由漂移、一致性下降、延迟退化、工具幻觉率），每项均设有 warning 和 critical 阈值。

## 断言类型参考

| 断言类型 | 用途 | 示例 |
|----------|------|------|
| `tool_called` | 验证特定工具被调用 | `{type: tool_called, tool: chemistry_tutor}` |
| `not_tool_called` | 验证特定工具未被调用 | `{type: not_tool_called, tool: save_question}` |
| `tool_arg_contains` | 验证工具参数包含预期值 | `{type: tool_arg_contains, param: student_id, value: "202610101"}` |
| `tool_count` | 限制工具调用次数上限 | `{type: tool_count, lte: 5}` |
| `max_tool_calls` | 全局工具调用上限 | `{type: max_tool_calls, value: 8}` |
| `tool_trajectory_order` | 验证工具调用顺序 | `{type: tool_trajectory_order, tools: [search, generate]}` |
| `no_error` | 执行过程无错误 | `{type: no_error}` |
| `has_text_response` | 必须有文本回复 | `{type: has_text_response}` |
| `text_contains_one_of` | 回复包含指定关键词之一 | `{type: text_contains_one_of, values: [...]}` |
| `result_referenced` | 验证工具结果被实际引用 | `{type: result_referenced, tool: search_exam_bank}` |
| `interrupt_triggered` | 验证审批中断被触发 | `{type: interrupt_triggered}` |
| `route_assertion` | 验证路由目标 | `{type: route_assertion, route: exam_workbench}` |
| `trajectory_hash_stable` | 验证轨迹哈希稳定 | `{type: trajectory_hash_stable}` |
| `node_sequence_stable` | 验证节点序列稳定 | `{type: node_sequence_stable}` |
| `edge_routing_stable` | 验证边路由稳定 | `{type: edge_routing_stable}` |
| `tool_set_stable` | Pass@k 工具集稳定 | `{type: tool_set_stable, threshold: 0.8}` |
| `tool_order_stable` | Pass@k 工具顺序稳定 | `{type: tool_order_stable, threshold: 1.0}` |
| `paraphrase_consistency` | 改述一致性 | `{type: paraphrase_consistency, threshold: 0.8}` |
| `event_present` / `event_not_present` | SSE 事件存在性 | `{type: event_present, event: heartbeat}` |
| `event_order` | SSE 事件顺序 | `{type: event_order, expected: [...]}` |
| `event_fields` | SSE 事件字段完整性 | `{type: event_fields, event: done, fields: [event, data]}` |
| `no_repeated_identical_call` | 无重复相同调用 | `{type: no_repeated_identical_call}` |

## 旧评测文档引用

本评测体系继承并形式化了以下历史评测文档中的场景：

- `评测文档/ChemAI_Agent_v2.0_测评体系.md` — 14 维度框架定义
- `评测文档/01_ChemAI_Agent_v2.0_测评体系设计.md` — 设计思路
- `评测文档/02_化学方程式审核专项/` — 方程式配平专项测试
- `评测文档/03_LLM专项评测/` — LLM 质量专项测试

历史文档保留在父目录中作为设计参考，本 evals 目录为运行时评测的唯一入口。

## 业界对标

| 本体系维度 | 对标框架 | 对标指标 |
|-----------|---------|---------|
| 路由准确性 | 六维轨迹框架 (6D Trajectory) | Tool Selection Accuracy |
| 工具调用准确性 | BFI v3 (Berkeley Function Calling) | AST 参数匹配 |
| 工作流完整性 | Tau-Bench / SWE-Bench | Multi-turn Task Completion |
| 行为约束 | Guardrails (NVIDIA NeMo / Llama Guard) | Safety / Policy Adherence |
| 边界情况 | 红队测试 (Red Teaming) | Adversarial Robustness |
| 错误恢复 | 混沌工程 (Chaos Engineering) | Graceful Degradation |
| 一致性 (Pass@k) | HumanEval / APPS | Pass@k 方法论 |
| 跨角色权限 | OWASP LLM Top 10 | Authorization / Access Control |
| SSE流式传输 | Web Standards (WHATWG) | SSE Protocol Compliance |

---

## 运行方式

```bash
# 运行全部评测
chemai-eval run --all

# 按层级运行
chemai-eval run --layer baseline
chemai-eval run --layer boundary
chemai-eval run --layer regression

# 按维度运行
chemai-eval run --dim routing
chemai-eval run --dim tool_call

# CI 门禁模式
chemai-eval ci --fail-on critical
```

## 目录结构

```
evals/
├── README.md                           # 本文件
├── baseline/
│   ├── routing/                        # 维度 1: 路由准确性
│   │   ├── golden_routing.yaml
│   │   └── gateway_routing.yaml
│   ├── tool_call/                      # 维度 2: 工具调用准确性
│   │   └── golden_tool_call.yaml
│   ├── workflow/                       # 维度 3: 工作流完整性
│   │   └── golden_workflow.yaml
│   └── constraint/                     # 维度 4: 行为约束
│       └── golden_constraint.yaml
├── boundary/
│   ├── edge_case/                      # 维度 5: 边界情况
│   │   └── edge_scenarios.yaml
│   ├── error_recovery/                 # 维度 6: 错误恢复
│   │   └── error_scenarios.yaml
│   ├── result_utilization/             # 维度 7: 工具结果利用
│   │   └── result_scenarios.yaml
│   ├── plan_coherence/                 # 维度 8: 计划连贯性
│   │   └── plan_scenarios.yaml
│   └── state_transition/               # 维度 9: 状态转换
│       └── checkpoint_replay.yaml
└── regression/
    ├── cross_role/                     # 维度 10: 跨角色权限
    │   └── role_scenarios.yaml
    ├── sse/                            # 维度 11: SSE流式传输
    │   └── sse_scenarios.yaml
    ├── consistency/                    # 维度 12: 一致性
    │   └── passk_scenarios.yaml
    ├── performance/                    # 维度 13: 性能基线
    │   └── performance_baseline.yaml
    └── monitoring/                     # 维度 14: 已知缺陷 + CI门禁
        ├── known_defects.yaml
        └── ci_gates.yaml
```

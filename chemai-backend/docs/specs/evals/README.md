# ChemAI Agent 评估体系升级 — Spec 跟踪

> 源文档：`docs/evals/eval-system-design.md`（七层模型设计）与 `docs/adr/0007-agent-eval-system.md`（决策记录）。
> 仓库无远端 issue tracker，本目录即 tracker：每份 spec 一个文件，状态在此索引维护。

## 状态词汇

- `draft` — 已拆解，待评审
- `ready-for-agent` — 评审通过，可进入实现
- `done` — 已实现且验收通过

## Spec 列表（按执行顺序）

| # | Spec | Phase | 状态 | 依赖 | 接缝 |
|---|---|---|---|---|---|
| 01 | [评估基建：快/慢双层运行器 + 门禁 + 趋势](spec-01-eval-infra.md) | P0 | done | 无 | 接缝 1（runner CLI） |
| 02 | [快跑层加固：L0 摸底 + L4 埋点 + L1 扩充](spec-02-fast-layer.md) | P1 | done | Spec 01 | 接缝 1/2/4 |
| 03 | [基础工具四件套：read/write/edit/bash（沙箱）+ find/grep](spec-03-tool-quartet.md) | P2 (开发A) | done | Spec 01, 02 | 被测对象（L0/L3 场景） |
| 04 | [L2 判官：五族 rubric + 校准 + 人机兜底](spec-04-judge-harness.md) | P3 | done | Spec 01 | 接缝 3（judge 入口） |
| 05 | [出题智能化：交互智能场景 + persona 增强](spec-05-question-gen.md) | P4 (开发B) | done | Spec 04 | 被测对象（L2 交互智能族） |
| 06 | [planner 接线 + L6 端到端场景](spec-06-planner-e2e.md) | P5 (开发C) | done | Spec 05 | 被测对象（L2/L6 场景） |
| 07 | [全工具链路验收矩阵](tool-chain-matrix.md) | P6 (2026-08) | done | Spec 01–06 | 48 工具 UI 链路 + 前端标准 S1–S4 + read 卡死修复 |

> 六份 spec 已全部拆解并实现完成。评估体系升级收官：快/慢双层运行器 + 七层模型 + 判官 + eval-first 全链路落地。

> 2026-08 新增：全工具链路验收（tool-chain-matrix.md）——48 工具全部验证，
> read 卡死根除（langgraph 1.x astream_events 吞 interrupt）、S3 文本零复述
> （适配器压制 + 标准过渡）、面板去重、教师身份注入、16+5 渲染器补齐，
> 全部 eval-first 收敛为 pytest 313 / evals 93 / vitest 263 常驻。

> 六份 spec 已于 2026-08 全部拆解完成，均为 ready-for-agent 状态，按编号顺序执行（02 与 04 可并行）。

## 执行约定

- **评估先行（eval-first）**：每个开发项先写红评估（`expected_fail` 标记，不挡门禁）→ 开发到绿 → 去掉标记转常驻。
- 每份 spec 评审通过后打 `ready-for-agent`，实现完成且验收通过后打 `done`。
- Spec 02 与 Spec 04 无相互依赖，可并行。

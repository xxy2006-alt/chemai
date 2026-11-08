# 基线层 EVALS (Baseline)
# 验证：正常条件下核心功能是否工作
# 场景总数：35，通过标准：≥88.6%
# 对标：六维轨迹框架 (Tool Selection / Argument Extraction / Task Completion)

## 子目录

| 目录 | 维度 | 场景数 | 通过标准 |
|------|------|--------|---------|
| [routing/](routing/) | 路由准确性 | 8 baseline + 24 gateway | 路由100%, Gateway≥91.7% |
| [tool_call/](tool_call/) | 工具调用 | 8 | ≥87.5% |
| [workflow/](workflow/) | 工作流链路 | 12 | ≥83% |
| [constraint/](constraint/) | 行为约束 | 7 | ≥86% |

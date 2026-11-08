## Why

diagnosis 页面的 bridge 消费者缺少 `showPlan` action——Agent 执行 `diagnose_barrier` 后生成了学习计划，但无法触发页面展开计划面板。

## What Changes

| 文件 | 改动 |
|------|------|
| `agent/gateway.py` | PAGE_ACTIONS 中 diagnosis 加 `showPlan` action 映射 |
| `frontend/js/diagnosis.js` | bridge 消费 `action: showPlan` → 调用 `togglePlanPanel()` |

## Tasks

- [x] 1. gateway.py: diagnosis page actions 加 `"showPlan"` 映射
- [x] 2. diagnosis.js: bridge consumer 处理 `action: showPlan` → `togglePlanPanel()`
- [x] 3. E2E: "诊断张三并生成学习计划" → agent-page-driver 分流到 diagnosis + 展示结果 + 展开计划

## Impact

- **Files changed**: 2 files, ~5 lines
- **Breaking**: 无

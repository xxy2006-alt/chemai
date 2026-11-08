# ChemAI 回归集管理策略

## 回归集来源

```
生产 trace 中任何 score 低于阈值
         ↓
   自动聚类 (HDBSCAN over span embeddings)
         ↓
   每类取 1 个代表性 checkpoint
         ↓
   人工标注预期轨迹 (expected tool calls + output)
         ↓
   提升到 CI 回归集 (golden_regression.yaml)
```

## 回归集格式

```yaml
# evals/golden_regression.yaml
regressions:
  - id: "rg-001"
    description: "ReAct loop 重复回复"
    checkpoint_id: "ckpt_abc123"
    thread_id: "m-1751539200000"
    expected_tools: ["chemistry_tutor"]
    forbidden_tools: []
    expected_behavior: "tool 输出 text 后不应再生成重复文本"
    fixed_in: "2026-07-04-sse-dedup"
    layer: "state"
    severity: "high"

  - id: "rg-002"
    description: "student persona 能调 balance_equation"
    checkpoint_id: "ckpt_def456"
    thread_id: "m-1751539300000"
    expected_tools: ["ionic_equation_tutor"]
    forbidden_tools: ["balance_equation"]
    expected_behavior: "student 不应该有 balance_equation 工具"
    fixed_in: "2026-07-03-persona-v2"
    layer: "safety"
    severity: "critical"
```

## 当前回归用例 (已 build)

| 编号 | Bug | 层 | 严重度 | 修复版本 |
|------|-----|-----|:---:|------|
| RG-01 | `import_exam_paper` 幽灵引用 | Capability | high | tools_core 重构 |
| RG-02 | submit 返回 mock 假数据 | State | **critical** | 错误处理升级 |
| RG-03 | EXAM 学生端不可见 | Capability | high | practice API 修复 |
| RG-04 | ReAct 循环重复回复 | State | high | SSE dedup |
| RG-05 | Agent 问"你是学生还是老师" | Quality | medium | persona prompt |
| RG-06 | No checkpointer set | State | **critical** | AsyncSqliteSaver |
| RG-07 | 多进程抢 8000 端口 | State | high | Docker 化 |

## 回归集大小限制

- 上限：50 条
- 超限策略：移除最旧的低严重度用例 (severity=low) 并归档到 `evals/archive/`
- 归档文件保留 expected behavior 和 original checkpoint_id 以便后续复验

## 待建设

- [ ] HDBSCAN 自动聚类流水线
- [ ] production trace → regression 自动提升
- [ ] Golden 数据集覆盖度报告 (哪些 tool 没被 golden 数据覆盖)
- [ ] Checkpoint replay 自动化 (A/B prompt testing)

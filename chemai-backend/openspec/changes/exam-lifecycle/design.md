# 考试生命周期 — 设计决策

> 来源：grilling（2026-09-12）。本 change 两项核心决策为代定（用户未逐项作答，按「全量实现」指令采用），显著标注，可推翻。

## 决策 4.1（代定，可推翻）：做实六态状态机

选项：做实六态 / 写 ADR 收缩 CONTEXT.md 承诺到两态 / 只加两端态。

采用**做实**：与全量实现目标一致；grading 态为判卷中心提供明确入口握手；学生在线考试是闭环的正式性一环。收缩方案被否决的原因：考试与练习在学生端将永远不可区分。

若推翻：退回「ADR 收缩」，成本仅为本 change 的迁移与转移规则不做，CONTEXT.md 改写。

## 决策 4.2（代定，可推翻）：学生作答 seam = 练习学生面扩展

选项：扩展现有练习学生面（allow_self 路由族）/ 新开独立考试作答路由族。

采用**扩展练习学生面**：该面已把已发布考试汇入学生任务列表（按 published 过滤），且 allow_self + ScopeGuard 的鉴权装置现成；新开路由族意味着两套学生作答入口、两套幂等与提交语义。考试专属语义（开考置 in_progress、提交后锁定、混合题型）作为该面上的规则承载。

约束：exam 路由维持 teacher-only（ADR-0009 默认拒绝不放松）；学生路径全部走 allow_self + ScopeGuard 收窄到本人。

## 状态机

```
draft → published → in_progress → grading → completed → archived
                └────────── cancelled（任何非终态）
```

| 迁移 | 触发 | 留痕 |
|------|------|------|
| draft → published | 教师/Agent 发布 | published_at |
| published → in_progress | 该考试任一学生开考 | started_at |
| in_progress → grading | 判卷中心出现首份结果 | grading_at |
| grading → completed | 全部确认 + finalize | completed_at |
| → cancelled | 教师取消 | cancelled_at |

- 存量迁移：`question_stats.published=True` → published；其余 → draft。
  （实现注记：Enum 列按成员 NAME 存储校验，原生 SQL 回填必须写 `PUBLISHED`/`DRAFT` 大写名，
  小写会让所有 ORM 读取 LookupError——review 发现后已修。）
- 实现期补充的合法边（状态图的收卷/握手例外，均有测试锁定）：
  published → grading（学生直接提交、未走取题握手）；published → completed 与
  in_progress → completed（发布后无人作答/进行中直接收卷）。transition() 不内嵌
  commit，事务边界归调用方（ADR-0012）。
- 已知并行真源：publish 仍写 question_stats.published 标志供旧读侧/导出，考试列表
  端点暂读标志——与 status 列的收敛为后续清理项（cancel/finalize 不回收该标志）。
- finalize 数据来源 = 判卷中心统计（均分/分布/参与 + 逐生分布），替换 exam.py 的 TODO 占位。

## 测试决策

- 状态迁移表驱动：合法迁移放行 + 非法迁移拒绝（如 completed → in_progress）。
- 学生可见性：draft/cancelled 不出现在任务列表；published/in_progress 出现且带标题与类型；completed 后不可再作答。
- 混合题型端到端：考试含选择 + 计算，学生分别作答提交，进入判卷中心异步队列。
- 先例：`tests/test_permission_matrix.py`（权限边界）、判卷中心测试。

## Out of Scope

- 考试定时（限时交卷）与防切屏。
- 补考/缓考流程。
- archived 态的归档存储策略（只建态，不迁移数据）。

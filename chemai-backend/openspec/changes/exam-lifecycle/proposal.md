# 考试生命周期（Exam Lifecycle States）

## Why

领域词汇表（CONTEXT.md）承诺考试六态生命周期（draft → published → in_progress → grading → completed → archived），数据库里只有 JSON 里的一个 published 标志——文档 interface 与 implementation 严重脱节。「grading」态不存在意味着判卷中心没有明确的入口态握手；学生没有任何正当路径在线作答已发布的考试（考试路由整体 teacher-only，ADR-0009 默认拒绝）；考试与练习在学生端同名「练习」不可区分（任务列表无标题/类型字段）；考试 finalize 只清点人数，平均分是 TODO。

## What Changes

- **ExamRecord 增加 status 列**，做实六态状态机；存量迁移：published 标志 → published 态，其余 → draft 态。
- **状态转移规则**：发布 → published；学生开考 → in_progress；判卷中心出现结果 → grading；全部确认/finalize → completed。每步记录时间戳。
- **学生作答走本人路由族**：扩展现有练习学生面（allow_self：任务列表/题目内容/提交）承载考试语义——考试按状态过滤出现在学生任务列表（带标题与类型，与练习可区分）；不开放 teacher 路由（ADR-0008/0009 框架内设计）。
- **finalize 真实统计**：从判卷中心读真实均分/分布，替换 TODO。
- **学生端支持混合题型作答**：选择题之外的题型提供文本输入；已提交后考试不可重复作答。

> 决策来源说明：本 change 的两项关键决策（做实六态 vs ADR 收缩承诺；学生作答 seam 选练习学生面）在 grilling 中按「全量实现」总指令代定，已在方案文档标注可推翻。

## Capabilities

### New Capabilities
- `exam-lifecycle`: 考试状态机——六态迁移合法、时间戳留痕、学生按状态可见可作答、finalize 产出真实统计。

## Impact

- **代码**：ExamRecord 模型 + Alembic 迁移；`app/api/exam.py` publish/finalize 改造；`app/api/practice.py` 学生任务面扩展（title/type/状态过滤）；`frontend/m/practice.html` 混合题型作答 UI。
- **依赖**：判卷中心（grading 态判定与 finalize 数据来源）——**本 change 依赖 grading-center 先行**。
- **API**：学生任务响应增加标题/类型字段（向后兼容）；考试路由权限边界不变。
- **测试**：状态迁移表驱动用例；学生可见性过滤；混合题型提交端到端。

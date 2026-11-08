## Purpose

考试六态生命周期做实：状态迁移合法且留痕、学生按状态在线作答已发布考试、finalize 产出真实统计——文档承诺与实现同构。

## ADDED Requirements

### Requirement: 状态机迁移合法且留痕
考试记录 SHALL 具有生命周期状态，SHALL 仅允许既有状态图上的迁移（draft → published → in_progress → grading → completed → archived，任意非终态可 cancelled），每次迁移 SHALL 记录时间戳；非法迁移 SHALL 被拒绝。

#### Scenario: 发布考试
- **WHEN** 教师发布一场草稿考试
- **THEN** 状态变为 published 并记录发布时间

#### Scenario: 非法迁移被拒
- **WHEN** 试图把一场已完成的考试置回进行中
- **THEN** 迁移被拒绝，状态与时间戳保持不变

#### Scenario: 存量数据迁移
- **WHEN** 状态列上线迁移执行
- **THEN** 原 published 标志为真的考试变为 published 态，其余变为 draft 态，无数据丢失

### Requirement: 学生按状态可见考试
学生任务列表 SHALL 按**学生维度**呈现考试：未交卷学生可见 published 与 in_progress 的考试（可继续作答），**grading 对未交卷学生同样开放**——同班有人先交卷不等于考试对该生关闭；completed/archived 才挡住未交卷学生。已交卷学生的考试 SHALL 始终按「已完成」分区可见（提交后不消失，成绩与答卷可回看）。draft/cancelled 的考试 SHALL NOT 出现在学生列表。任务 SHALL 附带标题与类型使其与练习可区分。

#### Scenario: 发布后学生可见
- **WHEN** 一场考试被发布
- **THEN** 该班学生任务列表出现该考试，显示考试标题与类型标识

#### Scenario: 同班先交卷不关闭考试
- **WHEN** 一场 in_progress 考试因首份结果转为 grading 态，但该生尚未交卷
- **THEN** 该生任务列表仍呈现该考试，取题接口仍可获取未作答题目

#### Scenario: 完成后不再待完成
- **WHEN** 一场考试 finalize 完成
- **THEN** 该考试离开未交卷学生的待完成列表；已交卷学生仍可在「已完成」分区回看该考试

### Requirement: 学生在线作答考试
学生 SHALL 能经本人路由族作答已发布/进行中的考试：混合题型（选择题 + 文本作答的主观题）均可提交；开考 SHALL 把考试置为 in_progress；同一学生对同一场考试 SHALL 只能提交一次。

#### Scenario: 混合题型考试作答
- **WHEN** 学生作答一场含选择题与计算题的考试并提交
- **THEN** 选择题即时判定，计算题进入主观题判定队列，考试状态为 grading（首份结果出现后）

#### Scenario: 重复提交被拒
- **WHEN** 学生对同一场考试第二次提交
- **THEN** 提交被拒绝，原有作答保持不变

#### Scenario: 学生不能触达教师路由
- **WHEN** 学生请求任一教师侧考试管理端点
- **THEN** 请求被拒绝（默认拒绝边界不放松）

### Requirement: finalize 产出真实统计
finalize SHALL 基于判卷中心的落库结果计算真实统计（平均分/分布/参与率），SHALL NOT 返回占位数据。

#### Scenario: 全部确认后 finalize
- **WHEN** 一场考试全部结果经教师确认后执行 finalize
- **THEN** 考试状态变为 completed，统计中的平均分与逐生结果一致

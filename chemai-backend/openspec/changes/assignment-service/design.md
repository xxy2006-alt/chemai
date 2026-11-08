# 练习分发 — 设计决策

> 来源：架构评审 + grilling 定案（2026-09-12），决策编号 C2-1 ~ C2-6。
> 总纲：ADR-0012（逻辑住 service module；skill 只能是薄 HTTP 客户端包装，不承载逻辑）。

## 逻辑归属（决策 C2-1）

进程内 service module（`assignment_service`）。否决「逻辑住 chem_skills handler」：skill handler 是 HTTP 客户端形态，会造成 REST→skill→REST 回环，且 4 个未接线 skill 已示范平行漂移；否决「就地抽函数」：scheduler 与组卷页接入时依赖一个 API 模块，service 无家。

## Interface（决策 C2-2）

```
assign(targets, source, name_hint) -> list[AssignmentResult] | AssignmentBatch
progress(batch_id) -> BatchProgress
```

- source 是值对象三选一：`Adaptive(kps?, count)` / `Bank(set_id)` / `Manual(question_ids)`。三来源只在「怎么取题」（内部 compose）不同，落库与分发尾部共用。
- 否决「三个独立方法」（interface 变宽、尾部重复三遍）与「compose→distribute 两阶段」（人工审核环节与人均一套的个性化量级冲突）。

## 质量闸（决策 C2-3）

Adaptive 来源走机器闸：生成 → 四维审核（既有引擎）→ 不达标自动重生成一次 → 再不过剔除换题 → 落库如实记 audit_status。人工逐题确认否决：40 人 × 5 题 = 200 题的人审量级不现实；教师对「布置」这个动作的把关由既有审批卡片承担。

## 批处理（决策 C2-4）

≤5 人同步（Agent 对话即时出真实结果卡片）；>5 人切 Celery 批次、逐生作业以 student_id 为幂等键（ADR-0006 至少一次投递契约），Agent 告知老师稍后回来查——复用 OCR 批已验证的异步交互模式（ADR-0005 G1）。原 `students[:5]` 裸截断消灭，批次切分收进服务内部。

## 调用方收敛（决策 C2-5）

| 调用方 | 处置 |
|--------|------|
| Agent 工具 assign_adaptive_practice | 变薄 adapter，返回真实逐生结果/批次号 |
| REST POST /api/practice/assign | 保留变薄（服务的 HTTP adapter，外部包装入口） |
| question.py smart-assign / batch-assign | 删除（零前端调用 + 重指外键偷题 + 非法裸枚举串） |
| 每日定时任务 | 改调服务 Bank 来源，生成有题的每日练习 |

## Agent 工具面（决策 C2-6）

改造 `assign_adaptive_practice`（名称/docstring 不变）+ 新增 `query_assignment_progress(batch_id)`，读写分离。审批卡片保留（布置是影响学生的写操作）。

## 测试决策

- 服务层 interface 为测试面：合成学生 + 假 LLM——三 source 各一条 compose 断言；机器闸「重生成一次再剔除」断言；>5 人批次切分与逐生幂等断言（作业重放不重复建卷）。
- 端到端：布置 → 学生任务列表出现该练习（含题目数）→ 可进入作答。
- Agent 工具只测薄壳转发与返回 JSON 形状。
- 先例：`tests/test_assign_practice.py`（布置）、`tests/test_practice_pipeline.py`。

## Out of Scope

- 学生通知投递本身（P3 `notification-dispatch`；本服务只发事件挂钩）。
- 组卷页 UI 的布置交互改造（接入服务后端点已兼容，页面另行）。
- 跨班布置、截止提醒调度。

## 追加决策（2026-09-14）
- **同步布置幂等（发现 #7）**：sync 路径 record_id 加入目标学生+来源+题目要点的内容摘要，双触发不再产生重复布置与重复通知。
- **adaptive 题型（发现 #10）**：question_types 不再硬编码 choice，按知识点配置可含主观题（配合判卷中心语义判定管线）。

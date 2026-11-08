# 考试生命周期 — 任务清单

> 前置依赖：grading-center change 完成（grading 态判定与 finalize 数据来源）。

## 1. 状态机

- [x] 1.1 ExamRecord 增加 status 列 + 时间戳字段；Alembic 迁移（published 标志 → published 态，其余 → draft）
- [x] 1.2 迁移函数：合法迁移放行 + 留痕，非法迁移拒绝（表驱动校验）
- [x] 1.3 `app/api/exam.py` publish 改为状态迁移；finalize 接判卷中心统计（替换 TODO）

## 2. 学生作答面（练习学生面扩展）

- [x] 2.1 学生任务列表按状态过滤（考试仅 published/in_progress），响应补 title/type 字段（向后兼容）
- [x] 2.2 开考置 in_progress（首次取题时迁移 + 留痕）
- [x] 2.3 提交一次性守卫（同生同考试二次提交拒绝）；判卷中心首份结果触发 grading 态
- [x] 2.4 `frontend/m/practice.html`：混合题型作答（选择题 UI + 主观题文本域）、考试标题/类型展示、已提交锁定态

## 3. 测试与回归

- [x] 3.1 状态迁移表驱动用例（含非法迁移拒绝、存量迁移）
- [x] 3.2 学生可见性过滤 + 越权（学生触达教师路由被拒）
- [x] 3.3 混合题型考试端到端：发布 → 开考 → 提交 → grading → 确认 → finalize completed
- [x] 3.4 `pytest` + `ruff check .` 全绿，练习流既有测试不回归

## 4. 实现说明（2026-09-12）

- [x] 4.1 published→completed 额外放行（发布后无人作答直接收卷的现实路径），draft→completed 仍拒绝
- [x] 4.2 存量回填双路径：migrate.py 原生 SQL（按 question_stats JSON 解析 + type 名大小写兼容）
  与 exam_lifecycle.backfill_statuses（ORM，测试/工具用）；Enum 列按 name 存储（EXAM）已对齐
- [x] 4.3 学生任务列表同时下发 title/type 字段（向后兼容），前端考试徽标区分
- [x] 4.4 e2e 采用自包含 StaticPool 会话（TestClient 跨线程；conftest 引擎无线程共享已踩坑记录）
- 验证：lifecycle 套件 11 绿；全量 616 passed（4 失败为分支基点已有）；ruff 全绿；practice.html JS 语法检查通过

## 5. code-review 修正（2026-09-12，双轴审查后）

- [x] 5.1 生产级迁移 bug：原生 SQL 回填写小写枚举值，ORM 按成员 NAME 校验 →
  迁移后所有 ExamRecord 查询 LookupError；改写 `PUBLISHED`/`DRAFT` 大写名（复验通过）
- [x] 5.2 学生任务装配双份漂移（helper 死代码 + 端点内联副本）→ student_tasks
  唯一实现，端点循环删除；_status_of 私有跨模块引用 → 公开 status_of
- [x] 5.3 内容端点无状态门（draft/cancelled/completed 考试可凭 ID 取题）→
  仅 published/in_progress 放行，其余 404 不泄漏存在性
- [x] 5.4 cancel 端点缺失（spec 状态图 cancelled 仅测试可达）→ POST /cancel
  （非终态可取消，终态 400）
- [x] 5.5 transition 内嵌 commit + 调用方再 commit（ADR-0012 事务边界）→
  transition 只改对象，提交归调用方；内容端点开考握手补 commit
- [x] 5.6 finalize 补逐生分布（design Interface「均分/分布/参与」落实）
- [x] 5.7 spec/design 补记实现期合法边（published→grading/completed、
  in_progress→completed）与 question_stats.published 并行真源的已知清理项
- 验证：lifecycle 11 绿；全量 616 passed（4 失败为基点已有）；ruff 全绿

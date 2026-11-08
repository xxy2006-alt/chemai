# 练习分发（Assignment Service）

## Why

「布置练习」存在 3.5 份各自漂移的实现：Agent 工具 `assign_adaptive_practice` 调 LLM 生成题目后不解析不落库，聊天卡片却显示「已为 N 名学生布置练习」（题目蒸发）；REST `POST /api/practice/assign` 完整落库但前端零调用（死代码）且截断前 5 名学生；每日定时任务建练习记录不建题目（学生收到空卷）；`question.py` 的 smart-assign/batch-assign 零调用且会把别处题库的题目外键重指（偷题）。学生永远收不到 Agent 布置的练习——业务闭环在第一环就断了。

## What Changes

- **新建练习分发服务**（ADR-0012 service module）：单一 `assign(targets, source, params)` 入口，source 为 Adaptive（AI 按最近发展区逐生生成 + 四维审核机器闸）/ Bank（既有题库）/ Manual（教师选题）三种取题策略；内部承载逐生落库、批次切分、幂等、通知挂钩。
- **Adaptive 质量机器闸**：生成 → 四维审核 → 不达标自动重生成一次 → 再不过剔除换题；落库如实记录审核状态。
- **小同步 + 大异步**：≤5 人同步完成并返回逐生真实结果；>5 人切 Celery 批次（逐生作业以 student_id 幂等），返回批次号供查询进度。
- **Agent 工具改造**：`assign_adaptive_practice` 保留名称与 docstring，实现改为调服务，返回真实逐生结果（不再谎报）；新增 `query_assignment_progress` 查询工具。
- **调用方全收敛**：删除 `question.py` 的 smart-assign 与 batch-assign 两个死端点（含偷题行为）；`POST /api/practice/assign` 变薄为服务的 HTTP adapter；每日定时任务改调服务的 Bank 来源（消灭空卷）。
- **通知挂钩预留**：布置完成后发出事件，供学生触达（P3）接入。

## Capabilities

### New Capabilities
- `assignment`: 练习分发——把练习（自适应生成 / 题库选取 / 手动指定）真实送达每个学生的任务列表，单一入口、机器质量闸、大批异步、结果可查。

## Impact

- **代码**：新建 `app/services/assignment_service.py`；`agent/tools/diagnosis.py` 布置工具变薄；`app/api/practice.py` assign 变薄；删除 `app/api/question.py` 两个 assign 端点；`app/scheduler/daily_practice.py` 改调服务。
- **API**：删除两个零调用端点（无前端影响）；assign 语义由服务定义，响应含逐生真实结果或批次号。
- **数据**：复用 ExamRecord(PRACTICE) + Question；新增 `assignment_batches` 表承载异步批次清单（migrate.py 幂等建表，存量库兼容）。
- **依赖**：Celery（ADR-0006）、四维审核引擎（既有）、ZPD 计算迁入服务。
- **测试**：服务层为测试面（合成学生 + 假 LLM）；三种 source 各一条、机器闸重生成、批次幂等。

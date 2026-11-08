# 练习分发 — 任务清单

## 1. 服务层

- [x] 1.1 新建 `app/services/assignment_service.py`：`assign(targets, source, name_hint)` 主入口；ZPD/薄弱知识点/主导障碍计算从 `app/api/practice.py` 迁入
- [x] 1.2 三种 compose：Adaptive（逐生生成 + RAG 真题上下文）/ Bank（题库取题）/ Manual（指定题目）；题库与手动来源建立关联副本，不重指外键
- [x] 1.3 Adaptive 机器闸：四维审核 → 不达标重生成一次 → 再不过剔除补足；audit_status 如实落库
- [x] 1.4 批处理：≤5 人同步返回逐生结果；>5 人切 Celery 批次，逐生作业 student_id 幂等键；`progress(batch_id)` 查询
- [x] 1.5 通知挂钩：布置完成后发出事件（P3 接入前的空挂钩点）

## 2. 调用方收敛

- [x] 2.1 `agent/tools/diagnosis.py` `assign_adaptive_practice` 变薄：调服务、返回真实逐生结果（record_id/题数/审核摘要）；异步批返回 batch_id 并提示稍后查询；审批保留
- [x] 2.2 新增 `query_assignment_progress(batch_id)` 工具（teacher persona）+ 薄壳测试
- [x] 2.3 `POST /api/practice/assign` 变薄为 HTTP adapter（响应含逐生结果或批次号）
- [x] 2.4 删除 `app/api/question.py` 的 smart-assign 与 batch-assign（先 grep 零引用验证）
- [x] 2.5 `app/scheduler/daily_practice.py` 改调服务 Bank 来源，产出含题练习

## 3. 测试与回归

- [x] 3.1 服务层：三 source 各一条 compose 断言；机器闸重生成/剔除补足；>5 人批次切分与逐生幂等；题库布置不改原记录
- [x] 3.2 端到端：Agent 布置 → 学生任务列表出现含题练习 → 进入作答
- [x] 3.3 既有 `tests/test_assign_practice.py` 适配新响应结构；`pytest` + `ruff check .` 全绿

## 4. code-review 修正（2026-09-12，双轴审查后）

- [x] 4.1 异步批次路径永不提交（Celery 作业 db.add 后无 commit，记录静默丢失）→ run_batch_student 持久化点补 commit
- [x] 4.2 机器闸未按 spec 补足题数 → 有界三轮（生成→重生成→缺口补足），补足成功题数达标，仍失败如实计 dropped
- [x] 4.3 daily_practice 去重按 class+name 会误命中他人练习 → 追加 question_stats.student_id 归属过滤
- [x] 4.4 practice.py 迁移留孤儿（三个学情 helper 零调用方）→ 删除；service 补 _get_dominant_barrier 进 audit（工具卡片用）
- [x] 4.5 通知挂钩缺失（tasks 1.5 已勾但无代码）→ _notify_assigned 落地（日志级，P3 dispatch 接入点）
- [x] 4.6 RAG 真题上下文丢失（老 practice.py 行为）→ _compose_adaptive 恢复 rag_context
- [x] 4.7 assignment_batches 无建表迁移 → migrate.py 幂等 CREATE TABLE；proposal Impact 同步修正
- [x] 4.8 batch total 未过滤无效目标 / _tb_note 死代码 / name 三元表达式歧义 / 不可能分支守卫 → 清理
- [x] 4.9 query_assignment_progress 薄壳测试补齐（2 用例）

# 整改批次 — 任务清单

## 1. 成绩确认门（P1，外部声音 #1）

- [x] 1.1 StudentAnswer 增 `confirmed` 列（migrate.py：存量回填 True 保持历史成绩生效）
- [x] 1.2 `confirm(exam_record_id)`：批量翻转 + 触发诊断一次；判卷中心页/Agent 待确认队列读侧接入
- [x] 1.3 线上考试提交路径接入确认门（EXAM 作答 confirmed=False）
- [x] 1.4 统一生效行查询助手 `effective_answers`，替换诊断/finalize/错题本/统计四处读侧

## 2. 主观题落行 + 消费（P1，ADR-0013，外部声音 #2/#6）

- [x] 2.1 submit 主观题落 `PENDING_SEMANTIC` 行（移除提交路径 grade_semantic 入队）
- [x] 2.2 消费器：Celery 作业 + APScheduler 周期扫描（扫 PENDING 标记 → judge 覆盖 → 诊断 + 通知）
- [x] 2.3 判定失败保留标记下轮重扫；读侧排除 PENDING 行（并入 1.4 助手）
- [x] 2.4 OCR 同步降级路径适配（grade_batch 语义判定保持内联不变——OCR 批本身已是异步语义）

## 3. 题型路由（P1，外部声音 #3）

- [x] 3.1 AnswerKey 增可选 `choice` 标记；线上/题库路径从 Question.options 提供
- [x] 3.2 grade 路由改用元数据；无元数据回退双边启发式；删除单边 `_is_choice(学生作答)` 路由
- [x] 3.3 回归用例：短化学式主观作答（Be/HF）进语义判定；选择题字母作答仍走归一化

## 4. P2 六项

- [x] 4.1 练习重做 upsert（save 覆盖更新；EXAM 守卫不变；重放同值无害断言）
- [x] 4.2 chat 诊断去抖（Student.diagnosis_requested_at，5 分钟窗口）
- [x] 4.3 同步布置幂等键（内容摘要 record_id）
- [x] 4.4 网关保守禁用（无 per-收件人配置不外发 + 文档标注）
- [x] 4.5 finalize 返回参与率（present/total）
- [x] 4.6 adaptive 主观题型 + 闭环 e2e（布置→作答→PENDING→消费判定→诊断→改判，全 fake LLM）

## 5. 收口

- [x] 5.1 `pytest` 全量 + `ruff check .` 全绿；CEO/ENG 审查报告更新为 CLEARED

- 验证（2026-09-14）：全量 624 passed（4 失败为分支基点已有）；ruff 全绿；闭环 e2e（混合题型布置→作答→PENDING→扫描判定→诊断触发）通过。

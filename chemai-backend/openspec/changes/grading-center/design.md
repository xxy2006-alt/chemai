# 判卷中心 — 设计决策

> 来源：架构评审 + grilling 定案（2026-09-12），决策编号 C1-1 ~ C1-6。
> 总纲：ADR-0012（业务逻辑住 service module，agent 工具与 HTTP 均为 adapter）。

## 核心决策：内核统一，入口分离

「线上判卷和线下判卷分离还是统一」的定案：**都不是——判卷内核统一，进入判卷的管线分离**。

统一的是「作答怎么判、判完怎么落库」：方程式等价判定不关心答案是键盘打的还是 OCR 认的；归一化匹配、批量语义判定、save 幂等、诊断触发、教师 override 只存在一份。

分离的是「作答怎么进来」（adapter 层前置管线）：线上（登录态身份、干净文本、练习即生效、无工件）、OCR（学号姓名匹配、噪声文本、确认制、原图+批注图工件）、教师手动（人工录入判定）。

验收标准：给语义判定加一种新等价规则，改一处，线上与线下同时生效。

## Interface（决策 C1-1，2026-09-12 定案）

```
grade(entries: list[AnswerEntry], key: AnswerKey) -> list[QuestionResult]
save(results, student_id, exam_record_id, source: online|ocr|manual|chat|training) -> None
override(answer_id, is_correct, reason, teacher_id) -> None
confirm(exam_record_id) -> None
finalize(exam_record_id) -> Stats
```

- `AnswerEntry` 与来源无关：题目引用（question_id 或题号）+ 原文作答。三路入口各自负责把原始形态转成 AnswerEntry。
- 现有 `grade_batch_answers` 的 OCR 形状入参降级为 OCR adapter 的内部转换，不再是判卷入口。

## 判卷时机（决策 C1-2）

选择题归一化匹配同步判（学生当场看到这部分分）；填空/计算/简答走 Celery 异步 LLM 语义判，学生看到「已提交，主观题待判定」，教师在判卷中心看到待确认队列。复用现有分层判卷哲学与 OCR 批已验证的异步交互模式（ADR-0005 G1）。

## 生效策略（决策 C1-3）

| 记录类型 | AI 判结果 | 教师角色 |
|----------|-----------|----------|
| 练习 PRACTICE | 即写入 StudentAnswer、即喂诊断 | 事后 override 纠偏，改判重触发该生诊断 |
| 考试 EXAM | 待确认队列 | 确认（confirm）后才 save 生效 |

## 双管线整合（决策 C1-4）

correct_edu 上传会话判卷管线尾部统一到 save；StudentSubmission 降级为图片工件记录（原 graded image 归档），不再是成绩载体。上传会话判卷入口保留。

## Agent 工具面（决策 C1-6，沿用 C2-6 模式）

`grade_answer_sheets` / `save_grading_results` 保留名称与 docstring（LLM interface 不变），implementation 改为调 service；新增 `query_grading_queue(teacher_id)` 读待判/待确认队列——读写分离，LLM 选择面清晰。

## 测试决策

- 服务层 interface 是唯一测试面：归一化匹配用表驱动用例；语义判定注入假 LLM 断言批量调用 ≤1 次/批；save 幂等（同 answer_id 重放不重复）；override 后诊断作业重入队；练习/考试两档生效各一条端到端断言。
- agent 工具只测薄壳：转发参数正确 + 返回 JSON 形状（不测业务，业务在服务层已覆盖）。
- 先例：`tests/test_practice_pipeline.py`（模型级管线）、`tests/test_api_auth_notification.py`（最小 app + dependency_overrides）。
- 好测试只断言外部行为：判对判错、落库与否、诊断触发与否——不断言内部函数调用次序。

## Out of Scope

- 学生端主观题公式编辑器（先文本域）。
- 语义判定提示词调优与判分权重（沿用现有 llm_grading 提示词）。
- 考试状态机（P4 `exam-lifecycle` change 承载；本 change 的 finalize 提供数据）。
- 判卷结果家长报告格式化（沿用既有周报/报告通道）。


## 追加决策（2026-09-14，外部声音审查后修复定案）

- **确认制落地（发现 #1）**：StudentAnswer 增 `confirmed` 列——练习/chat/training 默认 True；考试作答默认 False，`confirm(exam_record_id)` 批量翻转并触发诊断；诊断/finalize/错题本/统计读侧只认生效行。线上提交路径接入确认门（此前 EXAM 即写即生效的违约行为修正）。
- **主观题管线（发现 #2/#6）**：落行 + 消费统一，见 ADR-0013。`grade` 不再在提交路径同步语义判定；`PENDING_SEMANTIC` 行由 Celery/APScheduler 双路消费覆盖。
- **题型路由（发现 #3）**：AnswerKey 条目增可选 `choice` 标记（线上/题库路径从 Question.options 提供）；无元数据的 OCR 贴答案场景回退双边启发式（correct 与 student 都是 1-4 位字母才算选择题）。废除单边 `_is_choice(学生作答)`。
- **练习重做（发现 #4）**：save 对练习路径改 upsert 语义（重做覆盖旧判定；作业重放同值无害）；EXAM 由一次性守卫挡在 save 之前。
- **finalize 参与率（发现 #9）**：finalize 返回 present/total 供前端标注部分数据口径。

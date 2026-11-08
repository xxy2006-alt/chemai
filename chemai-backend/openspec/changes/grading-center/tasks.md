# 判卷中心 — 任务清单

## 1. 服务层（llm_grading → grading_center）

- [x] 1.1 新建 `grading_center` 服务：定义作答条目/答案键/判定结果三形态，把 `grade_batch_answers` 的归一化匹配与批量语义判定内核迁为 `grade(entries, key)`，OCR 形状入参降级为 OCR adapter 内部转换
- [x] 1.2 实现 `save(results, student_id, exam_record_id, source)`：单点写 StudentAnswer（幂等按 answer_id 去重）、按记录类型定生效策略（练习即生效 + 触发诊断作业；考试仅经确认后的 save_batch 落库）
- [x] 1.3 实现 `override(answer_id, is_correct, reason, teacher_id)`：更新判定并以该生为单位重触发诊断
- [x] 1.4 `finalize(exam_record_id)` 已实现并接入 exam finalize 端点（真实均分/参与，替换 TODO）；`grade_ocr_batch` 批改编排为确认保存的原语
- [ ] 1.6 `confirm(exam_record_id)` 考试级批量确认：OCRTask 保存前无 exam 关联字段，须与 P4 状态机（grading 态握手）一并落地
- [x] 1.5 `StudentAnswer` 增加 `source` 列 + 存量迁移（Alembic；回填 online/ocr）

## 2. 线上提交接线

- [x] 2.1 `POST /api/practice/submit` 尾部改调 grade + save：选择题同步判即时返回；主观题 enqueue Celery 语义判卷作业
- [x] 2.2 删除练习提交路径的内联 barrier 启发式（诊断作业成为唯一写者），保留真实 barrier 分布返回
- [x] 2.3 响应增加主观题待判定态字段，前端 `m/practice.html` 结果页展示

## 3. OCR 与既有管线统一

- [x] 3.1 `agent/tools/ocr_grading.py` 的 `save_grading_results` 落库体搬进 service，工具与 `app/api/ocr_sheets.py` 保存端点都变薄 adapter（消灭 HTTP 反调工具的倒置）
- [x] 3.2 `grade_answer_sheets` 工具改调 `grade`（interface/docstring 不变）
- [x] 3.3 correct_edu 上传会话无学生身份（roster 匹配不可行）——StudentSubmission 定为工件记录并注释约束；需入学情的判卷走批量管线（实现与 spec 意图的偏差已记录）
- [x] 3.4 `/api/ocr/stats` 粘贴判卷经判卷中心 grade+save（source=manual，Layer-1 归一化），诊断入队落库
- [x] 3.5 `wrong_question_trainer` 作答补 `source=training` 标记

## 4. Agent 工具面

- [x] 4.1 新增 `query_grading_queue(teacher_id)` 工具（teacher persona），返回待判定/待确认数量及构成
- [x] 4.2 薄壳测试：转发参数与返回 JSON 形状

## 5. 判卷中心前端

- [x] 5.1 `OcrSheetsPage.tsx` 升格为判卷中心：保留答题卡批量 tab，新增「待判队列」（主观题结果 + 考试确认）与「线上提交」（逐生逐题浏览 + 改判）
- [x] 5.2 改判交互调用 override 端点，确认操作调用 confirm 端点

## 6. 测试与回归

- [x] 6.1 服务层：归一化匹配表驱动用例；假 LLM 断言语义判定 ≤1 次/批；save 幂等；override 重触发诊断；练习/考试两档生效端到端
- [x] 6.2 线上提交含主观题的端到端（同步部分 + 队列部分分别断言）
- [x] 6.3 `ruff check .` 全绿；pytest 全量通过（4 失败为分支基点已有）；OCR 判卷/保存/工具契约测试不回归（§7 有终态记录）

## 7. code-review 修正（2026-09-12，双轴审查后）

- [x] 7.1 练习完成数双计：save 不再按题累加，提交路径 +1/次
- [x] 7.2 两段式提交诊断双触发：同步段 trigger_diagnosis=False，异步收尾段触发一次
- [x] 7.3 LLM 判定失败固化「判错」：judge_failed 标记 + 作业侧过滤，重试重新判定
- [x] 7.4 /stats 与错题训练内联写库（ADR-0012 硬违反）：统一走 grade+save（training 按会话前缀隔离幂等）
- [x] 7.5 工具/端点双份批改编排：收敛 grade_ocr_batch 单实现
- [x] 7.6 _compare_answers 私有 import：公开 normalized_match；finalize 接入 exam.py 消灭 TODO
- [x] 7.7 队列读侧移除硬编码 pending_semantic=0（Celery 在途态无落表，诚实留白待 P3）

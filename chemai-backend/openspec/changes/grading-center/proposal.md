# 判卷中心（Grading Center）

## Why

线上作答与线下答题卡走两套互不相识的判卷实现：线上只有字符串精确匹配（P0 已修提交键名 bug，但填空/计算/简答依然无法判定），LLM 语义判卷（方程式等价、离子式、过程判定）只存在于 OCR 答题卡管线。落库侧 StudentAnswer 有 4 条散落写入路径，`save_grading_results` 的落库逻辑住在 agent 工具文件里、HTTP 保存端点反向调用工具函数（依赖倒置）；correct_edu 管线写的 StudentSubmission 只写不读；exam finalize 的平均分是 TODO。教师没有任何人工改判或确认线上结果的入口——「出了练习谁来判」没有答案，诊断吃到的数据既不完整也不可信。

## What Changes

- **深化 `llm_grading.py` 为判卷中心服务**：interface 抬到与作答来源无关的形状——`grade(entries, key)` 分层判定（选择题归一化精确匹配 + 非选择题批量 LLM 语义判定 ≤1 次/批）、`save(results, student, exam_record_id, source)` 单点写 StudentAnswer 并按记录类型定生效策略、`override(answer_id, is_correct, reason)` 教师改判并重触发诊断、`confirm(exam_record_id)` 考试批量确认、`finalize(exam_record_id)` 真实统计。现有归一化/语义判定实现全部保留为内部函数。
- **生效策略由记录类型承载**：练习（PRACTICE）AI 判即生效、即喂诊断；考试（EXAM）保持教师确认制。
- **线上提交接线**：选择题同步判（学生当场见分），主观题入 Celery 队列异步语义判，学生见「主观题待判定」。
- **落库逻辑搬家**：save 从 agent 工具搬进 service，agent 工具与 HTTP 端点都变薄 adapter（ADR-0012）。
- **双管线尾部统一**：correct_edu 上传会话判卷、`/api/ocr/stats` 粘贴判卷的尾部统一走 save；StudentSubmission 降级为图片工件记录。
- **内联 barrier 启发式删除**：诊断作业成为 barrier 的唯一写者（消灭双写竞争）。
- **前端**：答题卡批量页升格为判卷中心，新增「待判队列」「线上提交」tab（逐生逐题浏览 + 改判）。
- **Agent**：新增 `query_grading_queue` 工具；`grade_answer_sheets` / `save_grading_results` 重接 service。

## Capabilities

### New Capabilities
- `grading-center`: 一切作答（线上提交 / 答题卡 OCR / 教师手动）经同一判卷、落库、纠偏路径；分层判定；练习即生效、考试确认制；教师可改判。

### Modified Capabilities
- `diagnosis-writeback`（既有）：barrier 写者收敛为诊断作业单点，练习提交路径的内联启发式移除。

## Impact

- **代码**：`app/services/llm_grading.py` → `app/services/grading_center.py`（深化更名）；`app/api/practice.py` submit 尾部改接；`agent/tools/ocr_grading.py` 变薄；`app/api/ocr_sheets.py`、`app/api/ocr.py`、`app/services/ocr_service.py` 尾部统一；`app/services/wrong_question_trainer.py` 补 source 标记；前端 `OcrSheetsPage.tsx` 升格。
- **API**：`POST /api/practice/submit` 响应语义增强（主观题待判定态）；OCR 保存端点契约不变。
- **数据**：`StudentAnswer` 增加 `source` 列（存量回填 online/ocr）。
- **依赖**：Celery 队列承载主观题语义判卷作业（ADR-0006）。
- **测试**：服务层为测试面（合成作答 + 假 LLM）；agent 工具只测薄壳转发；`pytest` + `ruff check .` 全绿。

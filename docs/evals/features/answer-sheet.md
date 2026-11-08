# Answer Sheet Grading — 六层评测

## 1. Capability (功能层)

| 编号 | 测试 | 位置 | 类型 |
|------|------|------|:---:|
| AS-C01 | ocr_tasks 表创建和 CRUD | `test_ocr_pipeline.py` | 确定性 |
| AS-C02 | 任务状态流转 pending→processing→done/failed | `test_ocr_pipeline.py` | 确定性 |
| AS-C03 | 答案语义对比 (大小写/空格) | `test_llm_grading.py` | 确定性 |
| AS-C04 | 批改管线 (正确匹配+空OCR) | `test_llm_grading.py` | 确定性 |
| AS-C05 | 3个 OCR tool 在 teacher persona | `test_tool_filtering.py` | 确定性 |

**CI 门禁：** 100% (全部确定性断言)

## 2. Routing (路由层)

| 编号 | 场景 | 预期路由 |
|------|------|---------|
| AS-R01 | 教师说"答题卡识别进度" | → query_ocr_progress |
| AS-R02 | 教师说"开始批改答题卡" | → grade_answer_sheets |
| AS-R03 | 教师说"保存批改结果" | → save_grading_results |

**CI 门禁：** >= 85%

## 3. Safety (安全层)

| 编号 | 场景 | 预期 |
|------|------|------|
| AS-S01 | Student persona 无 OCR tool | query/grading/save 都不在 student persona |
| AS-S02 | Teacher 查其他教师的 batch | 404 或空结果 |
| AS-S03 | OCR 引擎故障 | 任务标记 failed，不崩溃系统 |

**CI 门禁：** AS-S01/AS-S02 = 100% (确定性), AS-S03 >= 90%

## 4. State (状态层)

| 编号 | 场景 | 预期 |
|------|------|------|
| AS-T01 | OCR 任务处理中被服务重启打断 | 重启后继续 pending 任务 |
| AS-T02 | 批改结果未确认前不写入 StudentAnswer | grading_result 有值但 confirmed=False |

## 5. Quality (质量层)

| 编号 | 场景 | 评测 | 目标 |
|------|------|------|------|
| AS-Q01 | LLM 批改准确性 | LLM judge | >= 4.0/5 |
| AS-Q02 | OCR 识别准确率 (手写体) | 人工评测 | TBD |

## 6. Regression (回归层)

| 编号 | Bug | 防复发 |
|------|-----|--------|
| — | 暂无 | — |

## 未覆盖（TODO）

- 并发隔离：两个教师同时上传同批次
- 图片损坏/格式不支持
- 超大批量性能（>100 张）
- OCR 低置信度人工核验流程

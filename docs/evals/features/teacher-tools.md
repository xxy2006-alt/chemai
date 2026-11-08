# Teacher Tools — Evals

> 教师端出题/诊断/学生管理/OCR批改

## 基线

| 编号 | 测试 | 位置 | 断言 |
|------|------|------|------|
| TT-B01 | Teacher 有 15 个 tool | `test_tool_filtering.py` | 含 diagnosis/students/ocr/grading |
| TT-B02 | show_exam_workbench 可用 | `agent_eval_golden.yaml:gen-questions` | tool_called + arg_contains |
| TT-B03 | diagnose_barrier 返回 JSON | `agent_eval_golden.yaml:diagnose-single` | tool_called, route=false |
| TT-B04 | query_ocr_progress 查进度 | `test_tool_filtering.py` | 在 teacher persona |

## 边界

| 编号 | 场景 | 预期 |
|------|------|------|
| TT-E01 | Teacher 无 student tutoring tool | ionic/stoichio 不在 teacher 工具集 |
| TT-E02 | 空班级 ID 诊断 | 返回 error "class_id required" |
| TT-E03 | 两个批次的 OCR 进度并发查询 | 独立返回不串扰 |

## 回归

| 编号 | 历史 Bug | 防止措施 |
|------|---------|---------|
| TT-R01 | teacher.yaml 引用了不存在的 `import_exam_paper` | `test_tool_filtering.py` 验证 YAML skills ⊆ TOOL_META |

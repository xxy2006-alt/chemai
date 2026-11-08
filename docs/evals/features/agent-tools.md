# Agent Tools — Evals

> Tool 过滤、persona 分配、call_limit 限流

## 基线

| 编号 | 测试 | 位置 | 断言 |
|------|------|------|------|
| AT-B01 | 所有 tool 在 TOOL_META 中 | `test_tool_filtering.py` | set(TOOLS) == set(TOOL_META.keys()) |
| AT-B02 | Student 无教师工具 | `test_tool_filtering.py` | 无 exams/diagnosis/students/delete |
| AT-B03 | Student 有 9 个 tutoring tool | `test_tool_filtering.py` | ionic/stoichio/redox/equil/periodic/organic/chem/sim/web |
| AT-B04 | Teacher 有诊断+学生+OCR | `test_tool_filtering.py` | 全部 diagnosis/students/ocr tool |
| AT-B05 | call_limit >= 1 | `test_tool_filtering.py` | 所有 meta["call_limit"] >= 1 |
| AT-B06 | Persona 值合法 | `test_tool_filtering.py` | student/tutor/teacher/parent 之一 |
| AT-B07 | YAML skills 与 TOOL_META 一致 | `test_tool_filtering.py` | YAML available_skills ⊆ auto persona skills |
| AT-B08 | Tutoring factory 生成 JSON | `test_tutor_factory.py` | valid json, guidance 含关键词 |
| AT-B09 | Factory 空输入显示 intro | `test_tutor_factory.py` | title + guidance > 20 chars |
| AT-B10 | Factory 学生跟进返回 feedback | `test_tutor_factory.py` | feedback + guidance 都存在 |

## 边界

| 编号 | 场景 | 预期 |
|------|------|------|
| AT-E01 | 未注册 persona 查 tool | 返回空列表 |
| AT-E02 | call_limit=0 | Test 拒绝 |
| AT-E03 | 两个 persona YAML 空 available_skills | auto-detect from TOOL_META |

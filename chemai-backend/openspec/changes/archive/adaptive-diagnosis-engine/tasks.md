# Tasks: adaptive-diagnosis-engine

## T1: F4 障碍诊断 LLM 增强

**估时**: 2h
**涉及文件**: `app/api/diagnosis.py`, `app/services/llm_service.py`
**验证**: 班级诊断返回 LLM 实时分析结果

- [x] 1.1 新增 `POST /api/diagnosis/run-llm/{exam_id}` → 自动分析错误率高的题目
- [x] 1.2 LLM 返回的 barrier_type → 写入 `StudentAnswer.barrier_type`
- [x] 1.3 聚合 → `Student.barrier_type` JSON (weighted ratio)
- [x] 1.4 更新 `Student.barrier_last_updated`
- [x] 1.5 `PUT /api/diagnosis/override/{student_id}` → 老师手动指定 + OperationLog
- [x] 1.6 ThreadPoolExecutor(max_workers=5) 并发限制

---

## T2: F5 自适应出题核心算法

**估时**: 2.5h
**涉及文件**: `app/api/practice.py`
**验证**: 两个不同 barrier_type 的学生得到不同难度的题目

- [x] 2.1 `_calculate_zpd_difficulty()` → <40% easy / 40-70% medium / >70% hard
- [x] 2.2 `_get_weak_kps()` → Counter 统计 StudentAnswer 错误知识点 TOP3
- [x] 2.3 `POST /api/practice/assign` → 逐学生个性化调用 LLM，含 RAG context
- [x] 2.4 `POST /api/practice/submit` → 提交后自动更新 barrier_type + exercises_completed
- [x] 2.5 `GET /api/practice/effect/{student_id}` → 已是真实数据库统计

---

## T3: 全题型出题 Prompt 验证

**估时**: 1.5h
**验证**: 5 种题型生成质量通过基本检查

- [x] 3.1 5 种题型各生成 3 题 → 全部成功 (choice/fill/calc/experiment/inference)
- [x] 3.2 检查点 → choice:4选项, fill:有___标记, calc:含答案, experiment:多小问, inference:推断链
- [x] 3.3 化学方程式审核 → audit_chemical_equation() 执行，当前生成的题目以概念为主
- [x] 3.4 Prompt 调优 → 质量良好，无需调整
- [x] 3.5 各题型生成成功率 → 5/5 types = 100%

---

## T4: 诊断-出题闭环验证

**估时**: 1h
**验证**: 完整闭环数据一致性

- [x] 4.1 模拟场景 → 完整闭环: Teacher Override → Adaptive Assign → 5 students personalized
- [x] 4.2 barrier_type 变化 → override 后从 33/33/34 变为 90/5/5 (concept dominant)
- [x] 4.3 数据传递 → exam_record → question → student_answer → barrier_type 链路正确

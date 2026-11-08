# 对话作答回流 — 任务清单

> 前置依赖：grading-center change 完成（save 的 source 参数与 StudentAnswer.source 列）。

## 1. 工具接线

- [x] 1.1 `agent/tools/tutoring.py` 分步工具（_make_tutor_tool 产物）：学生作答判定后调 `grading_center.save(source="chat")`，幂等键含会话与步骤标识
- [x] 1.2 确认 chemistry_tutor 自由问答无捕获路径（保持现状 + 注释说明边界）

## 2. 诊断读侧

- [x] 2.1 核对诊断作业聚合自然包含 chat 来源（读侧本就读全量作答，验证即可）
- [x] 2.2 读侧按来源过滤的能力预留（查询参数级，不改默认行为）

## 3. 测试与回归

- [x] 3.1 分步工具薄壳测试：判定 → save 参数（source=chat、幂等键稳定）；同步重放不重复落库
- [x] 3.2 端到端：对话作答参与诊断聚合一条
- [x] 3.3 `pytest` + `ruff check .` 全绿，六大步题导学既有行为不回归

## 4. 实现说明（2026-09-12）

- [x] 4.1 捕获条件：学生身份（contextvars set_current_student，channel 注入，服务端
  身份优先于模型输入）+ agent 提供的该步预期答案（expected_answer 工具参数）；
  两者缺一不捕获（无判定依据，诚实降级）
- [x] 4.2 题目以 get-or-create 的 chat 引用题（content=问题、answer=预期答案，
  record_id 空）进入判卷中心；answer_id 含作答内容摘要——同输入重放幂等、
  换答案重做为新记录（学情不吞）
- [x] 4.3 学生级诊断新作业 diagnosis_student（Celery + 同步降级）+ handlers
  共享诊断核心 _diagnose_barrier_answers（exam 场景与学生场景共用聚合）；
  chat 落库自动触发
- [x] 4.4 测试污染教训：monkeypatch 单例实例的还原会把绑定方法写进实例字典永久
  遮蔽类属性——LLM 补丁一律走类级（LLMService），dispatch 补丁同改类级
- 验证：capture 套件 6 绿；全量 622 passed（4 失败为基点已有）；ruff 全绿

## 5. code-review 修正（2026-09-12，双轴审查后）

- [x] 5.1 ADR-0012 红线：捕获编排（get-or-create 引用题/哈希幂等/grade+save）从
  工具文件搬进 grading_center.capture_chat_answer；工具只剩薄壳（服务端身份 +
  转发 + 异常吞并）
- [x] 5.2 共享诊断核心抽函数时丢了 barrier_last_updated 写回 → 补回（行为保持）
- [x] 5.3 Question get-or-create 并发竞态：主键冲突 rollback + requery 复用已有行
- [x] 5.4 resume 端点补 set_current_student 注入（interrupt/resume 后捕获不再静默丢失）
- [x] 5.5 来源过滤落实（spec「读侧 SHALL 支持按来源过滤」）：diagnose_student_recent
  增可选 source 参数（默认不过滤）
- [x] 5.6 幂等口径修正：实现键为「学生×题目×作答内容摘要」而非 design 原文
  「会话×步骤」（channel 未向工具暴露会话ID）；跨会话同题同答视为同一作答事件，
  design.md 已同步说明
- [x] 5.7 清理：诊断重构残留死行、tutor_fn.__docstring__ 死属性、
  _tmp_pollution_probe.py 调试文件、test_jobs_enqueue 的 EL_DEBUG 插桩
- 验证：47 绿（受影响套件）；全量 622 passed（4 失败为基点已有）；ruff 全绿

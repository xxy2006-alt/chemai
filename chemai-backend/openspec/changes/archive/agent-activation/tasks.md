# Tasks: agent-activation

## T1: Skill Handler 联通服务层

**估时**: 2h
**验证**: 每个 handler 函数能成功调用并返回 service 结果

- [x] 1.1 chemistry-exam → agent/skills/generate.py + balance.py + search.py 已实现，通过 @registry.register
- [x] 1.2 chemistry-diagnosis → agent/skills/diagnose.py 已实现
- [x] 1.3 chemistry-parser → agent/skills/import_exam.py 已实现
- [x] 1.4 chemistry-memory → 新建 get_student_context() + skills_init.py
- [x] 1.5 chemistry-notification → weekly_report.py 已实现
- [x] 1.6 chemistry-improvement → 新建 assign_adaptive_practice Skill

---

## T2: Hermes Proxy 任务调度

**估时**: 1.5h
**验证**: POST `/api/hermes/chemistry-chat` 返回 Agent 响应

- [x] 2.1 任务路由 → Agent Think→Route→Execute 循环自动匹配 Skill
- [x] 2.2 多 Skill 串联 → memory → diagnose 链已测试通过
- [x] 2.3 Agent 响应格式 → SSE: {type, phase, tool_call, tool_result, text}
- [x] 2.4 SSE 流式返回 → agent.channel.fastapi_sse + StreamingResponse

---

## T3: 端到端 Agent 决策链测试

**估时**: 1.5h
**验证**: 一条自然语言指令完成完整教学任务

- [x] 3.1 场景 A → "出3道盐类水解选择题" → Agent 调用 generate_questions(盐类水解, medium, 3)
- [x] 3.2 场景 B → "诊断学生202610101" → Agent 调用 diagnose_barrier → 返回 concept:0.9
- [x] 3.3 Skill 失败降级 → generate_questions JSON解析错误时 Agent 友好回复
- [x] 3.4 9个 Skills 全部注册成功 → balance_equation, search_exam_bank, diagnose_barrier, generate_questions, chemistry_tutor, simulate_experiment, weekly_report, import_exam_paper, assign_adaptive_practice

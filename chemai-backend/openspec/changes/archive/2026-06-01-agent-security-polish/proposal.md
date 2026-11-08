## Why

Phase 1-3 构建了 agent 的能力层（多步执行、页面联动、规划），但安全边界和运维可观测性是零。Persona YAML 定义的权限规则从未被代码执行——学生 persona 理论上能调用教师专属的 import_exam_paper skill，家长 persona 的 data_access 纯属文档。没有任何 audit log 记录 skill 调用链路，出问题只能靠用户描述复现。错误处理分散在三层（skill/agent/channel）各有各的格式，排查困难。

这些是 agent 从"能跑"到"生产可用"必须补的课。

## What Changes

### Persona-based skill enforcement（`agent/core.py` + `agent/skill_registry.py`）
- `_build_system_prompt()` 只注入 persona.available_skills 中的 skill（目前注入全部 10 个）
- `_think()` 只传入允许的 tools 给 LLM function calling
- `registry.execute()` 在执行前检查 persona 是否有权限调用该 skill
- persona YAML 的 `data_access` 规则暂以文档形式保留，不做代码级数据过滤（数据过滤应在 API 层做，不在 agent 层）

### Audit logging（`agent/audit.py` 新文件）
- JSONL 格式写入 `data/audit/agent_audit.jsonl`
- 每条记录：`{timestamp, persona, user_id, skill_name, args, result_truncated, duration_ms, error}`
- 内存 ring buffer（最近 100 条）供调试面板查询
- 敏感参数自动脱敏（student_id 保留，password/parent_phone 等字段打码）

### Unified error handling（`agent/core.py` + `agent/channel/fastapi_sse.py`）
- 定义 `AgentError` 基类 + 子类（`SkillExecutionError`, `ProviderError`, `PlanError`）
- skill 级别的异常统一包装为 `AgentError` 而非裸 dict `{"error":"..."}`
- channel 级别的异常统一返回结构化 SSE event: `{type:"error", code:"...", message:"...", recoverable:bool}`
- 可恢复错误（超时、限流）→ 前端展示重试按钮；不可恢复（权限、配置）→ 展示错误描述

### Skill-level hardening（`agent/skills/*.py` 各 skill 文件）
- `weekly_report.py`: 加 student_id 权限检查（验证当前 persona 有权访问该学生）
- `diagnose.py`: class mode 加 class_id 验证
- `practice.py`: 移除对 `app.api.practice` 私有函数的脆性导入

## Capabilities

### New Capabilities
- `persona-skill-filter`: Persona YAML 的 available_skills 在 tool injection + tool execution 两层生效
- `audit-logging`: JSONL 格式的 skill 调用审计日志 + 内存 ring buffer
- `unified-error-handling`: AgentError hierarchy + 统一 SSE error 事件 + 前端错误展示
- `skill-hardening`: 修复 3 个 skill 的安全/脆性问题

## Impact

- **Files changed**: `agent/core.py` (~20 lines), `agent/skill_registry.py` (~10 lines), `agent/audit.py` (new, ~60 lines), `agent/errors.py` (new, ~30 lines), `agent/channel/fastapi_sse.py` (~10 lines), `agent/skills/weekly_report.py` (~10 lines), `agent/skills/diagnose.py` (~5 lines), `agent/skills/practice.py` (~10 lines), `frontend/js/agent.js` (~15 lines)
- **New dependency**: 无。JSONL 用 Python 内置 json 模块。ring buffer 用 collections.deque
- **Breaking**: 无。persona 过滤只限制不该有的 skill 访问，现有合法调用不变

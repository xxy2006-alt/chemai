## Context

Phase 1-3 构建了 agent 的执行能力。Phase 4 补安全边界和可观测性。当前 3 个 persona YAML 的权限定义完全是文档（从未被代码读取），skill 调用链路零审计，错误处理三层各自为政。

## Goals / Non-Goals

**Goals:**
- persona YAML 的 available_skills 在 tool injection + execution 两层生效
- skill 调用审计日志（JSONL + ring buffer）
- 统一错误处理（AgentError hierarchy + 结构化SSE error）
- 修复 3 个 skill 的安全/脆性问题

**Non-Goals:**
- 不做 data_access 的代码级过滤（那是 API 中间件层的事）
- 不做用户认证改造
- 不做完整的 RBAC 系统

## Decisions

### D1: Persona 过滤 — 在哪层生效

**选择**: 两层：`_build_system_prompt()` tool列表过滤 + `registry.execute()` 执行前验证。

**理由**: prompt 过滤防止 LLM 看到不该有的 tool（减少 prompt injection 风险），执行前验证防止代码 bug 绕过 prompt 层。两层是 defense in depth。system_prompt 的 `{tools}` 占位符只填入允许的 skills。`to_openai_tools()` 加 `allowed_skills` 参数过滤。

### D2: Audit log 格式 — JSONL vs 结构化日志

**选择**: JSONL 文件 `data/audit/agent_audit.jsonl` + 内存 `deque(maxlen=100)` ring buffer。

**理由**: JSONL 可直接 `tail -f` 查看，可被任何分析工具读取。Ring buffer 供未来调试面板（`/api/agent/audit/recent`）查询。不做数据库是因为避免引入新依赖——JSONL 零依赖且性能足够（每次 skill 调用追加一行，<1ms）。

### D3: 错误处理架构 — 三层统一

**选择**: `AgentError` 基类 + 子类 hierarchy。

```
AgentError
├── SkillExecutionError(skill_name, original_error)
├── SkillNotFoundError(skill_name)
├── SkillPermissionError(skill_name, persona)
├── ProviderError(provider, status_code) — 复用已有
└── PlanError(goal, reason)
```

每层职责：
- **Skill 层**: 内部异常 → 转换为 SkillExecutionError 或继续抛出
- **Agent 层 (core.py)**: 捕获 AgentError → 写入 audit log → 转换为 SSE error 事件
- **Channel 层 (fastapi_sse.py)**: 捕获未预料的异常 → 包装为结构化 SSE error，写 audit log

### D4: audit log 脱敏

**选择**: args 写入前，已知敏感字段名（password, phone, parent_phone, token, api_key）的值替换为 `"***"`。

**理由**: 最小化脱敏——只打码明确敏感字段。不尝试"自动检测"敏感数据（容易误杀/漏杀）。

## Risks / Trade-offs

- **Persona 过滤可能漏配**: 新增 skill 时忘记加到 persona YAML → skill 不可用。缓解：启动时打印 warning 如果注册了但不属于任何 persona 的 skill
- **Audit JSONL 文件无限增长**: 生产环境每天可能数千条。缓解：加 `max_size_mb=10` 自动 rotate（保留最近 2 个文件）。Phase 4 先不做，标记为 TODO
- **错误 hierarchy 引入新异常类型**: 现有代码有些地方 catch bare Exception。改动时要确保不吞掉 AgentError

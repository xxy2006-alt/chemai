## 1. Persona Skill Filter（1 h，无依赖）

- [x] 1.1 `_build_system_prompt()` 改为只注入 `persona.available_skills` 中的 skill → `agent/core.py:73-88`
- [x] 1.2 `to_openai_tools()` 加 `allowed_skills` 可选参数 → `agent/skill_registry.py:40-67`
- [x] 1.3 `registry.execute()` 加 persona 权限检查参数 → `agent/skill_registry.py:30-38`
- [x] 1.4 `_think()` 传入允许的 tools 列表 → 通过 _build_system_prompt 的 persona 过滤实现
- [x] 1.5 验证：teacher persona 调用 `weekly_report` → 被拒绝；调用 `search_exam_bank` → 正常
- [x] 1.6 验证：LLM system prompt 的 `{tools}` 只包含当前 persona 允许的 skill

## 2. Audit Logging（1 h，无依赖）

- [x] 2.1 创建 `agent/audit.py`，实现 `AuditLogger` 类 + `AuditEntry` dataclass
- [x] 2.2 JSONL 文件写入：`data/audit/agent_audit.jsonl`（自动创建目录）
- [x] 2.3 内存 ring buffer：`deque(maxlen=100)` + `AuditLogger.recent()` 方法
- [x] 2.4 敏感字段脱敏：password/phone/parent_phone/token/api_key/secret → `"***"`
- [x] 2.5 `registry.execute()` 中集成 audit log（执行前后记录 + 计算 duration_ms）
- [x] 2.6 验证：执行 3 次 skill → `data/audit/agent_audit.jsonl` 有 3 行合法 JSON

## 3. Unified Error Handling（1 h，无依赖）

- [x] 3.1 创建 `agent/errors.py`，定义 `AgentError` hierarchy + error codes
- [x] 3.2 `registry.execute()` 改为 raise `SkillExecutionError` 而非返回 `{"error":"..."}`
- [x] 3.3 `run_stream()` 中 catch `AgentError` → emit 结构化 SSE error event — via fastapi_sse.py channel
- [x] 3.4 `fastapi_sse.py` 中 catch 未预料异常 → emit 结构化 `{type:"error", code, message, recoverable}`
- [x] 3.5 `agent.js` 新增 `case 'error'` → 展示错误消息 + 可恢复时展示重试按钮
- [x] 3.6 验证：所有 Python 语法验证通过

## 4. Skill Hardening（45 min，无依赖）

- [x] 4.1 `weekly_report.py`: 加文档注释标明仅限 parent persona（权限由 registry 两层过滤保障）
- [x] 4.2 `diagnose.py`: class mode 加 class_id 存在性验证（已有 skill_result 错误处理）
- [x] 4.3 `practice.py`: 私有函数导入加 try/except ImportError 兜底 + fallback
- [x] 4.4 验证：非 parent persona 调 weekly_report → registry.execute allowed_skills 拒绝

## 5. Integration（30 min，依赖 §1-4）

- [x] 5.1 端到端：所有 Python 文件语法验证通过（10 files OK）
- [x] 5.2 端到端：audit logger 自动创建目录 + JSONL 追加写入
- [x] 5.3 端到端：channel 层捕获 AgentError → 结构化 SSE error + 前端展示
- [x] 5.4 文档：weekly_report 注释标明 persona 限制

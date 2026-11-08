## Context

ChemAI 的 LangGraph ReAct agent 当前 system prompt 结构：persona YAML system_prompt + 学生信息 + 分类器 hints + 14 条硬编码行为规则。LLM 看到的是合规清单，不理解产品全貌。`agent/langgraph_agent.py` 的 `build_persona_prompt()` (line 90-130) 负责拼装 prompt。

本次改动不涉及 LangGraph 架构、工具签名、SSE adapter、channel 端点。

## Goals / Non-Goals

**Goals:**
- 将 system prompt 从规则清单重构为四层结构化上下文，让 agent 理解产品心智模型
- 统一工具描述为单源真相（docstring 即描述），消除 prompt 文本与 LangChain tool binding 双路径冲突
- 用 GuardState `check_prerequisites()` 将"信息不足时反问"从 prompt 建议升级为结构性 gate
- 扩展 eval 覆盖：over-calling 检测、persona 交叉验证、route action 完整性

**Non-Goals:**
- 不改 ReAct loop（不做 planning step — 那是单独 change）
- 不改 tool 函数签名
- 不改 LangGraph graph 结构
- 不加 A/B testing 基础设施（DevOps scope）

## Decisions

### D1: 工具描述单源真相 — docstring 即描述

**选择**: 将 11 个 tool 的 docstring 改写为 When/What/Next 格式，`_build_tool_context()` 从 `StructuredTool.description` 直接读取。不做并行 TOOL_META dict。

**理由**: LangChain `create_react_agent` 将 `StructuredTool.description` 作为 tool schema 传给 LLM。如果另建 TOOL_META dict 并在 prompt [TOOLS] 段注入不同内容，LLM 接收两套描述 → 行为不可预测。docstring 做单源真相，LLM 在 prompt 和 tool binding 看到的是一致的。

**替代方案被拒绝**:
- TOOL_META + 原 docstring：双路径冲突（Eng review Finding 1/6）
- `_make_guarded_tool()` 覆盖 `base_tool.description`：可行但增加间接层，docstring 改写更直接

### D2: Structural missing_info gate

**选择**: `GuardState` 新增 `check_prerequisites(name, kwargs) -> str|None`，配合 `TOOL_PREREQUISITES: dict[str, list[str]]` 在工具执行前检查必要字段。缺失时返回 error 而非执行工具。

**理由**: CEO review 指出 REASONING 段的"信息够吗？"是 prompt 装饰——LLM 在 tool-calling flow 中不会做元认知。结构性 gate 把"反问"变成代码保证。LLM 仍然可以选择调不调工具，但调了就必须满足前置条件。

**TOOL_PREREQUISITES 内容**:
- `generate_questions`: `["knowledge_points"]`
- `diagnose_barrier`: `["student_id_or_class_id"]`（student_id/student_name/class_id 任意一个非空）
- `weekly_report`: `["student_id_or_class_id"]`
- `assign_adaptive_practice`: `["student_id_or_class_id"]`

### D3: Prompt section order — REASONING before TOOLS

**选择**: PRODUCT → ROLE → PROFILE → HINTS → REASONING → TOOLS

**理由**: Eng review 指出 TOOLS 段最长（~2000 tokens），放在中间有"lost in the middle"风险。放在最后利用 recency bias 让 LLM 在选择工具时注意力集中在工具描述上。REASONING 放在 TOOLS 之前，让自检问题在工具描述之前被处理。

### D4: request_approval 不出现在 [TOOLS] 段

**选择**: `_build_tool_context()` 跳过 `request_approval`（其 docstring 不含 When/What/Next 格式 → 自动跳过并 log warning）。

**理由**: `request_approval` 是内部护栏工具，不是用户面向的功能。在 [TOOLS] 段展示它会误导 LLM 把它当作普通工具。`get_tools_for_persona()` 仍然注册它（LLM 可以调），只是不在 prompt 里展示。

### D5: Persona YAML 清理策略

每个 persona YAML 的 system_prompt 保留角色定位文本，删除工具映射类内容：

- `tutor.yaml`: 保留"引导式教学，不直接给答案，分步讲解"，删除工具映射 bullet list
- `teacher.yaml`: 保留"班级管理、教学计划"上下文，删除工具映射
- `parent.yaml`: 保留角色描述，删除 JSON 决策格式指令

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| 去掉显式规则后 agent 工具选择变差 | Tool docstring "何时用"比旧规则更具体。Evals gate |
| Prompt 更长 → 首 token 延迟增加 | 净增 ~500 tokens（+Product -规则），TOOLS 段结构紧凑 |
| check_prerequisites 误拦合理调用 | 只对 4 个工具设前置条件，其余工具不受影响 |
| Persona YAML 清理破坏现有行为 | 仅删工具映射文字，保留角色定位。Evals 验证 |

## Why

ChemAI 的 LangGraph agent 行为不智能——用户说"根据高考真题出变种题"，agent 不反问知识点/难度/数量就直接搜题出题，出完不保存到题库也不跳转考试工作台。根因是 LLM 缺少产品心智模型：system prompt 里塞了 14 条行为规则，但没告诉它 ChemAI 是什么、工具有什么用、用户的完整旅程是怎样的。Agent 退化成了规则引擎，不是自主推理的 ReAct agent。

## What Changes

- **System prompt 重构**：从"14 条规则清单"改为四层结构化上下文（PRODUCT/ROLE/TOOLS/REASONING），去掉硬编码行为规则段
- **工具描述统一**：11 个 tool 的 docstring 全部改写为"何时用 / 会发生什么 / 下一步"格式，由 `_build_tool_context()` 从 `StructuredTool.description` 直接读取——单源真相，避免双路径冲突
- **结构性反问 gate**：`GuardState` 新增 `check_prerequisites()` 方法和 `TOOL_PREREQUISITES` 字典，工具执行前检查必要字段（如 generate_questions 必须 knowledge_points），缺失时自动 block 并返回"请先向用户确认"
- **Evals 扩展**：新增 5 个 workflow 场景（over-calling 检测、persona 交叉验证、route action 完整性、missing_info gate 测试）
- **LangGraph 架构零改动**：`create_react_agent`、`MemorySaver`、interrupt/resume、SSE adapter、channel 端点全部不变

## Capabilities

### New Capabilities
- `structured-prompt`: 四层 prompt 组装（PRODUCT/ROLE/TOOLS/REASONING），`build_persona_prompt()` 拆分为 4 个独立 section builder，prompt 段顺序为 PRODUCT→ROLE→PROFILE→HINTS→REASONING→TOOLS
- `tool-prerequisites`: GuardState 结构性前置条件检查，`TOOL_PREREQUISITES` 字典定义每个工具的必填上下文字段，`check_prerequisites()` 在工具执行前 block 缺失字段的调用
- `tool-docstring-context`: 工具 docstring 统一为"模块名 — 功能 / 何时用 / 会发生什么 / 下一步"三段式格式，`_build_tool_context()` 从 `StructuredTool.description` 自动读取并组装 [TOOLS] 段

### Modified Capabilities
<!-- No existing specs to modify. All caps are new. -->

## Impact

- `agent/langgraph_agent.py` — `build_persona_prompt()` 拆分 + GuardState 扩展 + 规则段移除（~120 行变更）
- `agent/tools.py` — 11 个 tool docstring 改写 + `TOOL_PREREQUISITES` 注册（~120 行变更）
- `evals/agent_eval_golden.yaml` — 新增 5 个 workflow 场景（~80 行追加）
- `evals/test_langgraph_agent.py` — 回归测试补 trajectory order 比较（~20 行）
- `agent/channel/langgraph_channel.py` — 不变
- `agent/langgraph_sse.py` — 不变

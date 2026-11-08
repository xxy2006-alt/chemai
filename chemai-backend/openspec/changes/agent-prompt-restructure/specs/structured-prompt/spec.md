## ADDED Requirements

### Requirement: System prompt has four structured sections
系统 SHALL 将 system prompt 组装为四个结构化段：[PRODUCT]、[ROLE]、[TOOLS]、[REASONING]。硬编码的 14 条行为规则段 SHALL 被移除。

#### Scenario: Prompt assembly includes all four sections
- **WHEN** `build_persona_prompt("tutor")` 被调用
- **THEN** 返回的 prompt 包含 `[PRODUCT]` 段、`[ROLE]` 段、`[TOOLS]` 段、`[REASONING]` 段
- **AND** 不包含原硬编码规则段（"## 行为规则（必须遵守）"）

#### Scenario: PRODUCT section is persona-independent
- **WHEN** 使用不同 persona（tutor、teacher、parent）调用 prompt builder
- **THEN** 每个 persona 的 [PRODUCT] 段内容完全相同

#### Scenario: ROLE section is persona-specific
- **WHEN** persona="teacher" 调用 prompt builder
- **THEN** [ROLE] 段包含教师视角内容（班级管理、诊断）
- **WHEN** persona="tutor" 调用 prompt builder
- **THEN** [ROLE] 段包含辅导视角内容（引导式教学）

### Requirement: Tool context auto-assembled from docstrings
系统 SHALL 通过 `_build_tool_context(tools)` 从每个 `StructuredTool.description` 读取工具描述，自动组装 [TOOLS] 段。每个工具的描述格式为：模块名 — 功能 / 何时用 / 会发生什么 / 下一步。

#### Scenario: Tool context includes all persona tools
- **WHEN** persona="teacher" 的工具列表包含 generate_questions、diagnose_barrier、assign_adaptive_practice 等
- **THEN** [TOOLS] 段包含这些工具的 When/What/Next 描述
- **AND** 不包含 persona YAML 中未列出的工具（如 teacher 不应有 simulate_experiment）

#### Scenario: request_approval is excluded from TOOLS section
- **WHEN** 工具列表包含 request_approval（内部护栏工具）
- **THEN** [TOOLS] 段不包含 request_approval 条目
- **AND** request_approval 仍注册为可用工具（LLM 可调用）

### Requirement: Prompt section order is PRODUCT→ROLE→HINTS→REASONING→TOOLS
系统 SHALL 按固定顺序排列 prompt 段：[PRODUCT] → [ROLE] → [PROFILE]（如有学生）→ [HINTS]（如有分类器推荐）→ [REASONING] → [TOOLS]。

#### Scenario: REASONING appears before TOOLS
- **WHEN** prompt 被组装
- **THEN** [REASONING] 段在 [TOOLS] 段之前
- **AND** [TOOLS] 段是 system prompt 的最后一段

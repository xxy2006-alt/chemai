## ADDED Requirements

### Requirement: Tool docstrings follow three-part format
每个工具的 docstring SHALL 采用"模块名 — 功能描述 / 何时用 / 会发生什么 / 下一步"三段式格式。Docstring 是工具描述的唯一来源（单源真相）。

#### Scenario: Docstring contains all three parts
- **WHEN** 读取 `generate_questions` 的 docstring
- **THEN** docstring 第一行包含模块名和功能描述（如"考试工作台 — 生成高中化学选择题"）
- **AND** 包含"何时用："段描述触发场景
- **AND** 包含"会发生什么："段描述用户可见的副作用
- **AND** 包含"下一步："段描述典型后续操作

#### Scenario: Docstring matches LangChain tool description
- **WHEN** `StructuredTool.description` 被 LangChain 绑定为 tool schema
- **THEN** LLM 在 tool binding 中看到的描述与 system prompt [TOOLS] 段的内容一致
- **AND** 不存在内容冲突或信息差异

### Requirement: _build_tool_context reads from StructuredTool.description
系统 SHALL 通过 `_build_tool_context(tools)` 遍历工具列表，对每个工具读取 `StructuredTool.description` 并格式化为 [TOOLS] 段的条目。工具描述不符合三段式格式的 SHALL 被跳过并 log warning。

#### Scenario: Valid tool description is included
- **WHEN** 工具的 description 包含"何时用："关键字
- **THEN** 该工具的条目出现在 [TOOLS] 段

#### Scenario: Invalid tool description is skipped
- **WHEN** 工具的 description 不包含"何时用："关键字（如 request_approval）
- **THEN** 该工具不出现在 [TOOLS] 段
- **AND** 系统 log 一条 warning 信息

### Requirement: All 11 production tools have updated docstrings
所有注册在 `TOOLS` 列表中的工具函数 SHALL 拥有符合三段式格式的 docstring。包括：search_exam_bank、web_search、generate_questions、diagnose_barrier、chemistry_tutor、simulate_experiment、balance_equation、weekly_report、import_exam_paper、assign_adaptive_practice、save_to_bank。

#### Scenario: Every tool in TOOLS has three-part docstring
- **WHEN** 遍历 `TOOLS` 列表中的每个函数
- **THEN** 每个函数的 `__doc__` 包含"何时用："、"会发生什么："、"下一步："三个关键字

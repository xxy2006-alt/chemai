## Why

现有 `chemical_balance.py`、`exam_bank.py` 等业务代码已经可用，需要封装为 Agent Skill 格式（`@registry.register()`），让 ChemAgent 能通过 function calling 自动调用。

## What Changes

- `agent/skills/balance.py` — 封装 chemical_balance.audit_chemical_equation
- `agent/skills/search.py` — 封装 exam_bank.search_questions
- `agent/skills/diagnose.py` — 学生障碍诊断（DB + LLM）
- `agent/skills/generate.py` — AI 出题（LLM 生成 + 自动审核）

## Capabilities

### New Capabilities
- `skills-balance`: 方程式配平审核 Skill
- `skills-search`: 真题搜索 Skill
- `skills-diagnose`: 障碍诊断 Skill
- `skills-generate`: AI 出题 Skill

## Impact

零新逻辑，纯适配现有代码。不修改 `app/services/` 下任何文件。

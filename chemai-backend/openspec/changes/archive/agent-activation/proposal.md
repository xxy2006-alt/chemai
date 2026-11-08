# Proposal: agent-activation

## Summary

激活 Hermes Agent 的 6 个 Chemistry Skills，使其能真正调用后端服务，并通过 Agent 决策链完成端到端的教学任务。

## Motivation

Product Spec v2.0 将 ChemAI 定位为 "AI Agent 驱动的智能教学工具"，而非传统 SaaS。当前：
- 6 个 Skill 代码已在 `hermes_skills/` 下，但 handler 未联通到 `app/services/*`
- Hermes proxy 路由 (`app/api/hermes_proxy.py`) 存在但未激活
- Agent 决策循环（观察 → 思考 → 规划 → 执行 → 反馈）未跑通

## Scope

- `hermes_skills/chemistry_exam/handler.py` — 联通出题+审核服务
- `hermes_skills/chemistry_diagnosis/handler.py` — 联通诊断服务
- `hermes_skills/chemistry_parser/handler.py` — 联通 MinerU 解析
- `hermes_skills/chemistry_memory/handler.py` — 联通学情记忆
- `app/api/hermes_proxy.py` — Agent 任务调度
- `app/mcp/` — MCP 工具注册

## Dependencies

依赖 `infra-foundation`, `mineru-pipeline`, `adaptive-diagnosis-engine` 的前期产出

## Acceptance

- [ ] 每个 Skill 的 handler.py 至少有一个函数联通到真实 service
- [ ] 通过 `/api/hermes/chat` 发送自然语言指令能触发正确的 Skill 调度
- [ ] Agent 能完成至少 1 条端到端决策链（如"帮我出一份试卷"）

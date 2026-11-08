# ADR-0012: 业务逻辑住在 service module——agent 工具与 chem_skills 一律为 adapter

**Date**: 2026-09-12
**Status**: Accepted（grilling 定案）

## Context

架构评审（2026-09-12）发现智能体业务闭环的五处断点，根因同一：Agent 需要的每个业务动作（布置练习、判卷、通知）都在「agent 工具层」被手抄了一份缺胳膊少腿的平行实现，而真正完整的实现躺在 REST 层无人调用：

- `assign_adaptive_practice`（agent/tools/diagnosis.py:596）调 LLM 生成题目后不解析不落库，聊天卡片却显示「已布置」；完整落库的 `POST /api/practice/assign` 前端零调用。
- `save_grading_results` 的落库逻辑住在 agent 工具文件里，HTTP 保存端点反向调用工具函数（依赖倒置）。
- `chem_skills/` 下 4 个 skill（exam / diagnosis / notification / improvement）从未被接线，与进程内 service 各自漂移。

## Decision

1. **业务逻辑的唯一家园是进程内 service module**（`app/services/`）。ZPD 计算、LLM 生成与解析、落库、批次切分、幂等——这些是 service 的 implementation。
2. **Agent 工具是 service 之上的薄 adapter**：保留工具名与 docstring（LLM 看到的 interface 不变），implementation 缩为「调 service + 结果转 JSON」。工具不持有业务逻辑、不直接开 db session 写业务表。
3. **chem_skills 是 service 的 HTTP 客户端包装**（外部复用层），不承载逻辑；接线时只允许 `handler.py → REST → service` 单向依赖。
4. **REST 路由同为薄 adapter**。禁止 HTTP 端点调用 agent 工具函数（消灭 ocr_sheets.py → agent/tools 的反向依赖）。

## Consequences

- Positive：单一实现，agent / REST / 定时任务 / skill 四类调用方零漂移；service interface 即测试面。
- Positive：审批（guard）、权限（PermissionChecker）、事务边界各归各层，不再互相穿透。
- Negative：service interface 的任何变更要同步检查四类调用方——用测试钉住（service 层单测 + 工具层薄壳测试）。
- Negative：在工具里「顺手」内联一段逻辑会非常诱人（历史上已发生 4 次）——review 时把「工具文件里出现 db.add / LLM 生成调用」视为红线。

## Alternatives Considered

- **逻辑住 chem_skills handler**：handler 是 HTTP 客户端形态（base_handler.post 调 REST），会造成 REST→skill→REST 回环；4 个未接线 skill 已示范漂移。否决。
- **逻辑留在 API 文件里就地抽函数**：scheduler / 组卷页接入时依赖 API 模块，service 无家。否决。

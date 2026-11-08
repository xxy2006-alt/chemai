## Context

现状（详见 proposal.md — Why）：
- `app/services/exam_bank.py` 的 `ExamBankService` 只管历史真题库（启动时从 JSON 加载进内存，`exam_bank_service = ExamBankService()` 模块级单例）。
- AI 生成题库（QuestionSet/Question/QuestionSetItem，SQLite）的持久化逻辑被内联在 `app/api/exam_bank.py` 与 `agent/tools/exam_bank.py` 两处，行为已漂移。
- 向量检索（`VectorSearchService`，Chroma 持久化于 `./data/chromadb`）能索引 AI 生成的题，但 `search_questions` 只在带 keyword 时走向量兜底 → known_gap：不带 keyword 或重启后搜不到自己保存的题。
- 约束：HTTP 契约被前端依赖，不能变；模块级单例是既有惯例；`Question.content` 无索引（去重查询为表级扫描，数据量级小可接受）。

## Goals / Non-Goals

**Goals:**
- 题库持久化收敛到单一服务 `QuestionBankService`，两个适配层变薄。
- 统一行为基线：content 去重、is_system 删除守卫、保存即同步（向量 + 历史）。
- 关闭 known_gap：保存的题（带/不带 keyword）可被搜索命中。
- 删除无引用的死代码 `agent/tools_core.py`。

**Non-Goals:**
- 不改变 HTTP 路由/参数/返回结构（前端无感知）。
- 不重构 `ExamBankService`（历史真题库）本身，仅作为 `QuestionBankService` 的依赖被调用。
- 不纳入 `format-questions`（LLM 文本格式化）——不同职责，无重复无漂移。
- 不合并 v1/v2 的 agent/SSE 双轨（独立问题，不在本 change 内）。

## Decisions

### D1. 独立 `QuestionBankService` 新文件，而非并入 `ExamBankService`
- **选**：新建 `app/services/question_bank.py`，类 `QuestionBankService`，导出单例 `question_bank_service`，在 `app/services/__init__.py` 注册。
- **理由**：CONTEXT.md 中"历史真题(Exam Paper)"与"AI题库(Question Set)"是两个独立领域概念，合并会让 ExamBankService 职责爆炸；新文件出生即用对名字，顺带推进命名对齐。
- **替代**：并入现有 exam_bank.py —— 被否：一个文件两个概念继续混居。

### D2. 服务拥有保存副作用（向量索引 + 历史真题库同步）
- **选**：`QuestionBankService.add_questions` 内部串起「写 QuestionSet + `VectorSearchService.index_questions(mode="append")` + `ExamBankService.add_question`」三步。
- **理由**：这是"深模块"的核心——一个 save = 三个一致副作用；否则 API 路径继续"存了搜不到"。依赖通过模块级单例引用，符合惯例。
- **替代**：调用方各自加副作用 —— 被否：漂移照旧。

### D3. 行为基线统一为更严格的一侧
- content 去重（沿用 API 实现，`Question.content == 新content` 查重复用）。
- is_system 删除守卫（沿用 API 实现，Agent 删除时同样拒绝系统题库）。
- **理由**：更安全；已是有意的既有实现，Agent 侧是缺漏。

### D4. HTTP 表面不变，内部改为委托
- `create_exam_set` / `get_exam_sets` / `import_questions_to_set` / `delete_exam_set` 改为调 `QuestionBankService`；`papers` / `historical` 继续调 `ExamBankService`。
- **理由**：候选目标是消除双份真相，不是重设计 HTTP 契约；改契约需前端行为确认，另立决定。

### D5. Agent 工具仅薄包装 QuestionSet 三个函数
- `save_to_bank` / `list_banks` / `delete_bank` 变薄包装：工具签名 + LLM 返回 JSON 格式化，核心调服务。
- `search_exam_bank` / `web_search` / `_do_web_search` / `show_exam_workbench` 不动（真题检索的 Agent 界面、外部 HTTP、UI 渲染）。

### D6. known_gap 捆绑：搜索联合历史 + AI 题库
- `QuestionBankService` 提供 `search_ai_generated()`（查 SQLite QuestionSet/Question）；Agent `search_exam_bank` 联合 `ExamBankService.search_questions` 与 `search_ai_generated` 返回，并标注来源。
- **理由**：深模块的验收标准就是"保存即搜到"；不带 keyword 也能命中 AI 题库（绕过当前"仅带 keyword 走向量"的缺口）。

### D7. 死代码删除
- `agent/tools_core.py` 删除前先 diff `agent/tools/*` 确认无独有函数（已核对 25 个函数均有副本，删除前再跑一次 `grep -rn "tools_core" --include="*.py"` 确认零引用）。

## Risks / Trade-offs

- **行为收紧影响现有测试/前端** → 回归防线：新增 save→search 集成测试；`pytest` + `ruff check .` 全绿；`evals --workflow` 覆盖 Agent 对话级行为（save_to_bank → 跳转题库 tab）。
- **去重查询无索引（表级扫描）** → AI 生成题量级小，可接受；如需规模化，后续为 `Question.content` 加普通索引（不在本 change 内）。
- **API 导入开始同步向量/历史，可能影响既有数据** → 同步操作幂等：向量 `index_questions(mode="append")`、历史 `add_question`（按 exam_id 覆盖更新）。
- **`QuestionBankService` 模块级单例在 import 时初始化**（与 `ExamBankService` 一致）→ 若后续想懒加载，可单独重构，不影响本 change 行为。

## Migration Plan

- 无数据库 schema 变更、无配置变更。
- 实现顺序：先建 `QuestionBankService` 并补齐集成测试 → 改 API 委托 → 改 Agent 工具薄包装 → 改搜索联合 → 删 `tools_core.py` → 全量回归。
- 回滚：单 PR 原子变更；若行为收紧引发问题，可先回滚 API/Agent 委托层（服务层保留）。

## Open Questions

- `Question.content` 是否在本次加索引：不阻塞验收，可后置。
- 前端 `format-questions` 与 `papers`/`historical` 端点是否有未使用项：不影响本 change，另立候选。

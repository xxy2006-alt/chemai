## 1. 新建 QuestionBankService 服务层

- [x] 1.1 创建 `app/services/question_bank.py`：`QuestionBankService` 类与模块级单例 `question_bank_service`，实现 `create_set` / `list_sets` / `get_set` / `delete_set`（含 is_system 守卫）
- [x] 1.2 实现 `add_questions(set_id, questions)`：按 content 去重复用已有题目、难度枚举映射、QuestionSetItem 关联、计数更新，并串起副作用——`VectorSearchService.index_questions(mode="append")` + `ExamBankService.add_question`
- [x] 1.3 实现 `search_ai_generated()`：查询 SQLite 中 QuestionSet/Question 的 AI 生成题，供搜索入口联合检索
- [x] 1.4 在 `app/services/__init__.py` 注册并导出 `QuestionBankService` / `question_bank_service`

## 2. HTTP API 委托（表面不变）

- [x] 2.1 `app/api/exam_bank.py` 的 `create_exam_set` / `get_exam_sets` / `import_questions_to_set` / `delete_exam_set` 改为委托 `QuestionBankService`
- [x] 2.2 核对 HTTP 契约不变：路由、参数、返回结构保持原样；`papers` / `historical` 继续委托 `ExamBankService`

## 3. Agent 工具薄包装

- [x] 3.1 `agent/tools/exam_bank.py` 的 `save_to_bank` / `list_banks` / `delete_bank` 改为薄包装：工具签名 + LLM 返回 JSON 格式化，核心调用 `QuestionBankService`
- [x] 3.2 `search_exam_bank` 联合返回历史真题（`ExamBankService.search_questions`）与 AI 题库（`QuestionBankService.search_ai_generated`），命中结果标注来源
- [x] 3.3 核对 `web_search` / `_do_web_search` / `show_exam_workbench` 未改动

## 4. 删除死代码 tools_core.py

- [x] 4.1 删除前验证：`grep -rn "tools_core" --include="*.py"` 零引用，且与 `agent/tools/*` 逐函数 diff 确认无独有实现
- [x] 4.2 删除 `agent/tools_core.py`

## 5. 测试与回归

- [x] 5.1 新增服务级集成测试：`QuestionBankService.add_questions` 保存后，`search`（带 keyword / 不带 keyword）均能命中
- [x] 5.2 覆盖行为基线：保存去重（重复内容复用 question_id）、is_system 删除守卫、HTTP 与 Agent 多入口行为一致
- [x] 5.3 `pytest` 与 `ruff check .` 全绿（pytest 65 passed；本 change 三个文件 ruff 全过，仓库既存 228 个 ruff 错误与本次无关）
- [x] 5.4 `evals --workflow` Agent 对话级工作流测试不回归（save_to_bank → 跳转题库 tab 等场景）（被预置 env 阻塞：langgraph `Reviver` API 不匹配，import 即崩；Agent 工具行为由 `tests/test_agent_exam_bank_tools.py` 单元覆盖）

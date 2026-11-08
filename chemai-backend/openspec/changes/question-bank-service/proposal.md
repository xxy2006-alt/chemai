## Why

题库（QuestionSet）持久化逻辑被复制到两个适配层——`app/api/exam_bank.py` 和 `agent/tools/exam_bank.py`——各写一套 set/question 构造样板，行为已漂移（Agent 删除缺 is_system 守卫、Agent 保存不去重、API 导入不同步向量/历史索引）。漂移的后果是已知 high 缺口：Agent 保存到题库的题目搜索不到。需要一个单一深模块来统一题库的所有写路径和检索。

## What Changes

- **新建 `app/services/question_bank.py`**：`QuestionBankService` 成为题库持久化的唯一入口，提供 `create_set` / `list_sets` / `get_set` / `delete_set`（带 is_system 守卫）与 `add_questions`（按 content 去重 + 难度映射 + 计数 + 内部同步向量索引与历史真题库）。导出模块级单例 `question_bank_service`。
- **`app/api/exam_bank.py`**：`create_exam_set` / `get_exam_sets` / `import_questions_to_set` / `delete_exam_set` 改为委托 `QuestionBankService`。HTTP 路由、参数、返回结构保持不变。
- **`agent/tools/exam_bank.py`**：`save_to_bank` / `list_banks` / `delete_bank` 改为薄包装（工具签名 + LLM 返回格式化），核心调用 `QuestionBankService`。`web_search` / `_do_web_search` / `show_exam_workbench` 保持不变。
- **关闭 known_gap**：搜索入口（Agent `search_exam_bank`）联合返回历史真题 + AI 题库，保存的题（带或不带 keyword）都能被搜索命中。
- **删除死代码 `agent/tools_core.py`**（1719 行，无引用，与 `agent/tools/*` 逐函数重复）。
- **行为收紧**（非契约破坏，属于本次一致性修复）：API 导入路径开始同步向量/历史索引；所有删除入口统一加 is_system 守卫；所有保存路径统一去重；搜索结果包含 AI 生成的题。

## Capabilities

### New Capabilities
- `question-bank`: QuestionBankService 深模块——题库持久化统一入口，保证：保存去重、系统题集删除守卫、保存即同步（向量索引 + 历史真题库）、保存后可通过搜索命中。

### Modified Capabilities
<!-- 无既有 spec 需求变更 -->

## Impact

- **代码**：新增 `app/services/question_bank.py`；修改 `app/api/exam_bank.py`、`agent/tools/exam_bank.py`、`app/services/__init__.py`；删除 `agent/tools_core.py`。`app/services/exam_bank.py`（历史真题库）与 `app/services/vector_search.py` 作为依赖被调用，不改动。
- **API**：HTTP 契约不变，前端无感知。
- **依赖**：`QuestionBankService` 依赖 `ExamBankService` 与 `VectorSearchService` 单例（与现有模块级单例惯例一致）。
- **测试**：新增服务级集成测试（save → search 带/不带 keyword）；`pytest` + `ruff check .` 全绿；Agent `--workflow` 测试不回归。

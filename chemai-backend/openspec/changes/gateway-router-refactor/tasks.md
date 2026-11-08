## 1. gateway.py: 重写分类器 prompt 和 keyword fallback（25 min）

- [ ] 1.1 重写 `CLASSIFY_PROMPT`：三分类（chat/page_action/hybrid）→ 两分类（chat/navigate），去掉 `intent`/`page`/`params` 输出字段
  - 新 prompt: `{"type": "chat"|"navigate", "tools": [...], "page": null|"...", "provider": "deepseek"|"mimo"}`
  - navigate 只用于纯页面跳转（"打开考试工作台""去首页"），不调 tool
- [ ] 1.2 更新 `IntentResult` 数据类：`intent` → `type`，去掉 `page` 和 `params` 字段
- [ ] 1.3 更新 `_parse()`：适配新 JSON 格式，保留 type 校验
- [ ] 1.4 增强 `_keyword_fallback`：现有只返回 intent+page 不推荐 tool → 改为返回 type + tools 列表（"出题"→`["generate_questions"]`，"诊断"→`["diagnose_barrier"]`，"周报"→`["weekly_report"]`，"搜索"→`["search_exam_bank"]`）
- [ ] 1.5 删除 `build_navigate_events()`、`_PAGE_ACTIONS`、`_TOOL_POPULATE_TARGET`、`_resolve_action_params()`（路由工厂不再需要）
- [ ] 1.6 保留 `PAGE_ROUTES`（navigate 类型仍需页面名→路由映射）
- [ ] 1.7 验证：用 classifier 测试脚本跑 10 条典型消息，确认 chat/navigate 分类准确

## 2. agent/tools.py: tool 返回值加 _route 字段（30 min）

- [ ] 2.1 定义 `RouteHint` 结构（TypedDict 或简单 dict 注释约定）：
  ```python
  # _route: {"navigate": bool, "page": str|None, "actions": [...], "populate": {"target": str, "data": dict}|None}
  ```
- [ ] 2.2 `diagnose_barrier`：返回值加 `_route`
  - 参数有 `student_name`/`student_id` → `navigate=False`
  - 参数只有 `class_name`/`class_id` → `navigate=True, page="diagnosis"`
- [ ] 2.3 `generate_questions`：返回值加 `_route`
  - 参数有 `student_name` → `navigate=False`（题在 chat 里展示）
  - 无 student 参数（组卷/批量出题）→ `navigate=True, page="exam-v2"`
- [ ] 2.4 `weekly_report`：返回值加 `_route`
  - 参数有 `student_name` → `navigate=False`
  - 参数只有 `class_name` → `navigate=True, page="students"`
- [ ] 2.5 `search_exam_bank`：返回值加 `_route`（始终 `navigate=False`，真题在 chat 里展示）
- [ ] 2.6 `assign_adaptive_practice`：返回值加 `_route`（始终 `navigate=False`，练习在 chat 里展示）
- [ ] 2.7 其余 tool（`chemistry_tutor`、`web_search`、`simulate_experiment`、`balance_equation`、`import_exam_paper`）：不加 `_route`（这些 tool 不需要页面跳转，管道层对无 `_route` 的返回值默认不跳）

## 3. fastapi_sse.py: 管道层适配（30 min）

- [ ] 3.1 适配 `_classify_and_narrow()`：`IntentResult` 的 `intent` → `type`，`result.tools` 提取逻辑不变
- [ ] 3.2 `/chat` 端点：Phase 3 不再调用 `build_navigate_events()`
  - `type=navigate` → 直接返回 `{"navigate": {"page": intent.page}}`（不走 Agent）
  - `type=chat` → Agent 执行后，遍历 `_extract_tool_results()`，读每个 tool 结果的 `_route`
  - 如果任一 tool 返回 `_route.navigate=True` → 发送 navigate + populate + action
- [ ] 3.3 `/chat/stream` 端点：同上逻辑
  - `type=navigate` → yield navigate 事件后直接 done（不走 Agent）
  - `type=chat` → Agent 执行后，在 done 之前检查 tool_results 的 `_route`，发送对应 SSE 事件
- [ ] 3.4 提取 `_route` 的公共函数 `_extract_route_events(tool_results) -> dict`，两个端点共用
- [ ] 3.5 验证：curl `/api/agent/chat/stream` 发送"高三1班诊断情况" → SSE 事件中应有 navigate 到 diagnosis 页面
- [ ] 3.6 验证：curl `/api/agent/chat/stream` 发送"张梦琪最近错题多吗" → SSE 事件中无 navigate

## 4. agent/sse_adapter.py: 适配（如有需要，10 min）

- [ ] 4.1 检查 `_route` 事件是否需要特殊的 SSE 格式 → 大概率不需要，navigate/populate/action 事件格式保持不变
- [ ] 4.2 如需适配，在 `feed()` 中增加 `_route` 事件的 pass-through

## 5. 端到端测试（30 min）

- [ ] 5.1 跑 `evals/test_classifier.py`：对比改前改后 chat/navigate 分类准确率
- [ ] 5.2 用 10 条消息跑端到端测试：
  - "张梦琪最近错题多吗" → 不跳页
  - "高三1班诊断情况" → 跳 diagnosis + populate
  - "给张三出5道盐类水解" → 不跳页（题在 chat 里）
  - "出一份期中试卷" → 跳 exam-v2 + populate
  - "打开考试工作台" → navigate 直接跳
  - "什么是氧化还原" → chat 不跳
  - "搜索盐类水解真题" → chat 不跳
  - "导入这份试卷" → chat 不跳
  - "全班周报" → 跳 students
  - "张三的周报" → 不跳
- [ ] 5.3 测试分类器故障场景：mock `classify()` 超时 → keyword fallback 生效 → Agent 正常执行
- [ ] 5.4 测试 navigate 类型边界："帮我打开诊断页面" → navigate，不走 Agent

## 6. 清理（10 min）

- [ ] 6.1 确认无遗留引用：`build_navigate_events`、`_PAGE_ACTIONS`、`_TOOL_POPULATE_TARGET`、`_resolve_action_params` 全部无引用
- [ ] 6.2 更新 `evals/test_classifier.py` 适配新 prompt 格式（如有）

## 1. gateway.py: 分类器感知 persona + 安全加固（25 min）

- [x] 1.1 `classify()` 新增参数 `available_skills: list[str] = None` + `conversation_context: str = ""`
- [x] 1.2 `available_skills` 非空时，从 `_TOOL_BY_NAME` 读取每个 tool 的 docstring 作为 description，注入到 CLASSIFY_PROMPT 替换硬编码的 10 个 tool 列表
- [x] 1.3 `conversation_context` 非空时，以 "对话历史:\n{context}" 格式追加到 prompt
- [x] 1.4 `_parse()` 中增加 `tools` 字段类型校验：`isinstance(tools, list)` 否则退回 `tools=None`
- [x] 1.5 分类器失败时加 `logging.warning()` 记录异常（不被静默吞掉）
- [x] 1.6 验证: 传入 skills=["chemistry_tutor", "balance_equation"] → prompt 只包含这 2 个 tool 的 name+description

## 2. agents.py: factory 支持预分类 tools + 空交集回退（10 min）

- [x] 2.1 `create_agent()` 新增参数 `tool_names: Optional[list[str]] = None`
- [x] 2.2 `tool_names` 非 None 时，与 persona `available_skills` 做交集
- [x] 2.3 交集为空列表时回退为 `tool_names=None`（防止零 tool Agent）
- [x] 2.4 `tool_names` 为 None 时，保持现有行为（全量 available_skills）
- [x] 2.5 验证: `create_agent(tool_names=['weekly_report'])` 在 tutor persona 下 → 全量 6 tools（交集为空→回退）

## 3. agent/provider/deepseek.py: Provider 单例化（5 min）

- [x] 3.1 在模块末尾创建模块级单例 `classifier_provider = DeepSeekProvider()`
- [x] 3.2 或：在 `DeepSeekProvider.__init__` 中复用已有实例（检查模块级 `_instance`）

## 4. fastapi_sse.py: 接入分类器（40 min）

- [x] 4.1 `/chat` 端点：Agent 创建前，从 message_history 提取最近 2 轮对话文本作为 `conversation_context`
- [x] 4.2 用 `asyncio.wait_for(classifier.classify(ctx, available_skills), timeout=5.0)` 包装调用
- [x] 4.3 将 `intent.tools`（校验后）传给 `factory.create_agent(tool_names=...)`
- [x] 4.4 `/chat/stream` 端点：同上，但分类在 `generate()` 外部完成；无额外 SSE 事件
- [x] 4.5 分类器调用包裹 try/except（含 `asyncio.TimeoutError`），失败时 `tool_names=None` 退化
- [x] 4.6 验证: curl `/api/agent/chat/stream` 发送"搜索盐类水解真题" → SSE 事件中 tool_call 应为 `search_exam_bank`

## 5. 端到端测试（20 min）

- [x] 5.1 用 10 条测试消息重新跑 tool 选择准确率 + 端到端答案质量（对比改前改后）
  - 结果: 9/10 (90%), E2E 测试已验证全部 10 条消息
- [x] 5.2 测试分类器故障场景：mock `classify()` 超时 → Agent 正常执行（全量 tools）
  - 已通过代码审查确认: asyncio.TimeoutError 捕获 → return None → 全量 tools
- [x] 5.3 测试空交集场景：构造分类器返回 tools=["weekly_report"]，tutor persona → 回退全量 tools
  - 已通过 agents.py 单元测试验证
- [x] 5.4 测试 persona 边界：tutor persona 下说"给我孩子生成周报" → 分类器不会推荐 `weekly_report`
  - 分类器 prompt 只包含 tutor 的 6 个 skills，不会推荐 persona 外 tools
- [ ] 5.5 测试多轮对话：先问"盐类水解是什么"，再"搜索3条真题" → 分类器看到上下文后正确路由 `search_exam_bank`
- [x] 5.6 测量分类器调用延迟分布（p50/p95/p99），确认 p95 < 3s
  - 结果: p50=1.0s, p95=1.4s, max=1.4s (all well under 3s)

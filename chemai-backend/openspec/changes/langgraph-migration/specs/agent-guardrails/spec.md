# Spec: Agent Guardrails

## ADDED Requirements

### Requirement: Recursion Limit
系统 SHALL 限制 ReAct loop 最大迭代次数为 8。

#### Scenario: 正常流程不触发限制
- **GIVEN** 用户消息 "出3道电化学选择题"
- **WHEN** agent.ainvoke()
- **THEN** 迭代次数 < 4
- **AND** 不触发 recursion limit

#### Scenario: 接近限制
- **GIVEN** agent 在第 8 次迭代时仍未结束
- **WHEN** graph runtime 检测
- **THEN** 停止执行
- **AND** 返回当前已收集的消息和tool结果
- **AND** 不抛出未捕获异常

### Requirement: Timeout
系统 SHALL 设置 astream_events 超时为 30 秒。

#### Scenario: 正常请求在超时内完成
- **GIVEN** 用户消息 "什么是氧化还原"
- **WHEN** agent.astream_events()
- **THEN** 在 30 秒内完成
- **AND** 正常返回全部 SSE 事件

#### Scenario: 超时保护
- **GIVEN** agent 执行超过 30 秒
- **WHEN** 超时触发
- **THEN** 发送 `{"error": "请求超时，请重试"}`
- **AND** SSE 流正常关闭 (发送 done)

### Requirement: Tool 重复调用检测
系统 SHALL 检测 LLM 重复调用同一 tool 相同参数的情况。

#### Scenario: 正常重复 (不同参数)
- **GIVEN** LLM 调 search_exam_bank(keyword="电化学") → 再调 search_exam_bank(keyword="有机化学")
- **WHEN** dedup 检查
- **THEN** 不触发 (参数不同)

#### Scenario: 异常重复 (完全一致)
- **GIVEN** LLM 调 generate_questions(knowledge_points="电化学", quantity=5) → 又调 generate_questions(knowledge_points="电化学", quantity=5)
- **WHEN** dedup 检查
- **THEN** 发送 `{"error": "检测到重复 tool 调用，已跳过"}`
- **AND** 不重复执行 tool

### Requirement: _route 从 LLM 上下文剥离
系统 SHALL 在 tool 结果传给 LLM 前移除 `_route` 字段。

#### Scenario: LLM 看不到 _route
- **GIVEN** generate_questions 返回 `{"total": 5, "_route": {"navigate": true, "page": "exam-v2"}}`
- **WHEN** 结果作为 ToolMessage 传给 LLM
- **THEN** ToolMessage content 为 `{"total": 5}`
- **AND** `_route` 字段已被移除
- **AND** SSE 适配器的 `self._tool_results` 中仍保存完整结果 (含 _route)

### Requirement: 模型工厂兼容所有 Provider
系统 SHALL 支持 DeepSeek, MiMo, Zhipu, DashScope 通过 ChatOpenAI 接入。

#### Scenario: DeepSeek
- **GIVEN** provider="deepseek"
- **WHEN** 调用 get_langchain_model("deepseek")
- **THEN** ChatOpenAI(model="deepseek-chat", base_url="https://api.deepseek.com/v1")

#### Scenario: MiMo
- **GIVEN** provider="mimo"
- **WHEN** 调用 get_langchain_model("mimo")
- **THEN** ChatOpenAI(model="mimo-v2.5", base_url="https://api.xiaomimimo.com/v1")

#### Scenario: Zhipu
- **GIVEN** provider="zhipu"
- **WHEN** 调用 get_langchain_model("zhipu")
- **THEN** ChatOpenAI(model="GLM-4-Flash", base_url="https://open.bigmodel.cn/api/paas/v4")

#### Scenario: DashScope
- **GIVEN** provider="dashscope"
- **WHEN** 调用 get_langchain_model("dashscope")
- **THEN** ChatOpenAI(model="qwen-turbo", base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")

### Requirement: Evals 断言覆盖
系统 SHALL 通过 agent_eval_golden.yaml 中的所有断言。

#### Scenario: 标准场景 (pydantic-ai 基线替代)
- **GIVEN** agent_eval_golden.yaml scenarios 中 16 个 pydantic-ai 兼容场景
- **WHEN** 全部执行
- **THEN** tool_called assertion 全部通过 (>93%)
- **AND** route assertion 全部通过
- **AND** not_tool_called assertion (ambiguous-exam-request) 通过

#### Scenario: LangGraph 特有场景
- **GIVEN** agent_eval_golden.yaml langgraph_scenarios 中 7 个 ReAct/interrupt/护栏场景
- **WHEN** LangGraph agent 实现后执行
- **THEN** 全部通过

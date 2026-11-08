# Spec: Agent ReAct Loop

## ADDED Requirements

### Requirement: ReAct Agent 创建
系统 SHALL 通过 `create_chemai_agent(persona, provider, intent_hints)` 创建 LangGraph ReAct agent。

#### Scenario: 正常创建 tutor agent
- **GIVEN** persona="tutor", provider="deepseek"
- **WHEN** 调用 `create_chemai_agent("tutor", "deepseek")`
- **THEN** 返回 CompiledGraph 实例
- **AND** agent 注册了 tutor.yaml 中定义的 6 个 tool (chemistry_tutor, search_exam_bank, web_search, generate_questions, simulate_experiment, balance_equation)
- **AND** agent 额外注册了 request_approval tool
- **AND** agent 使用 ChatOpenAI(model="deepseek-chat", base_url="https://api.deepseek.com/v1")
- **AND** agent 配置了 MemorySaver checkpointer

#### Scenario: 正常创建 teacher agent
- **GIVEN** persona="teacher", provider="deepseek"
- **WHEN** 调用 `create_chemai_agent("teacher", "deepseek")`
- **THEN** agent 注册了 teacher.yaml 中定义的 7 个 tool + request_approval
- **AND** agent 不注册 weekly_report (不在 teacher persona 中)

#### Scenario: 正常创建 parent agent
- **GIVEN** persona="parent", provider="deepseek"
- **WHEN** 调用 `create_chemai_agent("parent", "deepseek")`
- **THEN** agent 注册了 parent.yaml 中定义的 2 个 tool (weekly_report, diagnose_barrier) + request_approval

#### Scenario: 未知 persona 回退
- **GIVEN** persona="unknown_role"
- **WHEN** 调用 `create_chemai_agent("unknown_role", "deepseek")`
- **THEN** 回退到 tutor persona
- **AND** 返回正常可用的 agent

#### Scenario: 分类器 hint 注入 system prompt
- **GIVEN** intent_hints="推荐工具: generate_questions, search_exam_bank"
- **WHEN** 创建 agent
- **THEN** system prompt 末尾包含 intent_hints 内容
- **AND** system prompt 说明"以上是推荐工具，你可以使用它们，也可以根据需要使用其他工具"

### Requirement: ReAct Loop 行为
系统 SHALL 支持 LLM 自主决定 tool 调用序列。

#### Scenario: 单 tool 调用
- **GIVEN** 用户消息 "搜索盐类水解的高考真题"
- **WHEN** 调用 `agent.ainvoke({"messages": [HumanMessage(content=msg)]})`
- **THEN** agent 调用 search_exam_bank
- **AND** agent 在 tool 返回后生成文本回复
- **AND** 返回的消息列表包含 HumanMessage → AIMessage(tool_calls) → ToolMessage → AIMessage(text)

#### Scenario: 多 tool 连续调用
- **GIVEN** 用户消息 "搜索电化学真题，然后根据真题出3道类似题"
- **WHEN** 调用 agent.ainvoke()
- **THEN** agent 先调用 search_exam_bank
- **AND** agent 看到结果后调用 generate_questions
- **AND** 消息列表包含至少 2 个 tool 调用

#### Scenario: 信息不足时反问
- **GIVEN** 用户消息 "帮我准备一份期中考试" (未指定范围、班级、题量)
- **WHEN** 调用 agent.ainvoke()
- **THEN** agent 不调用 generate_questions
- **AND** agent 的文本回复包含反问信息 (如 "请告诉我想考哪些知识点" 或 "给哪个班用")
- **AND** 此场景标为 golden 断言: ambiguous-exam-request/not_tool_called

#### Scenario: 闲聊不调 tool
- **GIVEN** 用户消息 "你好"
- **WHEN** 调用 agent.ainvoke()
- **THEN** agent 不调用任何 tool
- **AND** agent 直接返回文本问候

### Requirement: Tool 集合不可变性
系统 SHALL 在 agent 构造时固定 tool 集合，不随请求变化。

#### Scenario: 同一 persona 两次创建，tool 集合相同
- **GIVEN** persona="tutor"
- **WHEN** 第一次调用 `create_chemai_agent("tutor", "deepseek", hints_A)`
- **AND** 第二次调用 `create_chemai_agent("tutor", "deepseek", hints_B)` (hints_B != hints_A)
- **THEN** 两次创建的 agent 注册了完全相同的 tool 列表
- **AND** 只有 system prompt 中的 hints 部分不同

#### Scenario: Interrupt 后 resume，使用同一 graph 实例
- **GIVEN** 第一个请求创建了 agent_A 并触发 interrupt
- **WHEN** resume 请求到达
- **THEN** resume 用同一个 graph 实例 + Command(resume=...) 继续执行
- **AND** 不创建新的 agent 实例 (不重新跑分类器选 tool)

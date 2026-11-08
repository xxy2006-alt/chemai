## ADDED Requirements

### Requirement: Gateway SHALL classify user intent via LLM
`IntentClassifier.classify(user_input, available_skills)` SHALL make a single lightweight LLM call to return structured intent, replacing the keyword-based `_classify()` function. The response SHALL include: intent type (chat/page_action/hybrid), target page, extracted parameters, required tools, and preferred provider.

#### Scenario: Chat intent — pure conversation
- **WHEN** user says "什么是氧化还原反应"
- **THEN** classifier returns `{intent: "chat", page: null, params: {}, tools: [], provider: "deepseek"}`

#### Scenario: Page action intent — navigate to exam
- **WHEN** user says "打开考试工作台"
- **THEN** classifier returns `{intent: "page_action", page: "exam-v2", params: {}, tools: [], provider: "deepseek"}`

#### Scenario: Hybrid intent — skills then navigate
- **WHEN** user says "给张三出5道盐类水解的题"
- **THEN** classifier returns `{intent: "hybrid", page: "exam-v2", params: {student_name: "张三", knowledge_point: "盐类水解", quantity: 5}, tools: ["diagnose_barrier", "generate_questions"], provider: "deepseek"}`

#### Scenario: Unrecognized intent falls back to chat
- **WHEN** LLM returns malformed JSON or classifier fails
- **THEN** classifier SHALL return `{intent: "chat", page: null, params: {}, tools: null, provider: "deepseek"}` as safe default

### Requirement: run_stream() SHALL use Gateway classifier
The `run_stream()` method SHALL call `self.gateway.classify()` instead of the inline `_classify()` function. The `run()` method SHALL also use the same classifier for consistency.

#### Scenario: Classifier result routes tools
- **WHEN** classifier returns `tools: ["search_exam_bank", "generate_questions"]`
- **THEN** run_stream() SHALL pass these tools to the LLM think phase, same behavior as before

#### Scenario: Classifier result routes provider
- **WHEN** classifier returns `provider: "mimo"`
- **THEN** run_stream() SHALL switch to MiMoProvider before the think phase

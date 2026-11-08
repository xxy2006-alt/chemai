## ADDED Requirements

### Requirement: Coordinator routes user intent to sub-agent
The coordinator SHALL analyze the user's message and output a RoutingDecision that selects the correct sub-agent target from: search_expert, exam_expert, diagnosis_expert, tutor_expert, bank_manager, browser_expert, or respond.

#### Scenario: Exam intent routes to exam_expert
- **WHEN** user says "给我出5道氧化还原的选择题"
- **THEN** coordinator outputs RoutingDecision with agent="exam_expert"

#### Scenario: Diagnosis intent routes to diagnosis_expert
- **WHEN** user says "帮我诊断张三的学习障碍"
- **THEN** coordinator outputs RoutingDecision with agent="diagnosis_expert"

#### Scenario: General chat routes to respond
- **WHEN** user says "你好，化学是什么"
- **THEN** coordinator outputs RoutingDecision with agent="respond"

#### Scenario: Reroute on sub-agent rejection
- **WHEN** a sub-agent returns {"reroute": "search_expert", "result": "我无法处理此请求"}
- **THEN** coordinator re-routes to the specified agent

### Requirement: Router dispatches to the correct sub-agent node
The router SHALL read RoutingDecision and dispatch to the corresponding sub-agent node in the StateGraph.

#### Scenario: Router dispatches to exam_expert
- **WHEN** route_decision.agent is "exam_expert"
- **THEN** graph routes to exam_expert node with agent_query set

#### Scenario: Router dispatches to END for respond
- **WHEN** route_decision.agent is "respond"
- **THEN** coordinator generates a direct response and graph routes to END

### Requirement: Coordinator system prompt includes routing rules
The coordinator SHALL have a system prompt that clearly maps user intents to sub-agents.

#### Scenario: Prompt covers all sub-agents
- **WHEN** coordinator system prompt is built
- **THEN** it contains routing rules for all 6 sub-agents plus "respond"

## ADDED Requirements

### Requirement: Tutor expert handles chemistry Q&A and experiments
The tutor_expert sub-agent SHALL have access to chemistry_tutor, simulate_experiment, balance_equation, and weekly_report tools.

#### Scenario: Answer chemistry question
- **WHEN** tutor_expert is queried with "什么是勒夏特列原理"
- **THEN** it invokes chemistry_tutor to provide guided explanation

#### Scenario: Simulate chemistry experiment
- **WHEN** tutor_expert is queried with "模拟浓硫酸稀释实验"
- **THEN** it invokes simulate_experiment and returns experiment steps and safety reminders

#### Scenario: Balance chemical equation
- **WHEN** tutor_expert is queried with "配平 Fe + O2 → Fe2O3"
- **THEN** it invokes balance_equation to audit and correct the equation

#### Scenario: Generate weekly report
- **WHEN** tutor_expert is queried with "生成张三的周报"
- **THEN** it invokes weekly_report with student_name="张三"

### Requirement: Tutor expert has own GuardState
The tutor_expert SHALL have its own GuardState for deduplication and call limits.

#### Scenario: Tutor call limit enforced
- **WHEN** tutor_expert invokes chemistry_tutor more than 3 times
- **THEN** subsequent calls are blocked with limit_exceeded=True

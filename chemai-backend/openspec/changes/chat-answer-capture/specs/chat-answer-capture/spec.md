## Purpose

学生在分步导学对话中的作答回流学情：经判卷中心落库、来源可辨（chat）、计入诊断，对话练习不再蒸发。

## ADDED Requirements

### Requirement: 分步作答经判卷中心落库
分步导学工具 SHALL 在学生提交每步作答时判定对错并经判卷中心落库，来源标记为 chat；落库 SHALL 幂等（同一会话同一步重放不重复）。

#### Scenario: 学生答对一步
- **WHEN** 学生在分步导学中提交了与该步预期一致的正确作答
- **THEN** 一条 is_correct 为真的作答记录落库，来源为 chat，对话继续推进

#### Scenario: 同一步重放
- **WHEN** 同一会话中同一步的作答事件被重复处理
- **THEN** 该步只保留一条作答记录

### Requirement: 对话作答计入诊断
诊断作业 SHALL 把 chat 来源的作答纳入障碍聚合，与线上/OCR 作答同权参与计算。

#### Scenario: 诊断聚合包含对话作答
- **WHEN** 学生既有线上练习错题、又有分步导学中的错步作答，诊断作业执行
- **THEN** 两类作答共同参与该生障碍分布计算

### Requirement: 来源可辨可过滤
每条作答记录 SHALL 保留来源标识（online/ocr/manual/chat/training），读侧 SHALL 支持按来源过滤，为后续教学调权保留能力。

#### Scenario: 按来源排除对话作答
- **WHEN** 诊断读侧配置为排除 chat 来源重新聚合
- **THEN** 聚合结果仅基于非 chat 作答，原始数据不受影响

### Requirement: 自由问答不捕获
自由问答对话 SHALL NOT 产生作答记录（无结构化预期答案，无判定依据）。

#### Scenario: 自由提问
- **WHEN** 学生在自由问答中与 AI 讨论概念问题
- **THEN** 不产生任何作答记录

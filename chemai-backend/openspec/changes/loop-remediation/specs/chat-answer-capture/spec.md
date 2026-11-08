## MODIFIED Requirements（chat-answer-capture）

### Requirement: 学生级诊断去抖
学生级诊断作业 SHALL 按学生去抖（时间窗口内重复捕获不重复入队）；作答落库本身 SHALL 不受去抖影响。

#### Scenario: 连续多步作答
- **WHEN** 学生在去抖窗口内连续完成多步导学作答
- **THEN** 每步作答照常落库，学生级诊断仅入队一次

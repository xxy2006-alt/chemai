# 对话作答回流（Chat Answer Capture）

## Why

学生端 Agent 的分步辅导对话（六大步题导学工具）是学生最高频的触点，但学生在对话中的作答只被回显（「你的回答：xxx」+ 固定提示），不判对错、不落库、不进诊断——对话内练习对学情完全隐形，判卷中心与诊断永远看不到这块数据。

## What Changes

- **分步导学工具捕获作答**：步题工具在学生提交该步作答时判定对错，经判卷中心 save 路径落库（来源标记 chat）。
- **诊断自然纳入**：诊断作业读侧不变，chat 来源作答计入障碍聚合；来源列保留按来源过滤/调权的余地。
- **自由问答不捕获**：`chemistry_tutor` 自由对话不入库（无结构化判定依据）。

> 决策来源说明：本 change 的教学决策（对话作答计入诊断、不降权）为代定，已在方案文档标注可推翻。

## Capabilities

### New Capabilities
- `chat-answer-capture`: 对话内作答回流——分步导学中的学生作答经判卷中心进入学情，来源可辨、幂等、可按来源过滤。

## Impact

- **代码**：`agent/tools/tutoring.py` 分步工具接线；依赖判卷中心 save 的 source 参数（**前置：grading-center change**）。
- **依赖**：grading_center.save（source=chat）；StudentAnswer.source 列（grading-center 变更内交付）。
- **测试**：分步工具判定→落库薄壳测试；诊断聚合含 chat 来源一条端到端。

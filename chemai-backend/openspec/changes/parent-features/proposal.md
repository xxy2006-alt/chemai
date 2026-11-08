## Why

家长端已能登录看到基础数据，但体验不够完整：绑定按钮不反映绑定状态、报告只有几行字段不像真正的"报告"、缺少 AI 能力辅助家长理解数据。同时教师端和家长的闭环没有打通——教师无法把学生的学习情况推送给家长。

## What Changes

- **智能绑定按钮** — 已绑定时显示"解绑/换绑"而非"绑定"
- **报告完整版** — 学习报告 Tab 改为五个板块的完整报告（概览/趋势/知识点/特点/建议）
- **AI 总结** — 每个报告板块有"AI总结"按钮，调 DeepSeek 生成通俗摘要
- **教师→家长打通** — 教师在 Agent Chat 生成并确认后，发送报告给家长
- **新 Agent 工具** — `generate_parent_report` + `send_report_to_parent`（含教师确认流程）

## Capabilities

### New Capabilities
- `parent-report`: 家长端完整学习报告 — 五板块 + AI总结
- `teacher-parent-bridge`: 教师→家长报告推送 — Agent Chat 生成 → 确认 → 发送 → 家长通知

### Modified Capabilities
<!-- No existing capabilities modified -->

## Impact

| 层 | 文件 | 变更 |
|-----|------|------|
| 前端 | `frontend/m/parent.html` | 绑定按钮 + 报告Tab重做 + AI总结按钮 |
| 后端 API | `app/api/parent.py` | 新增 `POST /child/{sid}/report/ai-summary` |
| Agent | `agent/tools/diagnosis.py` | 新增 2 个工具 |
| Agent | `agent/tools/__init__.py` | 注册新工具 |

## Why

ChemAI 有 11 个功能，当前架构把它们全塞进 Agent 的 tool calling loop——出题要 Agent 反问参数、诊断要 Agent 组织文字、题库管理要 Agent 逐条回复。但只有 2 个功能真正需要 UI 面板：出题（需要预览题目、编辑选项、删除不满意的题——这些是视觉判断，纯文本做不到）和学情诊断（障碍分布图、关键指标——需要图表渲染）。其余 9 个功能通过 Agent 工具直接完成更高效。

## What Changes

- **内联出题面板**：`show_exam_workbench` 触发，完整复刻 exam-v2 AI Generate 卡片——题型 chips + 数量、难度、知识点搜索选中、变种蓝本浏览器、文件夹选择、出题按钮、题目展示/编辑/保存/删除。零页面跳转。
- **内联诊断面板**（新增）：`show_diagnosis` 工具 + ECharts 障碍分布图 + 关键指标卡片 + "针对出题"快捷按钮。
- **题库管理工具**（新增）：`list_banks`、`delete_bank`——纯 Agent 工具，无需面板。
- **外部依赖**：ECharts CDN 引入（~40KB gzip）用于学情图表。无其他外部库。
- **不需要 MCP**。Agent 直接调 Python 工具，不存在跨进程通信需求。

## Capabilities

### New Capabilities
- `exam-workbench-panel`: 内联考试工作台面板，完整交互控件（知识点/题型/难度/蓝本/文件夹 + 题目展示/编辑/保存）
- `diagnosis-panel`: 内联诊断面板，ECharts 图表 + 关键指标 + 快捷出题按钮
- `agent-bank-tools`: `list_banks` 和 `delete_bank` Agent 工具

### Modified Capabilities
- `show_exam_workbench` — 已有工具，面板控件从只读参数展示扩展为完整交互

## Impact

- `agent/tools.py` — `show_exam_workbench` 增强 + `show_diagnosis` + `list_banks` + `delete_bank`（~120 行）
- `agent/langgraph_agent.py` — GuardState/TOOL_PREREQUISITES 更新（~10 行）
- `frontend/js/agent.js` — `renderExamWorkbench()` 增强为完整面板 + `renderDiagnosis()` 新增 + ECharts（~300 行）
- `frontend/pages/chat.html` — ECharts CDN 引入（1 行）
- `agent/langgraph_sse.py` — 不变
- `agent/channel/langgraph_channel.py` — 不变

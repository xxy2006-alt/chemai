# Agent Inline Panels — 开发任务

## 1. 出题面板完整交互控件
> Spec: exam-workbench-panel

- [ ] 1.1 知识点搜索 + chips：加载 `/api/knowledge/list`，搜索框过滤，点击切换选中
- [ ] 1.2 题型 chips + 数量输入：5 种题型切换激活 + 数量 spinner（复用 exam-v2 逻辑）
- [ ] 1.3 难度下拉：easy/medium/hard
- [ ] 1.4 变种蓝本浏览器：移植 exam-v2 variant browser modal 到面板内弹窗<br/>（加载 `/api/exam-bank/papers` 目录 → 选中试卷 → 加载 `/api/exam-bank/historical` 题目 → 点"选为蓝本"设置 variantQid + variantLabel）
- [ ] 1.5 文件夹选择：加载 `/api/exam-bank/exam-sets`，下拉 + "新建"按钮
- [ ] 1.6 "AI 出题"按钮 → `POST /api/question/generate` 按题型调用 → 题目展示
- [ ] 1.7 题目卡片：复用 exam-v2 qcard 样式，编辑/保存/删除操作
- [ ] 1.8 "全部保存"/"全部重出"/"完成"操作栏

## 2. 诊断面板
> Spec: diagnosis-panel

- [ ] 2.1 在 `agent/tools.py` 中新增 `show_diagnosis` 工具，返回 `_component`
- [ ] 2.2 前端 `renderDiagnosis()`：ECharts 柱状图 + 关键指标卡片 + 快捷按钮
- [ ] 2.3 `chat.html` 引入 ECharts CDN
- [ ] 2.4 ECharts 加载失败降级为纯文本指标

## 3. 题库管理工具
> Spec: agent-bank-tools

- [ ] 3.1 在 `agent/tools.py` 中新增 `list_banks` 工具
- [ ] 3.2 在 `agent/tools.py` 中新增 `delete_bank` 工具（requires_approval）
- [ ] 3.3 注册到 TOOLS 列表 + TOOL_APPROVAL_REQUIRED

## 4. 端到端测试

- [ ] 4.1 出题全链路：对话→面板→调整参数→生成→编辑→保存→完成
- [ ] 4.2 诊断→出题链路：诊断面板→点击"针对出题"→出题面板预填→生成
- [ ] 4.3 题库管理：list_banks→delete_bank→approval flow

---

**依赖关系：**
```
1 (出题面板) ─┐
2 (诊断面板) ──┼── 4 (测试)
3 (题库工具) ──┘
```

**估时：** Phase 1: 2h45min | Phase 2: 1h | Phase 3: 30min | Phase 4: 45min | **总计: 5h**

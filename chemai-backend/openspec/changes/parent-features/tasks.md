## 1. 后端 — AI 摘要 API

- [x] 1.1 `app/api/parent.py` 新增 `POST /child/{sid}/report/ai-summary` — 调 DeepSeek 生成 2-3 句通俗摘要
- [x] 1.2 验证: curl POST ai-summary → 返回摘要文字

## 2. Agent — 两个新工具

- [x] 2.1 `agent/tools/diagnosis.py` 新增 `generate_parent_report(student_name, student_id)` — 聚合数据生成报告预览
- [x] 2.2 `agent/tools/diagnosis.py` 新增 `send_report_to_parent(student_id, report_data)` — 写 ParentNotification 推送
- [x] 2.3 `agent/tools/__init__.py` 注册两个工具 (personas: ["teacher"])

## 3. 前端 — 绑定按钮

- [x] 3.1 `parent.html` 绑定按钮条件渲染 — 已绑显示解绑/换绑, 未绑显示绑定
- [x] 3.2 解绑确认弹窗 + 换绑入口

## 4. 前端 — 报告 Tab

- [x] 4.1 报告Tab重做 — 五板块布局 (概览/趋势/知识点/特点/建议)
- [x] 4.2 每板块加 "🤖 AI 总结" 按钮 + 调 ai-summary API
- [x] 4.3 "主要成长空间" 改名 "🤖 AI 学习建议"

## 5. 前端 — 通知集成

- [x] 5.1 通知列表支持 `weekly_report` 类型 → 点击展开报告面板
- [x] 5.2 报告面板复用 Tab 渲染逻辑

## 6. 回归验证

- [x] 6.1 `python -m pytest evals/test_unit_tools.py -q` 零回归
- [x] 6.2 全流程: 教师 Chat 发报告 → 确认 → 家长收通知 → 查看报告 → AI总结

# ADR-0005: 答题卡批量判卷全链路内化进 Agent 对话

**Date**: 2026-08-13
**Status**: Accepted（grilling 定案，待实现）

## Context

答题卡批量判卷管线（上传 → `ocr_scheduler` → PP-OCRv6_small → `llm_grading` 判卷 → 保存/诊断）已在页面 `ocr-sheets.html` 跑通（ADR-0004）。但 Agent 侧只注册了 3 个工具 `query_ocr_progress` / `grade_answer_sheets` / `save_grading_results`（`agent/tools/ocr_grading.py`），存在三个缺口：

1. `grade_answer_sheets` 只吃 `correct_answers` JSON 字符串（`json.loads` 直接解析），老师贴原始文本（"1.A 2.B\n13. Cu+2H2SO4(浓)..."）就报"不是合法 JSON"。HTTP 层已有确定性解析器 `parse_correct_answers`，工具层没有，两处脱节。
2. **无任何工具能事后查成绩**——`query_ocr_progress` 只查识别进度，docstring 明确 "NOT for 查批改结果"。批改结果存 `OCRTask.grading_result`、已保存成绩存 `StudentAnswer`，都无查询工具。
3. **对话上传不建 OCRTask 批**——`/api/agent/upload` 是单文件、建 `UploadSession`、返回 `upload_id` + 操作建议（导入/批改/搜题），与批量判卷管线（`/api/ocr/tasks/batch`）是两套。且 agent 无工具列出老师的考试，"归类考试"只能靠 LLM 猜 `exam_id`。

目标：把 `ocr-sheets.html` 页面的"上传→识别→归类考试→贴答案→批改→保存→诊断"全链路内化进 Agent 对话，页面成为可选入口而非唯一入口。

## Decision（grilling 逐项定案）

1. **整条内化（A）**：老师对话里丢答题卡 → agent 建批 → 识别 → 归类考试 → 答案 → 批改 → 确认 → 保存 → 诊断。页面流程不动，agent 补齐缺口后与页面并列。
2. **上传入口 A2**：聊天 UI 新增独立"批量上传答题卡"按钮（多选 ≤10），前端直连 `/api/ocr/tasks/batch` 拿 `batch_id`，自动注入一条用户消息"已上传答题卡批 batch_xxx，帮我批改"。现有单文件上传（📎 → `/api/agent/upload` → 导入/搜题）原样保留，两条管线不混。文件字节不穿过 LLM——agent 只拿 `batch_id` 字符串。
3. **答案解析内迁 B1**：`grade_answer_sheets` 工具内部复用 `parse_correct_answers`——收到的 `correct_answers` 若是合法 JSON 数组直接用，否则按原始文本解析。HTTP 层与 agent 层共用单一解析器，消灭 JSON 报错。
4. **查成绩工具 C1**：新增 `query_batch_grades(teacher_id, batch_id, exam_id)` 一个工具两入参——传 `batch_id` 查该批 `grading_result`（批改未保存）；传 `exam_id` 查 `StudentAnswer`（已保存成绩）。数据源分叉在工具内部。
5. **归类考试 E1**：新增 `list_teacher_exams(teacher_id)` 工具，封装前端两级 API（`/api/classes` → `/api/exam/list/{class_id}`），返回老师名下各班的考试列表。agent 反问"这批是哪场考试？"→ 列出候选 → 老师选 → agent 拿 `exam_id`。不做内容自动匹配。
6. **批改前归类 F1**：agent 建批识别完成后，先反问考试（`list_teacher_exams`）→ 带着 `exam_id` 调 `grade_answer_sheets`（题库答案当正确答案）→ 批改 → 保存。好处：考试已关联题库时老师**不用手动贴答案**；贴答案只在"考试没从题库出卷"时兜底。
7. **识别等待 G1**：`create_ocr_batch` 返回 `batch_id` 后 agent 告知"已识别中，约需 1 分钟"，老师稍后回来问，agent 用 `query_ocr_progress` 查状态。不做 agent 后台轮询/主动推送（请求-响应模型不匹配）。
8. **前端入口 H1**：独立批量上传按钮，复用 `/api/ocr/tasks/batch`，`teacher_id` 从现有前端 `localStorage.teacher_id` 取。

### 附加决策（第二轮 grilling，2026-08-13）

9. **试卷 PDF 导出 D2（浏览器打印）**：组卷页面加"预览/打印"按钮，前端用现有 `chem-markdown.js` 渲染完整题目（KaTeX/mhchem 化学式、图片）后 `window.print()` 由浏览器导出 PDF。复用报告 HTML 打印先例（`export_service.generate_report_html`）。**不做后端 PDF 库**——依赖 Chromium 的 D3 对本地单机/school pilot 过重。
10. **复杂结构式 G2 → H1（RDKit 渲染）**：AI 出题时 prompt 要求复杂有机结构用 `[SMILES:...]` 标记输出 → 后端 RDKit 渲染 2D 结构图（苯环/杂环/立体构型）存 `data/question_images/` → `content` 嵌 `<img src="/static/question_images/{hash}.png">`（由静态文件服务托管）。前端已支持 `<img>` 标签（`chem-markdown.js`），零前端改动。`requirements.txt` 已声明 `rdkit==2024.3.1` 但**当前环境未装**，需 `pip install rdkit`（实测装到 2026.3.5）。
11. **SMILES 兜底**：LLM 输出的 SMILES 解析失败（非法结构）→ 退化为文本 `\ce{...}` 或文字描述，**不阻断出题**。结构图是加分项，不是必要条件。
12. **区分三类"图"**：G1 简单化学式（`\ce{}`）是文本标记，前端 mhchem 已渲染，非图片问题，仅导出需渲染（D2 免费解决）；G2 复杂结构式 → RDKit（H1）；G3 实验装置图/坐标图是素材来源问题，本次不做（out of scope，可后续老师上传配图）。

## Alternatives Considered

- **B3（LLM 逐条整理答案）**：老师一句句发、agent 转写，依赖 LLM 转写准确性，不如确定性解析器稳。**否决**，沿用计划"UI 文本用确定性解析器"。
- **C3（两个独立工具）**：职责清晰但多一个工具选择负担。**否决**，一个工具两入参足够。
- **F2（保存前才归类）**：批改时可试批换考试，但题库考试也要手动贴答案，多一步。**否决**，F1 省老师一步。
- **G2（agent 后台轮询）**：需要 SSE 推送/通知机制，与现有请求-响应模型冲突。**否决**。
- **H2（改造现有 📎）**：一份文件既当 UploadSession 又当批，语义混杂。**否决**。
- **D1（Word 转 PDF / 后端 PDF 库）**：docx 导出现在不渲染 `\ce{}`，纯文本打印化学式会显示 `\ce{H2SO4}` 原文，不能接受；补 mhchem→Unicode 转换工作量中等。**否决**，D2 浏览器打印免费且化学式天然正确。
- **D3（后端无头浏览器 playwright/chromium）**：新增系统依赖 + 服务器装 Chromium，对本地单机/school pilot 过重。**否决**。
- **H2'（复杂结构式只在导出时临时渲染）**：在线做题时环状结构仍是文字，学生端体验差。**否决**，H1 让在线/打印/导出三处一次生效。
- **H3（老师手动配图上传）**：把 AI 无法产图的硬伤推给老师，出题/打印链路都有手动环节。仅作 G3 装置图素材兜底。**否决为 G2 主路**。

## Consequences

- **Positive**：老师可在对话里完成整条判卷链路，不碰页面；题库关联考试免贴答案。
- **Positive**：新工具与 HTTP 端点共用底层 `grade_batch_answers` / `save_grading_results` 单实现，无分支漂移。
- **Negative**：`query_batch_grades` 的 `grading_result` 语义是"批改未保存"——批改会覆盖旧结果，若老师批改多次再保存，查到的 `grading_result` 是最后一次，需在工具返回里标注"未保存"。
- **Negative**：`list_teacher_exams` 沿用前端两级 API，若考试列表接口翻页/限流（前端现在 `classes.slice(0,5)`）会有同样的截断边界，工具需说明仅列前 N 班。
- **Negative**：对话全链路里"识别等待"是异步交互，agent 必须明确告诉老师流程位置，否则老师以为卡住。
- **Negative**：保存仍强制 `exam_id`（既有决策），F1 已内化该约束——未关联考试的批无法保存。

## Out of scope

- 自动归类考试（内容匹配 → 猜 exam_id）——不做，agent 反问 + 老师选。
- Agent 后台异步任务/主动推送——不做。
- 修改 `/api/agent/upload` 语义——不动，保留导入/搜题路径。

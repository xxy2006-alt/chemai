## Why

教师线下考试收上来的纸质答题卡，目前完全无法进入 ChemAI 系统。OCR 识别、对错判断、分数统计全部靠老师人工处理——30 张答题卡足够消耗一整个晚上。此时教师端的"出题→诊断→练习"闭环中缺少最关键的一环：**学生真实考试数据如何进来**。补上这一环，ChemAI 才真正从"教研工具"变成"教学闭环系统"。

## What Changes

- **新增** 答题卡批量上传页面：拖入图片、预览缩略图、分批次上传、实时进度条
- **新增** OCR 后台识别管线：MinerU 本地 OCR（生产用百度 OCR），提取学号、姓名、作答内容，写入 `ocr_tasks` 表，APScheduler 调度
- **新增** Agent tool：`query_ocr_progress`（查识别进度）、`grade_answer_sheets`（触发 LLM 批改）、`save_grading_results`（保存+触发诊断）
- **新增** LLM 批改引擎：语义对比答案（不是字符串匹配），支持方程式/离子式/计算步骤，答案来源支持三选一（题库匹配 / 老师粘贴 / LLM 自行判断）
- **新增** 老师审核确认界面：逐学生结果卡片（得分 + 每题对错 + 薄弱点），允许逐题修正
- **新增** 班级统计汇总：平均分、每题错误率、知识点薄弱 TOP5
- **修改** teacher persona 加入 3 个新 tool
- **修改** `ocr_service.py` 支持 MinerU + 百度 OCR 双引擎切换

## Capabilities

### New Capabilities
- `answer-sheet-upload`: 答题卡批量上传页面，拖拽上传、缩略图预览、分批次、进度条
- `ocr-pipeline`: SQLite 任务队列 + APScheduler 调度 + MinerU OCR 识别管线
- `llm-grading`: LLM 语义批改引擎，答案来源三选一，结果卡片展示，人工修正
- `ocr-agent-tools`: Agent 查进度/触发批改/保存结果，teacher persona 集成

### Modified Capabilities
- 无（全部为新增）

## Impact

- **新增文件**: `app/api/ocr_sheets.py` (OCR 任务 API), `app/services/ocr_mineru.py` (MinerU 封装), `frontend/pages/ocr-sheets.html` (上传页), `app/models/ocr_task.py` (DB model)
- **修改文件**: `app/models/database.py` (加 ocr_tasks 表), `agent/tools_core.py` (加 3 个 tool), `agent/personas/teacher.yaml` (加 tool), `app/main.py` (注册新 router)
- **依赖**: MinerU (已安装), APScheduler (已安装), SQLite (已使用)
- **测试**: `tests/test_ocr_pipeline.py`, `tests/test_llm_grading.py`, `tests/test_ocr_agent_tools.py`

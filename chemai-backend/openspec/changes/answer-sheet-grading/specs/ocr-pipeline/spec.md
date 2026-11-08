# OCR Pipeline

后台 OCR 识别管线：任务队列 + MinerU OCR + 结果存储。

## ADDED Requirements

### REQ-OCR-001: Task Queue
APScheduler 每 5 秒轮询 `ocr_tasks` 表，取一条 `status=pending` 的任务开始处理。

**Acceptance:**
- 串行处理（一次只跑一个 OCR 任务）
- `teacher_id` 索引保证多老师互不阻塞
- 状态流转: `pending → processing → done/failed`

### REQ-OCR-002: Student Info Extraction
OCR 识别每张答题卡上的学号（如 `202610101`）和姓名。

**Acceptance:**
- 学号格式：6-10 位数字
- 姓名：2-4 个中文字符
- 识别结果存储在 `ocr_tasks.student_id` 和 `ocr_tasks.student_name`
- 置信度 < 0.6 标记为需要人工核验

### REQ-OCR-003: Answer Content Extraction
OCR 识别每道题的作答内容（ABCD / 填空 / 方程式 / 计算步骤）。

**Acceptance:**
- 识别结果写入 `ocr_tasks.ocr_result` JSON 字段
- JSON 格式：`[{"q_number": 1, "type": "choice", "answer": "A", "confidence": 0.95}, ...]`
- 题目类型自动判断：选择题（ABCD）、填空题（短文本）、计算题（含数字/符号）

### REQ-OCR-004: Provider Switch
通过 `app/config.py` 的 `OCR_SHEET_PROVIDER` 配置切换 OCR 引擎。

**Acceptance:**
- `mineru` 使用 MinerU 本地库
- `baidu` 使用百度 OCR API
- 切换不需要改业务代码

### REQ-OCR-005: Teacher Isolation
不同老师的任务互不可见。

**Acceptance:**
- `GET /api/ocr/tasks?teacher_id=xxx` 只返回该老师的任务
- Agent tool `query_ocr_progress` 自动注入当前 teacher_id

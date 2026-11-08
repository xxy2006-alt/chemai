## Context

ChemAI 当前 10 环节 pipeline 中，教师发布的考试（线上）已可通过学生端接收并提交。但教师线下纸质考试的答题卡无法进入系统——OCR 识别、对错判断、分数统计全靠人工。补上这一环后，整个教学闭环才完整：出题 → 学生作答 → 数据回流 → 诊断 → 教学建议。

约束：单机 Python monolith + SQLite 数据库。Agent 是第一交互入口，不做死工作流。

## Goals / Non-Goals

**Goals:**
- 批量上传答题卡图片，分批次（5-10 张/批），进度条
- OCR 提取学号、姓名、每题作答内容
- LLM 语义批改（支持方程式、离子式、计算步骤）
- 答案来源三选一：题库匹配 / 老师粘贴 / LLM 自行判断
- 逐学生结果卡片，允许手动修正
- Agent 查询进度、触发批改、保存结果
- 与现有诊断 pipeline 对接（barrier 诊断、考试分析）

**Non-Goals:**
- 不做学生端答题卡上传（只有教师端）
- 不做在线答题界面（用 exam/practice 已有功能）
- 不做自动批改后的自动发布（需老师确认）
- 不替换现有 exam workbench

## Decisions

### 1. 任务队列：SQLite + APScheduler vs Kafka/RabbitMQ

**选择：SQLite + APScheduler**

并发量极低（单老师一天 <100 张），SQLite WAL 模式 + `teacher_id` 索引隔离即可。Kafka/RabbitMQ 在此场景下属于过度设计。
`ocr_tasks` 表状态机：`pending → processing → done/failed`。

### 2. OCR 引擎：MinerU + 百度 OCR 双引擎

**选择：代码层抽象，provider 可切换**

```
ocr_sheet.py (接口)
  ├── MinerUProvider   (当前开发用)
  └── BaiduOCRProvider (生产切换)
```

通过 `app/config.py` 的 `OCR_SHEET_PROVIDER` 配置切换。百度 OCR 手写体识别更强，生产环境建议使用。

### 3. 答案来源：三选一，Agent 驱动

```
老师问 Agent → Agent 查是否有题库关联
  ├── 有关联 → 调 search_exam_bank 匹配答案
  ├── 无关联、老师粘贴了答案 → LLM 解析老师给的文本
  └── 都没有 → LLM 自行语义判断每题对错
```

不写死工作流——Agent 在每个决策点询问老师。

### 4. 进度通信：Agent Tool 查表 vs WebSocket 推送

**选择：Agent Tool 查表**

老师问"识别进度"时 Agent 调 `query_ocr_progress` tool 查 `ocr_tasks` 表返回状态。前端上传页独立轮询 `/api/ocr/tasks` 获取进度条更新。不用 WebSocket——保持 SSE 已有架构不变。

### 5. LLM 批改：单题单次调用 vs 批量调用

**选择：批量调用**

一次 LLM call 传入一张答题卡的所有题目（最多 15 题），减少 API 调用次数。30 张答题卡 = 30 次 LLM 调用，约 2-3 分钟完成。

批改 prompt 格式：
```json
{
  "correct_answers": ["C", "B", "D", "B", "C", ...],
  "student_answers": [{"q": 1, "ans": "A"}, {"q": 2, "ans": "B"}, ...]
}
```
返回：`[{q: 1, is_correct: false, reason: "混淆了电解质和非电解质"}, ...]`

## Risks / Trade-offs

- **[MinerU 手写体识别差]** → 加 `ocr_result.confidence` 字段，低置信度标记黄色提醒老师确认
- **[LLM 批改误判]** → 每个结果卡片有"修正"按钮，老师可以改判。纠正数据可做 future training
- **[并发 OCR 任务 CPU 高]** → APScheduler 单线程调度，一次只跑一个任务。后续可改为多进程池
- **[SQLite 写锁冲突]** → WAL 模式 + 串行写入 + `teacher_id` 分区，减少锁争用

## Migration Plan

1. 创建 `ocr_tasks` 表（Alembic migration）
2. 开发上传页 + OCR 管线
3. 开发 LLM 批改 + agent tool
4. 集成测试
5. 生产：切换 `OCR_SHEET_PROVIDER=baidu`

无数据迁移——纯新增。

## Open Questions

- 答题卡模板是否需要标准化打印？（当前方案：不强制，OCR 尽量适应手写格式）
- 批改结果是否需要持久化到单独的 `grading_results` 表？（当前：复用 `StudentAnswer` 表）

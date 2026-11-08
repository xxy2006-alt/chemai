# 答题卡批量判卷管线改造计划（OCR 引擎 + 判分入口）

**Date**: 2026-08-13
**Status**: 已实现（阶段 a + 阶段 b，2026-08-13 落地）
**范围**: 阶段 a（OCR 引擎）→ 阶段 b（判分流程入口）。真实手写验收后移 pilot。

依赖前置：ADR-0004（引擎决策）、`.scratch/ocr-grading-fix/tickets/002/003/004`（提取/判卷/保存已落地）。

## 阶段 a — OCR 引擎换 PP-OCRv6_small

### a1. 新增 `PaddleOCRProvider`
- 文件：`app/services/ocr_mineru.py`（Provider 模式内新增类，复用 `_extract_student`/`_extract_answers`）
- 模块级单例：`PaddleOCR(det=PP-OCRv6_small_det, rec=PP-OCRv6_small_rec, engine="onnxruntime")`，避免每任务重载
- `_providers` 注册 `"paddle"`；`app/config.py` 默认 `OCR_SHEET_PROVIDER="paddle"`；`.env` 同步改
- verify: `python -c "from app.services.ocr_mineru import get_ocr_provider; r=get_ocr_provider().extract('samples/web/kaiti_sheet.png'); print(r)"` 输出学号/答案与实测一致

### a2. 正则层加固（楷体实测暴露）
- `ocr_mineru.py` `_HEADER_RE` 补词：`选择题|非选择题|答题卡|注意事项|请在|作答`
- `_NAME_RE` 加负向前瞻防吞标签：`姓名[：:\s]*([\u4e00-\u9fff]{2,4})(?!学|班|考)`
- verify: `tests/test_ocr_extraction.py` 全绿 + 楷体样本 name=张伟（非"张伟学号"）

### a3. 调度器
- 不动。5s 轮询 + 串行，7s/张，10 张 ≈ 70s，可接受。

### a4. 空文本/漏检兜底
- 0 文本框 → 任务 failed 带错误信息（现状已有）
- 低置信/缺答案任务：可开关地调一次 `llm_service.analyze_paper_with_vision("answer_sheet")` 单卡视觉复核（默认开，开关入 config）
- verify: 楷体样本 9-12 题漏检场景下，视觉复核能补回答案

## 阶段 b — 判分流程补入口

### b1. 前端批改区（`frontend/pages/ocr-sheets.html`）
- 答案输入 textarea（"1.A 2.B" 每行/每题）
- 关联考试下拉（可选，复用已有考试列表接口）
- 按钮：开始批改 / 确认保存
- verify: 手工走通 上传→识别→贴答案→批改→确认→保存

### b2. HTTP 端点（现在判卷/保存只有 Agent 对话入口）
- `POST /api/ocr/grading/grade`：包装 `grade_batch_answers`，接收 `batch_id + correct_answers`（JSON）或 `exam_id`
- `POST /api/ocr/grading/save`：包装现有保存逻辑（复用 `save_grading_results` 的 exam_id 校验 + 诊断触发）
- Agent 工具 `grade_answer_sheets`/`save_grading_results` 保留，底层共用
- verify: curl 调端点返回逐学生分数；保存后 StudentAnswer 落库 + 诊断触发

### b3. 答案解析 + mimo 判分
- UI 文本用**确定性解析器**（按行/正则拆 `correct_answers` JSON），不走 LLM
- `llm_grading._semantic_judge_card` 判定 LLM `provider="mimo"`（降级 dashscope/deepseek）
- 语义判定 prompt 补："OCR 常见的 0/O、l/I 混淆、上下标形式差异不计错"
- verify: ✅ **已用真实 mimo 通过**（2026-08-13）：楷体样本 q13 `Cu + 2H2S04(浓) 加热生成 CuS04 + S02气体 + 2H20` vs 标准 `Cu + 2H2SO4(浓) 加热生成 CuSO4 + SO2气体 + 2H2O`、q15 `2KCI03...2KCI + 302` vs `2KClO3...2KCl + 3O2` 均判等价，11/11 全对。验证脚本 `.scratch/ocr-grading-fix/samples/real_mimo_grading.py`

### b4. 保存/诊断衔接（UI 化已有逻辑）
- 批改出分**不要求**关联考试；**保存必须关联真实考试**（exam_id 校验已有），保存后触发 barrier 诊断
- verify: 无 exam_id 保存返回明确错误；有 exam_id 保存后诊断记录生成

## 已确认决策（2026-08-13 grilling）

1. **mimo 判分主模型**：`_semantic_judge_card` provider="mimo"，失败降级 dashscope/deepseek
2. **保存必须关联考试**：接受（与 `save_grading_results` 现状一致）
3. **低置信卡 mimo 视觉复核**：接受，默认开

## Out of scope

- 端到端 VLM 判分（图直接出分）——不做主路
- 答案图片上传（老师拍答案纸）——先不做
- 调度器并行化/吞吐优化——7s/张已够
- 生产部署（Docker/密钥）——已有框架

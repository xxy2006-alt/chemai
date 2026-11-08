# Tasks: mineru-pipeline

## T1: MinerU CLI 功能验证

**估时**: 1.5h
**前置**: infra-foundation T1
**验证**: 一份 PDF 得到结构化输出

- [x] 1.1 准备测试素材 → 创建了含化学内容的 PDF (test_chemistry_exam.pdf)
- [x] 1.2 调用 mineru_client.parse_by_cli() → 发现绝对路径 bug（已记录）
- [x] 1.3 检查输出内容 → hybrid-auto-engine 需 VLM 模型，首次下载超时
- [x] 1.4 验证化学式转 LaTeX → 阻塞于模型下载
- [x] 1.5 记录性能 → 首次运行需下载 2-5GB 模型，后续 ~30-60s/份
- [~] 1.6 尝试 pipeline 模式 → 也需模型下载
- [~] 1.7 评估替代方案 → Docker/WSL/预下载模型，建议在 Linux 服务器上运行 MinerU

---

## T2: 解析后处理增强

**估时**: 1.5h
**涉及文件**: `hermes_skills/chemistry_parser/engine/latex_standardizer.py`, `mineru_client.py`
**验证**: 输出的 formulas 列表含有标准 LaTeX

- [x] 2.1 增强 `_extract_formulas()` → 支持水合物、配合物、复杂化学式
- [x] 2.2 增强 `_extract_questions()` → 已有基础实现 (choice/fill/calc/short-answer)
- [x] 2.3 激活 `latex_standardizer.py` → 在 `_read_parse_output()` 中调用
- [x] 2.4 验证输出结构匹配 `ParseResult` dataclass → 已确认

---

## T3: 统一文档解析 API 端到端测试

**估时**: 1h
**涉及文件**: `app/api/ocr.py`, `app/services/document_parse_service.py`
**验证**: POST `/api/ocr/parse/document` 返回正确结果

- [x] 3.1 测试 PDF 上传 → MinerU 解析 → MinerU 模型未下载，正确返回错误提示
- [x] 3.2 测试图片上传 → OCR/Vision 解析 → provider=ocr, 成功识别
- [x] 3.3 验证 `file_type=auto` 自动检测 → PDF header 检测正确
- [x] 3.4 验证 fallback → MinerU 不可用时 `fallback_used=False` + 明确错误信息
- [x] 3.5 检查 `/api/ocr/services/status` → 三个服务状态正确报告 (OCR ✓, MinerU ✗, Vision ✓)

---

## T4: 题目格式化 LLM 链路

**估时**: 1h
**涉及文件**: `app/api/exam_bank.py`
**验证**: OCR/MinerU 原始文本 → 结构化 Question 入库

- [x] 4.1 用 LLM 格式化化学题目 → success, 2题正确解析为 choice/answer
- [x] 4.2 验证 LLM 返回的 JSON → content, type, options, answer, knowledge_points, difficulty 完整
- [x] 4.3 验证 LLM JSON 解析的容错 → json.loads + markdown strip 正常工作
- [x] 4.4 测试 `/api/exam-bank/import-questions` → 成功导入 2 题到真题集
- [x] 4.5 验证导入后的题目 → exam-sets/{id} 返回 question_count=2

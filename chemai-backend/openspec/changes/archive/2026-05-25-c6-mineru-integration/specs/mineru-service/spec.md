## ADDED Requirements

### Requirement: MinerU 客户端封装
系统 SHALL 提供 `MinerUClient` 类，通过 HTTP 调用 MinerU Docker 服务，上传 PDF 并返回结构化解析结果。

#### Scenario: 提取试卷题目
- **WHEN** 调用 `client.extract_questions(pdf_path)`
- **THEN** 返回题目列表 `[{"number": "T1", "content": "...", "options": [...], "answer": "A"}, ...]`

#### Scenario: MinerU 不可用
- **WHEN** MinerU Docker 容器未启动
- **THEN** 返回明确错误 `{"success": false, "error": "MinerU 服务不可用"}`

#### Scenario: PDF 解析超时
- **WHEN** PDF 处理超过 120 秒
- **THEN** 抛出 `MinerUTimeoutError`，建议分批处理

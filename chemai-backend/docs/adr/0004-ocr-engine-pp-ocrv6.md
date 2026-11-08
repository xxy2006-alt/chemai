# ADR-0004: 答题卡 OCR 引擎改用 PP-OCRv6_small（本地开源）

**Date**: 2026-08-13
**Status**: Accepted（真实手写验收后移 pilot 补测）

## Context

答题卡批量判卷管线（上传 → `ocr_scheduler` → OCR 引擎 → `llm_grading` 判卷 → 保存/诊断）的 OCR 引擎经历了两轮反复：

- **MinerU**（本地）：CPU-only 单张 >10min，2026-08-08 真实手写答题卡实测**零文本**，被判出局。
- **百度手写文字识别 API**（付费）：接回后代码通路已验证，但**账号无余额、从未真实跑通过**；且仓库里唯一一张"真实手写样本"经 PP-OCRv6 识别后真相为**土耳其机读答题卡照片**（`T.C. İNKILAP TARİHİ / MATEMATİK / FEN BİLİMLERİ`），并非中文手写。

2026-08-13 对 PP-OCRv6_small（百度飞桨开源、7.7M 参数、含手写训练）做实测，数据如下。

## Decision

**PP-OCRv6_small（onnxruntime 引擎）作为答题卡唯一 OCR 引擎。**
- 新增 `PaddleOCRProvider`，复用现有 `_extract_student`/`_extract_answers` 正则层。
- `OCR_SHEET_PROVIDER=paddle`（`.env` + `app/config.py` 默认值）。
- `MinerUProvider` / `BaiduOCRProvider` 类保留但不启用；Provider 抽象不变，换引擎只改一行。

## Evidence（2026-08-13 实测）

| 样本 | 结果 |
|------|------|
| 土耳其机读卡照片（原"真实手写样本"） | 读出 307 个文本区（MinerU 同图零文本）。证明"照片能读出文本"，非中文手写 |
| 楷体合成中文化学答题卡（已知答案） | 学号 ✓、选择题 1-7 ✓、非选 14 ✓；暴露 3 问题：整行漏检、化学式 0/O 与 l/I 混淆、正则吞"学号"/小节标题粘题 |
| 2024 安徽化学真题卷扫描件 | 47 文本区，化学式 `C60H90O4` 等保持字母 O |
| 2022 全国甲卷扫描件 | 35 文本区，题干识别良好 |

性能：CPU 单张 900×601 约 **7s**（含文档预处理），比 MinerU 快两个数量级。模型自动下载（det 9.4MB + rec 20.2MB），`pip install paddleocr` 即可，无需 paddlepaddle 全量安装。

## Alternatives Considered

- **百度手写 API**：付费、未实测、账号无余额。保留 Provider 类，不启用。
- **MinerU**：CPU 过慢、真实手写零文本。保留仅打印体场景，不进答题卡管线。
- **端到端 VLM 判分**（`analyze_paper_with_vision("answer_sheet")` 直接图出分）：成本/延迟高（每卡一次图像 token 调用 + 30s），且 mimo 复杂 JSON 已知慢/偶发空。**不做主路**，仅作低置信单卡视觉复核兜底（见计划 b/a4）。

## Consequences

- **Positive**：免费、本地、无外部依赖；吞吐从"1 任务/数十分钟"降到 ~7s/张。
- **Positive**：Provider 抽象保留，引擎切换成本一行。
- **Negative**：真实潦草手写准确率未在本机验证（用户无样本存档），验收后移 school pilot；低置信留空待老师确认的流程必须保留。
- **Negative**：化学式 0/O、l/I 混淆真实存在（`H2SO4→H2S04`、`KClO3→KCI03`），由判分语义层兜底，不在归一化层做全局替换（避免伤学号等纯数字）。
- **Negative**：整行漏检偶发（楷体合成第 3 行 9-12 题整行消失），以"0 答案/低置信 → failed 或 mimo 视觉复核"兜底。

# Proposal: mineru-pipeline

## Summary

打通 MinerU 文档解析 → 题目格式化 → 入库的完整流水线，实现"真题 PDF 一键录入"的核心差异化能力。

## Motivation

MinerU 是 ChemAI v2.0 的核心差异化组件（Product Spec v2.0 定义），能将历年高考真题 PDF 中的化学式自动转为标准 LaTeX。当前：
- `mineru_client.py` 代码完整但未跑过真实 PDF
- `document_parse_service.py` 框架就绪但未端到端测试
- `exam_bank.py` 的 `/format-questions` LLM 格式化链路未验证

## Scope

- `hermes_skills/chemistry_parser/mineru_client.py` — 验证 CLI 调用
- `app/services/document_parse_service.py` — 端到端测试
- `app/api/exam_bank.py` — 格式化 + 入库链路
- `app/api/ocr.py` — `/parse/document` 统一入口验证

## Dependencies

依赖 `infra-foundation` T1 (MinerU 依赖安装)

## Acceptance

- [ ] 用真实高考化学试卷 PDF 测试 MinerU CLI，得到 md_content + formulas + questions
- [ ] LaTeX 公式质量合格（如 Ca(OH)₂ → Ca(OH)_2 保留）
- [ ] `/api/ocr/parse/document` 统一入口工作，自动选 provider
- [ ] `/api/exam-bank/format-questions` LLM 格式化链跑通
- [ ] 完整链路：PDF 上传 → 解析 → 题目入库 → 可被出题时关联引用

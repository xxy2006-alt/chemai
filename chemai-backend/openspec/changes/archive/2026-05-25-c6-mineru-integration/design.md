## Context

MinerU 官方提供 Docker 镜像，通过 HTTP API 暴露 PDF 解析能力。ChemAI 通过 `MinerUClient` 封装 HTTP 调用，不依赖进程内 import。

## Goals / Non-Goals

**Goals:**
- Docker Compose 一键启动 MinerU + ChemAI
- `MinerUClient.extract_questions(pdf_path)` 返回结构化题目列表
- 错误处理：加密 PDF、扫描质量差、超时

**Non-Goals:**
- 不做 MinerU 源码修改
- 不做 GPU 加速配置（CPU 够用）

## Decisions

1. **Docker 独立部署，HTTP 调用** — 解耦，MinerU 升级不影响 ChemAI
2. **不 import mineru 库** — 避免 Python 依赖冲突

## Risks

- [MinerU 大 PDF 超时] → 异步任务队列（后续），当前 120s 超时

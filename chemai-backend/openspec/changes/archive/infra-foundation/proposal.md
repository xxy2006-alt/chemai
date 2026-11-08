# Proposal: infra-foundation

## Summary

修复基础设施层的 4 个关键问题，让所有技术组件能正常启动和调用。

## Motivation

当前项目整体架构完整，但存在以下阻塞性问题：

1. **MinerU 依赖未安装** — 源码已下载但 20+ Python 包缺失，是 v2.0 文档解析能力的最大缺口
2. **LLM 调用方式脆弱** — 使用 `subprocess.run(["curl", ...])` 而非 httpx 直接调用，Windows 兼容性差，无重试
3. **OCR 端点未验证** — 智谱 OCR API 端点从未用真实图片测试过
4. **启动时报错** — APScheduler 找不到 ReviewTask 模型，ChromaDB telemetry 警告

## Scope

- `app/services/llm_service.py` — curl → httpx 改造
- `app/services/ocr_service.py` — 端点验证 + fallback 完善
- `app/main.py` — 启动报错修复
- `MinerU-master/` — pip install -e .

## Dependencies

无 — 这是第一个 change，不依赖其他。

## Acceptance

- [ ] `pip install -e .` 在 MinerU 目录成功
- [ ] LLM 调用从 httpx 发出，不依赖系统 curl
- [ ] OCR + LLM Vision 两张网都能通（用真实图片测试）
- [ ] 服务启动无 error 日志（warning 可接受）

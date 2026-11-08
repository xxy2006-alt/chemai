## Context

当前 `app/services/llm_service.py` 用 `subprocess.run(["curl", "-s", "-k", ...])` 调 LLM API。每次调用 fork 进程，无连接复用，无结构化重试。需要替换为 `httpx.AsyncClient`，同时抽出 Provider 抽象层支持多模型切换。

目标模型分工：
- DeepSeek V4 Flash → 纯文本主力
- GLM-4.6V-FlashX → 多模态（图片输入）
- GLM-4-Flash → 智谱文本备用
- Qwen-turbo → DashScope 备用

## Goals / Non-Goals

**Goals:**
- 统一的 `LLMProvider` 接口：`chat()` + `chat_stream()`
- httpx 连接池复用，3 次重试 + 指数退避
- 三个 Provider 全部可独立运行
- 支持 OpenAI function calling 格式的 tools 参数

**Non-Goals:**
- 不做模型自动 fallback（由上层 ChemAgent 决策）
- 不做 token 计费统计
- 不做请求缓存

## Decisions

1. **httpx.AsyncClient 而非 aiohttp** — httpx 已在项目依赖中（0.28.1），API 更简洁
2. **每个 Provider 一个类，而非工厂模式** — 三个 API 的认证方式、base_url、请求格式都不同，独立类更清晰
3. **chat_stream 返回 AsyncIterator[str]（SSE chunks）** — 不解析 SSE 流，原样透传，减少耦合
4. **tools 参数用 OpenAI function calling 格式** — DeepSeek 和智谱都兼容，通义千问也支持

## Risks / Trade-offs

- [DeepSeek API 格式不完全兼容 OpenAI] → 测试验证 function calling 格式，必要时做适配
- [智谱多模态模型 image_url 格式不同] → `zhipu.py` 中处理 `data:image/xxx;base64,` 格式转换
- [网络不稳定导致重试过多] → 仅对 429/5xx 重试，4xx 直接抛异常

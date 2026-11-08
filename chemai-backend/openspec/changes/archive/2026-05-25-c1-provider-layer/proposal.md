## Why

当前 `app/services/llm_service.py` 使用 `subprocess.run(["curl", ...])` 调用大模型 API——每次请求 fork 一个进程、无连接复用、无重试、无超时控制。同时支持 3 个模型（DeepSeek V4 Flash / 智谱 GLM-4.6V-FlashX / 通义千问 qwen-turbo），需要统一的调用接口，让 ChemAgent 可以按任务类型切换模型。

## What Changes

- 新增 `agent/provider/base.py` — LLMProvider 抽象基类，定义 `chat()` 和 `chat_stream()` 接口
- 新增 `agent/provider/deepseek.py` — DeepSeek V4 Flash，纯文本主力（答疑/出题/诊断/报告）
- 新增 `agent/provider/zhipu.py` — 智谱 GLM-4.6V-FlashX（多模态）+ GLM-4-Flash（文本备用），API Key 与 OCR 共用
- 新增 `agent/provider/dashscope.py` — 通义千问 qwen-turbo（备用）
- 统一使用 `httpx.AsyncClient`：连接池复用 + 3 次重试 + 指数退避 + 60s 超时
- **BREAKING**: `app/services/llm_service.py` 中 `subprocess.run(["curl", ...])` 调用将被替换

## Capabilities

### New Capabilities
- `llm-provider`: 统一 LLM 调用接口，支持多模型路由、流式/非流式、自动重试

### Modified Capabilities
- (无)

## Impact

- `app/services/llm_service.py` — 替换底层调用方式，保留业务 prompt 逻辑
- `agent/provider/` — 新增 4 个文件
- 依赖：`httpx`（已安装，版本 0.28.1）
- 环境变量：`DEEPSEEK_API_KEY`（新增）、`ZHIPU_API_KEY`（已有）、`DASHSCOPE_API_KEY`（已有）

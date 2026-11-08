## ADDED Requirements

### Requirement: LLMProvider 抽象接口
系统 SHALL 提供 `LLMProvider` 抽象基类，定义 `chat()` 和 `chat_stream()` 方法签名，以及 `model_name` 属性。所有 Provider 实现 MUST 继承此基类。

#### Scenario: Provider 实现 chat 方法
- **WHEN** 调用 `provider.chat(messages, temperature, max_tokens, tools)`
- **THEN** 返回 `ChatResult` 对象，包含 `content`、`tool_calls`、`usage`、`model` 字段

#### Scenario: Provider 实现 chat_stream 方法
- **WHEN** 调用 `provider.chat_stream(messages, temperature, max_tokens, tools)`
- **THEN** 返回 `AsyncIterator[str]`，yield SSE data chunks

### Requirement: DeepSeek Provider
系统 SHALL 提供 `DeepSeekProvider`，使用 `deepseek-v4-flash` 模型，通过 `https://api.deepseek.com/v1` 端点调用。

#### Scenario: 纯文本对话
- **WHEN** 调用 `DeepSeekProvider().chat([{"role":"user","content":"1+1=?"}])`
- **THEN** 返回内容包含正确答案

#### Scenario: API 调用失败自动重试
- **WHEN** API 返回 429（限流）或 5xx（服务端错误）
- **THEN** 自动重试，最多 3 次，每次间隔指数增长（1s/2s/4s）

### Requirement: 智谱 Provider
系统 SHALL 提供 `ZhipuProvider`，支持 `GLM-4.6V-FlashX`（多模态）和 `GLM-4-Flash`（文本），通过 `https://open.bigmodel.cn/api/paas/v4` 端点调用。API Key 与现有 OCR 服务共用 `ZHIPU_API_KEY`。

#### Scenario: 多模态图片输入
- **WHEN** 消息中包含 `image_url` 类型的内容块
- **THEN** 智谱正确解析图片并返回文本分析结果

#### Scenario: 文本对话
- **WHEN** 仅传入文本消息
- **THEN** 返回正确的文本回复

### Requirement: DashScope Provider（备用）
系统 SHALL 保留 `DashScopeProvider`，使用 `qwen-turbo` 模型，通过 DashScope compatible-mode 端点调用。使用已有 `DASHSCOPE_API_KEY`。

#### Scenario: 文本生成
- **WHEN** 调用 `DashScopeProvider().chat(messages)`
- **THEN** 返回正确的文本回复

### Requirement: 连接池复用和超时控制
所有 Provider MUST 使用 `httpx.AsyncClient` 实现连接池复用，超时设置为 60 秒。4xx 客户端错误 MUST 不重试，直接抛出 `ProviderError`。

#### Scenario: 4xx 错误不重试
- **WHEN** API 返回 400（请求错误）
- **THEN** 不重试，立即抛出 `ProviderError` 异常

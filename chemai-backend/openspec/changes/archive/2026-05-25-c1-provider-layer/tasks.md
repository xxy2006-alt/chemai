## 1. 基础设施

- [ ] 1.1 创建 `agent/provider/` 目录结构（`__init__.py`）
- [ ] 1.2 实现 `base.py` — `LLMProvider` 抽象类 + `ChatResult` 数据类 + `ProviderError` 异常类

## 2. DeepSeek Provider

- [ ] 2.1 实现 `deepseek.py` — `DeepSeekProvider(LLMProvider)`，模型 `deepseek-v4-flash`
- [ ] 2.2 实现 `chat()` 非流式调用，3 次重试 + 指数退避
- [ ] 2.3 实现 `chat_stream()` 流式调用，SSE 透传
- [ ] 2.4 验证：`curl` 测试或单元测试确认返回正确回答

## 3. 智谱 Provider

- [ ] 3.1 实现 `zhipu.py` — `ZhipuProvider(LLMProvider)`，支持 `GLM-4.6V-FlashX`（多模态）和 `GLM-4-Flash`（文本）
- [ ] 3.2 处理多模态 image_url 格式（`data:image/xxx;base64,`）
- [ ] 3.3 实现 `chat()` + `chat_stream()`，重试逻辑
- [ ] 3.4 验证：文本调用和多模态调用均正确返回

## 4. DashScope Provider（备用）

- [ ] 4.1 实现 `dashscope.py` — `DashScopeProvider(LLMProvider)`，模型 `qwen-turbo`
- [ ] 4.2 实现 `chat()` + `chat_stream()`
- [ ] 4.3 验证：确认现有 DASHSCOPE_API_KEY 可用

## 5. 集成验证

- [ ] 5.1 确认三个 Provider 的 `chat()` 均可独立调用
- [ ] 5.2 确认流式 `chat_stream()` 均可正常 SSE 输出
- [ ] 5.3 确认 4xx 错误不重试，5xx/429 重试正确

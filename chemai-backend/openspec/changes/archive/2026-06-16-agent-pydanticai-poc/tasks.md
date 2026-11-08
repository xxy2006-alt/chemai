## 1. 环境准备（15 min，无依赖）

- [x] 1.1 `pip install pydantic-ai` 安装框架（锁定版本）
- [x] 1.2 配置 DeepSeek provider: `Agent('deepseek:deepseek-chat', ...)`
- [x] 1.3 验证 DeepSeek 基础连接：`agent.run_sync('Hello')` 返回正常响应

## 2. search_exam_bank 迁移（30 min，依赖 §1）

- [x] 2.1 创建 `agent/skills/search_pydantic.py`
- [x] 2.2 用 `@agent.tool` 装饰器实现 `search_exam_bank_pydantic`
- [x] 2.3 对比 `search.py` 和 `search_pydantic.py` 的差异行数，记录迁移模式

## 3. Agent + SSE 适配层（45 min，依赖 §2）

- [x] 3.1 创建 `agent/pydantic_agent.py`
- [ ] 3.2 实现 `event_stream_handler` → SSE 事件映射 -- **阻塞**: pydantic-ai 0.0.10 无 stream_events()
- [x] 3.3 新增 `POST /api/agent/chat/pydantic` 端点
- [x] 3.4 手动测试：文本流式输出正常，tool_call 事件无法测试（版本限制）

## 4. 评估与文档（30 min，依赖 §1-3）

- [x] 4.1 记录 skill 迁移工作量（行数变化、新增/删除的模式）
- [x] 4.2 记录事件映射的完整度和缺口（哪些 SSE 事件无法映射）
- [ ] 4.3 A/B 对比：暂跳过（版本限制，需 >=0.1.0 才能做完整对比）
- [x] 4.4 写出 PoC 结论报告

## Context

当前 ChemAI 有 `web_search` 工具（通过 MiMo API 搜索），但没有真正的浏览器交互能力。需要新增一个浏览器专家 sub-agent，集成到现有的 multi-agent StateGraph 中。

## Goals / Non-Goals

**Goals:**
- 实现 5 个 Playwright 浏览器工具
- 新增 browser_expert sub-agent node
- 将 browser_expert 集成到 coordinator 路由中
- 并发安全的 browser pool

**Non-Goals:**
- 不改 coordinator/router 架构
- 不在 browser agent 中实现文件下载
- 不支持 WebSocket 或 video/audio 流

## Decisions

### D1: Per-process browser pool with asyncio.Lock

模块级 `_browser_instance` + `_page_instance`，`asyncio.Lock` 序列化并发访问。idle 60s 自动关闭。

**Why:** 复用 browser 实例避免每次 3s 冷启动。Lock 防止并发请求的页面操作互相干扰。60s 超时在有持续流量时保持 browser 存活，闲时释放资源。

### D2: Browser expert 作为独立 sub-agent

不把 browser tools 塞进 search_expert。Browser 操作有自己的 ReAct 逻辑（导航→阅读→点击→截图），应该独立决策。

**Why:** 分离关注点。搜索 agent 返回结果文本，浏览器 agent 返回页面内容/截图/操作序列结果。

### D3: 工具返回 JSON，不返回 raw HTML

每个工具函数返回结构化的 JSON 结果（title + text + url 等），而不是 raw HTML。文本截断到 8000 字符。

**Why:** LLM 上下文有限，raw HTML 浪费 token。结构化结果更容易被 browser_expert 的 ReAct 循环处理。

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| Playwright 安装失败 | 部署脚本在 `pip install` 后执行 `playwright install chromium` |
| Browser 内存泄漏 | idle 60s 自动关闭 + process cleanup |
| 并发请求排队（Lock 瓶颈）| 高并发场景下可改为 per-request browser 实例 |
| 页面加载超时 | 每个操作设 timeout=30s，超时返回错误 JSON |

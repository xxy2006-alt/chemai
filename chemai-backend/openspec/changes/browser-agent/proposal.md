## Why

Agent 需要能驱动浏览器完成完整网页交互。当前只有 `web_search`（通过 MiMo API 搜索），无法处理需要点击、填表、截图的场景——比如搜索高考政策页面后提取指定段落、在题库网站上搜索并提取题目。

## What Changes

- 新增 `agent/browser_tools.py` — 5 个 Playwright 工具
- 新增 `sub-agent-browser` spec — 浏览器专家 sub-agent
- `requirements.txt` 添加 `playwright`
- 不改变现有 graph 结构（浏览器 agent 作为第 6 个 sub-agent node 集成到 multi-agent-architecture 的 graph 中）

## Capabilities

### New Capabilities
- `sub-agent-browser`: 浏览器专家 sub-agent — browse_navigate, browse_click, browse_input, browse_read, browse_screenshot
- `browser-tools`: Playwright 工具实现 — module-level browser pool with asyncio.Lock + idle timeout

### Modified Capabilities
- `multi-agent-coordinator`: RoutingDecision agent 选项增加 "browser_expert"


## Impact

- `agent/browser_tools.py` — 新增（~120 行）
- `agent/langgraph_agent.py` — 新增 browser_expert node + coordinator prompt 更新（~20 行）
- `requirements.txt` — 添加 `playwright`
- 部署脚本 — 添加 `playwright install chromium`

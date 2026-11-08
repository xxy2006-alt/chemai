# 06 · CHEMAI 开发实施全流程

## 实际时间线（按 git log 还原）

```bash
git log --oneline --reverse
```

共 32 个提交，覆盖 8 周。

### Week 1（1月7-13日）：环境搭建 + LLM 接入 + 第一轮访谈

**Day 1（1月7日）**
- `pip install fastapi uvicorn sqlalchemy python-dotenv httpx pydantic`
- 创建项目骨架：`app/main.py`、`app/core/config.py`、`chemai.py`
- 第一个路由：`@app.get("/")` → `FileResponse("frontend/index.html")`，返回 200
- 环境变量：`CHEMAI_PORT=8001`、`DEEPSEEK_API_KEY=sk-...` 写入 `.env`

**Day 2（1月8日）**
- `app/services/llm_service.py:72-99`：第一个 `generate_text()` 方法
- Provider 优先级：MiMo → DashScope → DeepSeek
- 第一条测试："配平 Fe + O2 = Fe2O3"，DeepSeek 返回正确

**Day 3（1月9日）**
- `app/services/ocr_service.py`：Baidu OCR 集成
- 测试：拍高考化学试卷，识字率约 80% 但化学式全部丢失
- 结论：Baidu OCR 不适合化学试卷，需要专门方案

**Day 4-5（1月10-13日）**
- 第一轮用户访谈（角色扮演式）
- 输出 `化学教师AI辅助教学访谈记录_角色扮演版.md`（约 3000 字）
- 核心发现：错题统计 1.5h/次、AI 出题后需验题 30min/次、90+ 人班无法个性化

### Week 2（1月14-20日）：OCR 管线 + 前端第一版

**Day 8（1月14日）**
- `app/api/ocr.py`：OCR API 端点
- `frontend/pages/ocr.html`：答题卡识别的上传页面
- `frontend/index.html`：AI 教研助手主页（基于 `Academic Catalyst` 设计系统）

**Day 9-10（1月15-17日）**
- `import_exam_papers.py`：Baidu OCR → LLM 解析 → JSON → DB 的全链路
- 第一卷测试：2020 全国卷 22 页，22 × 3s = 66 秒出结果
- 结果惨烈：只提取出 6 道题，LaTeX 全部丢失

**Day 11-12（1月18-19日）**
- 决定换 OCR 引擎。调研 MinerU vs Qwen-VL-OCR
- 最终选 MinerU v3.4 pipeline
- `download_mineru_models.py`：下载 7 个 pipeline 模型

**Day 13（1月20日）**
- POC 测试：MinerU 处理 2020 卷，12/12 题完整提取，LaTeX 全保留
- `test_mineru_2020.py`（第一期测试脚本）
- 踩坑：Windows multiprocessing → `if __name__ == '__main__'`

### Week 3-4（1月21日-2月4日）：Agent v1 → v2

**Week 3**
- 接入 pydantic-ai，写第一个 Agent
- 问题：单轮调用不支持多步骤工具链，经常漏调工具

**Week 4**
- 发布 8bba4e9 `前端重设计 — 5页面精简架构`：删 177+ 旧前端文件，重建 6 页面
- 开始调研 LangGraph：`pip install langgraph langgraph-checkpoint-sqlite`

### Week 5-6（2月5-25日）：Agent v3 + Multi-Agent

**Day 32（2月15日）**
- `agent/langgraph_agent.py`：第一个 LangGraph ReAct Agent
- 14 个工具注册，协调器 + LLM 路由

**Day 38（2月20日）**
- Multi-Agent StateGraph 完成：1 协调器 + 6 子专家
- Gateway 关键词路由（`agent/gateway.py:245-289`）
- 14 skills registered: `[Agent] 14 skills registered: search_exam_bank, web_search...`

**Day 40（2月23日）**
- 提交 824c2c6 `前端完全重做 — 完美还原 Academic Catalyst 设计系统`
- 删除了旧学生端 1866 行代码（`frontend/src/modules/student/`）
- 新增 21 个文件（含 6 个教师端页面）

### Week 7-8（2月26日-3月29日）：生产加固 + 新需求

**3月15日**：教导主任提出变种真题需求
**3月25日**：MinerU 2020 卷导入完成（12 题/115 分）
**3月27日**：`architecture-review-ocr-final.html` 架构评审
**3月28日**：前端渲染修复（KaTeX + marked + 图片路径）
**3月29日**：学生端移动端重建（`frontend/m/` + 对话持久化 + Persona 修复）

## 关键决策时间线

| 日期 | 决策 | 影响 |
|------|------|------|
| 1月7日 | SQLite（非 PostgreSQL）| 零运维，单文件备份 |
| 1月18日 | MinerU（非 Baidu/Qwen OCR）| 准确率 100% vs 50% |
| 2月20日 | LangGraph Multi-Agent（非 pydantic-ai）| 路由准确率 100% vs 70% |
| 3月29日 | AsyncSqliteSaver（非 MemorySaver）| 对话持久化 |

### 完整 Git 提交历史（2026-01 至 2026-03）

```bash
git log --oneline --reverse
```

共 40+ 个提交，按主题分组：

**基础架构（1 月）**
- `892ce30 v1.0.0: 初始版本 - 邵阳县第一中学演示数据完成`
- `dee2be0 feat: ChemAgent v2.0 — AI 化学教学 Agent + 前后端完整修复`

**前端重设计（2 月）**
- `824c2c6 feat: 前端完全重做 — 完美还原 Academic Catalyst 设计系统`（删 177+ 旧文件，新增 21 文件）
- `8bba4e9 feat: 前端重设计 — 5页面精简架构 + Agent性能优化 + 视觉升级`
- `94ea667 feat: MiMo-V2.5 全模态模型接入 + Agent 工具调用 + 前端重设计`

**Agent 架构演进（2-3 月）**
- `9445551 fix: add console.error to SSE catch block for debugging`
- `a12abcf fix: handle [DONE] before JSON.parse, remove orphaned catch`
- `49dc2b2 fix: bubble.innerHTML wiped inline panel — use insertAdjacentHTML instead`
- `3bc48c3 fix: flatten grouped papers API response + remove debug logs`
- `3386156 fix(panel): CSS + 3-phase progress + historical API + save feedback + markdown`
- `f80933e feat(sse): add route/sub_agent_start/subagent_text/sub_agent_end SSE events`
- `1f17011 feat(inline): add show_students tool + student-list component, remove page nav`
- `6fae687 fix(agent): fix routing for class/student queries + limit show_students calls`
- `3483796 fix(tools): flexible class name matching in show_students`

**体验修复（3 月）**
- `302f470 fix: pass sub-agent result directly instead of coordinator re-generating`
- `f820595 fix: suppress coordinator chatter before route + relax sub-agent output format`
- `f214c8e fix(gateway): remove "看看" from navigate trigger — too broad`

### 每个提交的代码行数变化

```bash
git diff --stat HEAD~40..HEAD
```

累加约 5000 行新增代码（不含自动生成和 CDN 依赖）。Python 约 2500 行（app/ + agent/），前端 HTML/JS/CSS 约 2000 行（frontend/），配置文件约 500 行。

## 每次提交的实际代码量

```bash
git diff --stat HEAD~32..HEAD
```
























































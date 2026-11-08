# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

## ChemAI 项目架构

### Agent 层 (LangGraph)

**v2 (推荐)**: `agent/langgraph_agent_v2.py` — 单 ReAct agent，所有工具直接可见，基于 docstring 选择工具。

```python
from agent.langgraph_agent_v2 import create_chemai_agent

agent, guard_state = await create_chemai_agent(persona="tutor", provider="deepseek")
result = await agent.ainvoke(
    {"messages": [{"role": "user", "content": "你好"}]},
    config={"configurable": {"thread_id": "conv-123"}, "recursion_limit": 12},
)
```

**v1 (fallback)**: `agent/langgraph_agent.py` — 多 Agent 架构（Coordinator + Router + 6 子Agent），保留作为回退。

**核心文件：**
- `agent/langgraph_agent_v2.py` — v2 单 Agent 工厂 + GuardState 护栏
- `agent/langgraph_sse_v2.py` — v2 SSE 适配器（简化，无 sub_agent_depth）
- `agent/langgraph_agent.py` — v1 多 Agent 工厂（保留）
- `agent/langgraph_sse.py` — v1 SSE 适配器（保留）
- `agent/channel/langgraph_channel.py` — FastAPI 端点，通过 `version` 参数切换 v1/v2

**护栏 (D8/D9)：**
- `recursion_limit=12` — ReAct loop 最大迭代（v2）
- `GuardState` — per-invocation 共享状态：`seen_calls`（去重）、`approved`（requires_approval 检查）、`last_route`（_route 剥离后存储）
- 破坏性工具（`assign_adaptive_practice`, `delete_bank`）需要先调 `request_approval` 获得授权
- `_route` 字段在传给 LLM 前自动剥离

**端点：**
| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/agent/chat/langgraph/stream` | POST | 流式 SSE（`version: "v2"` 使用单Agent） |
| `/api/agent/chat/langgraph` | POST | 非流式 JSON |
| `/api/agent/chat/langgraph/resume` | POST | 中断恢复 |
| `/api/agent/chat/langgraph/reset` | POST | 重置对话 |
| `/api/agent/upload` | POST | 对话中上传文件（图片/PDF/Word）→ OCR 预览 + 操作建议（导入/批改/搜题） |
| `/api/agent/chat/conversations` | GET | 会话列表 |
| `/api/agent/chat/history/{thread_id}` | GET | 会话历史 |
| `/api/agent/chat/new` | POST | 新建会话 |
| `/api/agent/chat/conversations/{thread_id}` | DELETE | 删除会话 |

> 旧 pydantic-ai SSE 端点 `/api/agent/chat/stream`、`/api/agent/chat` 已随 pydantic-ai 移除（`fastapi_sse.py` 已删，不再注册）。对话管理 4 端点在 `app/main.py` 直接注册在 app 上。

### 测试

```bash
# 全部测试
python evals/test_langgraph_agent.py --all

# 单独模块
python evals/test_langgraph_agent.py --boundary   # 边界/护栏 (无 API)
python evals/test_langgraph_agent.py --golden     # Golden 数据集 (需 API)
python evals/test_langgraph_agent.py --langgraph  # LangGraph 特有场景 (需 API)
python evals/test_langgraph_agent.py --regression # 回归对比 (需 API)

# 完整测试套件
python evals/run_evals.py

# 回归测试：认证 + 数据可见性（每次更新后必跑）
# 覆盖「token 过期 → 学生/学情数据看起来消失」这类反复踩坑的回归
python -m pytest tests/test_regression_auth_data.py -q
```

> **更新后必跑**：任何后端/前端更新后，至少跑 `python -m pytest tests/ -q`（含上面的认证+数据可见性回归）。历史上多次出现「更新后 token 过期 → 学生/学情数据看起来全消失」，根因是认证 token 过期且前端无自动续期，已收敛为 `tests/test_regression_auth_data.py` 钉住（token 立即有效 / 有效 token 取到学生列表 / 数据跨重启仍在）。

### 数据库提交纪律 (chemai.db)

`chemai.db` 被 git 跟踪（演示数据入库的刻意设计），但它是 WAL 模式的活库：服务运行中的写入停在 `chemai.db-wal`，主文件要等 checkpoint 才更新。因此：

- **任何要提交 `chemai.db` 的场合，先跑 `python scripts/db_checkpoint.py`**（把 WAL 落盘再提交）
- `git stash` / 切分支 / checkout 涉及 `chemai.db` 前同理——否则主文件与残留 WAL 失配，打开即报 `database disk image is malformed`（2026-09-20 实际发生过，见 scripts/db_checkpoint.py 头注释）
- 库的表结构由服务启动时 `create_all` 重建、题库由 JSON 同步，空 schema ≠ 数据丢失，先起一次服务再判断

### 已知架构缺口 (known_gaps)

这些是测试中发现的已知问题，详见 `evals/agent_eval_golden.yaml` 的 `known_gaps` 部分：

| 缺口 | 严重度 | 描述 |
|------|--------|------|
| search-exam-bank 不读 SQLite | **high** | `search_exam_bank` 只读 JSON 文件，Agent 保存到题库的题目无法被搜索到 |
| ~~batch_import 方法缺失~~ | ✅ fixed | 已删除旧 `import_exam_paper` 工具，由 Baidu OCR pipeline 替代 |
| 不自动保存题目 | medium | `generate_questions` 不自动保存，依赖 LLM 记得调 `save_to_bank` |
| LLM 跳过 approval | medium | 即使明确要求确认，LLM 仍有概率不调 `request_approval` |
| _route 不持久化 | low | _route 数据通过 SSE 传递，前端未打开时丢失 |

### 工作流完整性 (workflow_scenarios)

`evals/agent_eval_golden.yaml` 新增 5 个 workflow 场景，覆盖：
- 空知识点 → 必须反问
- 出题（无学生）→ 生成 → 保存 → 跳转
- 出题（有学生）→ 生成 → 不保存
- 搜索后信息不足 → 反问
- save_to_bank → 跳转题库 tab

**后续更新时务必跑 `--workflow` 测试确保这些场景不被回归。**

---

## Health Stack

- typecheck: cd frontend && npx tsc --noEmit
- lint: ruff check .
- test: pytest && cd frontend && npx vitest run
- deadcode: none
- shell: none (shellcheck 未安装)
- gbrain: timeout 5s gbrain doctor --json
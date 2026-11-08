# Session 16 · 测试调优与Bug修复实战

## 产出物

- `evals/` 目录下的评测集脚本，用于 Agent 路由回归测试
- 5 个亲手修复的 bug（从 15 个真实 bug 中选取代表性的）
- `agent/tools.py` 中 `web_search` 的 Bing HTTP 直搜实现
- `agent/langgraph_agent.py` 中 AsyncSqliteSaver 懒加载方案
- `frontend/js/agent.js` 中 `renderChem` 的 marked v12 兼容修复
- `agent/tools.py` 中 `chemistry_tutor` 的 persona 分离方案
- 性能基准测试报告（curl 实测数据 + 瓶颈排名）

## 前置条件

- Session 15 完成，Agent 多智能体架构可用（Gateway + Router + 7 子专家）
- `evals/run_evals.py` 已创建（Session 15 中搭建的评测框架）
- Agent 可以通过用户输入正确路由到子专家
- `chemai.db` 和 `chemai_checkpoints.db` 存在且可读写

## 项目背景（给学生的概述）

前面 15 节课你把 ChemAI 从零搭了出来——FastAPI 骨架、LLM 接入、OCR 识别、Agent 架构、出题工作台、数据闭环。功能都写完了，但一用就发现问题：学生登录后对话区域一片空白，前端公式显示为原始 LaTeX 文本，服务重启后对话记录全丢，联网搜索居然说"2026 年还没到"。

这些不是"没写完"的问题——是"写完了但写错了"的问题。

真实软件工程中，bug 是常态。ChemAI 项目 1 月到 3 月共记录了 15 个真实 bug，从"加一行 JSON 字段就行"的简单修复，到"4 次尝试、2 小时"的硬骨头。这节课你要亲自动手修其中的 5 个，同时学会一套完整的调试方法论。

除了 bug 修复，这节课还要做性能摸底。ChemAI 的性能瓶颈不在代码——在外部 API 和模型推理。你会测量端到端延迟的每一层，找出 2.5-6 秒的总延迟到底花在哪。

这节课学完，你就知道"面向真实用户"的开发和"能跑就行"的开发的真正区别。

---

## 操作步骤

### 步骤 1：构造评测集脚本

**目标**：创建一个评测脚本，用 20 个 Golden 场景测试 Agent 路由准确率

**提示词**（复制到 Claude Code）：

```
在 chemai-backend 的 evals/ 目录下（如果不存在则创建），写一个路由评测脚本 run_evals.py。

这个脚本需要：
1. 定义 20 个 Golden 测试场景，每个场景包含：
   - user_input: 用户输入文本
   - expected_tool: 应该路由到的子专家名称（如 "chemistry_tutor"/"generate_questions"/"diagnose_barrier"/"search_exam_bank"等）
   - persona: 用户角色（"teacher"/"student"）

2. 场景覆盖范围（每类场景至少 2 个）：
   - 化学知识问答（氧化还原/离子反应/有机化学）
   - 出题请求（选择题/填空题/计算题）
   - 错题诊断（看答题记录/分析薄弱点）
   - 真题搜索（按年份/按知识点）
   - 学习建议（学习方法/复习策略）
   - 前沿知识（最新化学研究/诺贝尔奖相关）
   - 教师教研（考点分析/教学设计/学生误区）
   - 闲聊/边界（"你好"/"今天天气怎么样"）

3. 对每个场景：
   - 调用 Agent 的路由（gateway.classify()）
   - 对比 actual_tool 与 expected_tool
   - 计算准确率 = 正确的路由数 / 总数

4. 输出格式：
   - 每个场景一行：场景名 | 输入 | 期望 | 实际 | 通过/失败
   - 末尾：总准确率 XX/20 = XX%

5. 运行方式：python evals/run_evals.py

要求：脚本独立可运行，不依赖外部配置。如果 gateway.classify() 的接口你还不清楚，先读 agent/gateway.py 确认函数签名。
```

**验证**：
- [ ] `python evals/run_evals.py` 能运行
- [ ] 输出 20 个场景的逐个结果
- [ ] 末尾显示准确率（目标：20/20 = 100%）
- [ ] 如果准确率不是 100%，记录哪些场景路由错了

---

### 步骤 2：Agent 路由回归测试

**目标**：确保路由在 bug 修复前全线通过，作为回归基线

**提示词**（复制到 Claude Code）：

```
跑刚才写的 evals/run_evals.py。如果 20/20 全部通过，继续下一步。

如果有失败场景，分析原因：
- 是 gateway.classify() 的关键词匹配覆盖不全？
- 还是 prompt 中的 persona 影响了路由？

修复失败场景，直到 20/20 全部通过。

修复思路参考：
- gateway.py:174-289 中的关键词匹配逻辑，检查是否覆盖了失败场景的输入模式
- 如果是 persona 相关，检查 tools.py 中的子专家是否正确读取 _current_persona

最终目标：输出 "路由准确率：20/20 = 100.0%"
```

**验证**：
- [ ] `python evals/run_evals.py` 输出 20/20 = 100%
- [ ] git commit 保存这个干净的基线（message: "eval: Agent 路由回归基线 20/20"）

---

### 步骤 3：Bug 修复实战 — 前端渲染崩溃（marked API 兼容性）

**目标**：修复 `renderChem` 函数中 marked v12 API 变更导致的公式/图片不渲染

**背景**：考试工作台的历史真题页面，`$\mathrm{SO_2}$` 显示为原始 LaTeX 文本，图片不显示。原因是 `renderChem` 函数用了 `marked.setOptions()`——这个 API 在 marked v12 中已废弃，整段崩溃回退到纯文本渲染。这是典型的"静默失败"——不报错、不白屏、不崩溃，只是功能降级。

**提示词**（复制到 Claude Code）：

```
读 frontend/pages/exam-v2.html，找到 renderChem 函数（大约在 627 行）。

当前代码用了 marked.setOptions()，但这个方法在 marked v12 中已废弃。

请修复为：
1. 使用 marked.parse(text, {breaks: true, gfm: true}) 替代 marked.setOptions() + marked()
2. LaTeX 公式块（$$...$$ 和 $...$）先用占位符保护，再用 KaTeX 渲染，避免 marked 破坏 LaTeX 语法
3. 同理修复 frontend/js/agent.js 中的 renderChemistry 函数（大约在 952 行）

修复后检查：
- $\mathrm{SO_2}$ 应该渲染为数学公式
- 化学式 $\mathrm{H_2SO_4}$ 正确显示
- 图片正常显示
- 纯文本不受影响
```

**验证**：
- [ ] 打开考试工作台 → 历史真题 → 2020 全国卷 → 题目内容中公式正常渲染
- [ ] 图片正常显示
- [ ] 无浏览器控制台报错
- [ ] agent.js 的 renderChemistry 也同步修复

---

### 步骤 4：Bug 修复实战 — 对话历史持久化（AsyncSqliteSaver）

**目标**：将 Agent 对话从内存存储迁移到 SQLite 持久化存储

**背景**：这是 15 个 bug 中最硬的一个——花了 4 次尝试、约 2 小时。第一次用 `MemorySaver`（内存，重启即丢）；第二次换 `SqliteSaver`（不支持 async）；第三次换 `AsyncSqliteSaver`（asyncio.run() 冲突）；第四次终于找到方案——懒加载。

**提示词**（复制到 Claude Code）：

```
读 agent/langgraph_agent.py，找到 checkpointer 的初始化代码（大约在 16-24 行）。

当前用的是 MemorySaver——进程重启后所有对话历史丢失。需要改为 SQLite 持久化。

修复方案（这是真实项目经过 4 次尝试后的最终方案）：

```python
import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

_checkpointer = None

async def _get_checkpointer():
    global _checkpointer
    if _checkpointer is None:
        conn = await aiosqlite.connect("chemai_checkpoints.db")
        _checkpointer = AsyncSqliteSaver(conn)
    return _checkpointer
```

关键点：
1. 懒加载模式——不是每次请求创建新连接，首个请求初始化后缓存
2. 使用 aiosqlite（异步 SQLite），不是 sqlite3（同步）
3. 数据库文件 chemai_checkpoints.db 会自动创建（如果不存在）

修改所有使用 checkpointer 的地方，改为 `await _get_checkpointer()`。

确认：
- aiosqlite 已在 requirements.txt 中
- 如果缺少，运行 pip install aiosqlite
```

**验证**：
- [ ] 启动服务，进行一轮对话
- [ ] 重启服务（Ctrl+C 再 python chemai.py）
- [ ] 对话历史仍然存在（不会因重启丢失）
- [ ] 检查 `chemai_checkpoints.db` 文件是否已生成（`ls -lh chemai_checkpoints.db`）

---

### 步骤 5：Bug 修复实战 — 联网搜索时效性

**目标**：修复联网搜索回答"截至 2024 年，2026 年尚未到来"的问题

**背景**：问 2026 年的考试信息，MiMo 回答"截至 2024 年，2026 年尚未到来"。根因是 MiMo 的 `enable_search` 搜索确实执行了，但模型在系统 prompt 影响下追加了训练数据截止声明。修复方案：不使用 MiMo 内置搜索，改为 Bing HTTP 直搜 + DeepSeek 总结。

**提示词**（复制到 Claude Code）：

```
读 agent/tools.py，找到 web_search 函数的实现。

当前使用的是 MiMo 内置的 enable_search 参数，但搜索结果被模型的训练截止日期声明覆盖了。

请修复为两阶段方案：
1. 第一阶段 — Bing HTTP 搜索：用 httpx 直接请求 Bing 搜索 API（或使用 duckduckgo 的免费搜索），获取原始搜索结果
2. 第二阶段 — DeepSeek 总结：将搜索结果作为上下文，用 DeepSeek 提炼出含时效性信息的回答

伪代码：
```python
# Step 1: 搜索
search_results = await http_search(query)  # Bing/DDG HTTP
# Step 2: 总结
summary = await llm_service.generate_text(
    prompt=f"基于以下搜索结果回答问题（注意当前是 2026 年）：{search_results}\n问题：{query}"
)
```

如果 HTTP 搜索 API 不可用（如 Bing 需要 API key），fallback 方案：直接让 DeepSeek 使用 enable_search 参数，但 system prompt 中明确告知当前是 2026 年，不要用训练截止日期覆盖搜索结果。

修改完成后，用以下输入测试：
"2026 年的化学高考改革动向是什么？"
预期：不应出现"2026 年尚未到来"之类的回答。
```

**验证**：
- [ ] 问"2026 年的化学高考信息"不再回答"2026 年还没到"
- [ ] 联网搜索结果包含近期的网页信息
- [ ] 如果 Bing API 不可用，至少 DeepSeek fallback 不输出训练截止声明

---

### 步骤 6：Bug 修复实战 — persona 分离

**目标**：修复 Agent 把教师当学生教的 persona 混淆问题

**背景**：前端传了 `persona: "teacher"`，但 `chemistry_tutor` 仍用学生模式回答。根因是 LLM 调用工具时传 `persona="tutor"`（默认值），覆盖了 `_current_persona`。修复需要三步：全局变量 + fallback 逻辑 + 动态 prompt 编译。

**提示词**（复制到 Claude Code）：

```
读 agent/langgraph_agent.py 和 agent/tools.py。

问题：前端传 persona="teacher"，但 chemistry_tutor 仍用学生模式回答。

根因：LLM 调用工具时传 persona="tutor"（默认值），覆盖了 _current_persona。

三步修复：

1. agent/langgraph_agent.py 中加全局变量：
```python
_current_persona = "student"  # 默认学生
```

在 Agent 入口处（用户消息到达时），根据前端传入的 persona 更新：
```python
global _current_persona
_current_persona = request.persona if request.persona in ("teacher", "student") else "student"
```

2. agent/tools.py 的 chemistry_tutor 函数中加 fallback 逻辑：
```python
if persona in ("", "tutor", "auto"):
    # 读取全局变量作为兜底
    from agent.langgraph_agent import _current_persona
    persona = _current_persona
```

3. 子专家 prompt 改为动态编译——根据 persona 的值选择教师模式的 prompt 或学生模式的 prompt。

教师模式 prompt 特征：考点分析 + 教学策略 + 学生常见误区 + 课堂活动建议
学生模式 prompt 特征：引导式提问 + 不直接给答案 + 联系已有知识 + 鼓励性语言

测试方法：
- persona="teacher" 时问"氧化还原反应怎么讲"，应得到考点分析（不是单纯的知识讲解）
- persona="student" 时问"氧化还原反应怎么学"，应得到引导式讲解（不直接给结论）
```

**验证**：
- [ ] 教师模式：问"氧化还原反应怎么讲"，回答含"考点""学生误区""教学策略"等关键词
- [ ] 学生模式：问"氧化还原反应怎么学"，回答含引导式提问（"你想想..."）
- [ ] 两个模式不会互相混淆

---

### 步骤 7：Bug 修复实战 — 滚动定位错误

**目标**：修复新消息不自动滚动到底部的问题

**背景**：对话超过一屏后，新消息不自动滚动到底部。根因是 `scrollBottom()` 函数滚动了 `#chat-messages`，但 CSS overflow 在父层 `.chat-area`。这是一个经典的"选择器层级错误"——滚动对象和 overflow 容器不一致。

**提示词**（复制到 Claude Code）：

```
读 frontend/js/agent.js，找到 scrollBottom 函数（大约在 762 行）。

当前代码：
el = document.getElementById('chat-messages')
el.scrollTop = el.scrollHeight

问题：CSS overflow 设置在父层 .chat-area 上，不在 #chat-messages 上。
滚动 #chat-messages 没有效果——需要滚动的是 .chat-area。

修复：
```javascript
var el = document.querySelector('.chat-area') || document.getElementById('chat-messages');
if (el) {
    el.scrollTop = el.scrollHeight;
}
```

注意：用 querySelector 查找 .chat-area 作为首选，fallback 到 #chat-messages 保证向后兼容。

修复后测试：发送 10 条消息，检查是否始终自动滚到最新消息。
```

**验证**：
- [ ] 发送多轮对话后，页面始终滚动到底部显示最新消息
- [ ] 手动往上翻后，新的 AI 回复到来时自动滚回底部
- [ ] 不影响其他页面的滚动行为

---

### 步骤 8：性能基准测试

**目标**：用 curl 测量各端点的实际响应时间，拆解端到端延迟的每一层

**提示词**（复制到 Claude Code）：

```
在 chemai-backend 目录下，用 curl 测量以下端点的实际响应时间。

用 -w 参数获取精确耗时，格式：
curl -w "time_total: %{time_total}s\n" -o /dev/null -s <URL>

测试以下端点：
1. 首页：http://127.0.0.1:8001/
2. 考试工作台：http://127.0.0.1:8001/pages/exam-v2.html
3. 真题库 API：http://127.0.0.1:8001/api/exam-bank/historical?region=全国卷&year=2020&page_size=1
4. 练习任务 API：http://127.0.0.1:8001/api/practice/student/202610101/tasks

同时检查：
5. 数据库文件大小：ls -lh chemai.db
6. 对话 checkpoint 大小：ls -lh chemai_checkpoints.db

将结果整理成表格。

然后，基于以下端到端延迟拆解数据，写出完整的性能分析报告：

```
用户点击发送
  │ ~50ms  ─ 前端 fetch 请求构造 + DOM 更新
  │ ~15ms  ─ FastAPI 中间件（CORS + auth middleware）
  │ ~5ms   ─ Gateway classify() 关键词匹配
  │ ~200ms ─ 网络往返到 DeepSeek API
  │ ~2-5s  ─ LLM 推理（首 token）
  │ ~50ms/token ─ 后续 token（SSE 流式）
  │ ~10ms  ─ 前端 renderChem() 渲染
  │ ~5ms   ─ AsyncSqliteSaver 写入 checkpoint
  └ 总计: 2.5-6s（取决于回复长度）
```

分析结论：瓶颈在哪一层？占比多少？值不值得优化？

最终输出为一个性能基准报告，包含：
- curl 实测数据表
- 端到端延迟拆解表（标注瓶颈）
- 数据库大小
```

**验证**：
- [ ] curl 全部 4 个端点返回正常耗时（均 <0.1s）
- [ ] 性能分析报告指出 LLM 推理占端到端延迟的 >85%
- [ ] 数据库文件大小在合理范围内（<10MB）

---

## 发生了什么（教师参考）

### 1. 这 15 个 bug 是怎么来的

ChemAI 没有 QA 团队，没有自动化测试，所有 bug 都是开发者自测或种子教师反馈发现的。以下是完整记录：

| # | Bug | 发现日期 | 现象 | 根因 | 修复方法 | 代码变更 | 修复耗时 |
|---|-----|---------|------|------|---------|---------|---------|
| 1 | 2020 卷只导出 6 题 | 2月25日 | JSON 里只有 6 道题 | Baidu OCR 对化学式识别率极低 | OCR 管线迁移到 MinerU | `import_mineru_paper.py` | 数天 |
| 2 | 前端公式不渲染 | 3月28日 | $\mathrm{SO_2}$ 显示为原始文本 | marked.setOptions 在 v12 废弃 | marked.parse + KaTeX 保护 | `exam-v2.html:627` + `agent.js:952` | 30min |
| 3 | 加入考试后题目不显示 | 3月29日 | 考试列表 0 题 | API 返回 exam_id，前端读 question_id | 加一行 JSON 字段 | `exam_bank.py:485` | 10min |
| 4 | 对话历史丢失 | 3月29日 | 重启后对话消失 | MemorySaver 只在内存中 | 4 次尝试 → AsyncSqliteSaver 懒加载 | `langgraph_agent.py:16-24` | 2h |
| 5 | 学生端对话空白 | 3月29日 | 对话区域无内容 | scrollBottom 滚错元素 | 选择器改为 .chat-area | `agent.js:762` | 5min |
| 6 | 联网搜索时效性 | 3月29日 | 回答"2026 年尚未到来" | MiMo 训练截止声明覆盖搜索结果 | Bing HTTP 直搜 + DeepSeek 总结 | `tools.py:web_search` | 1h |
| 7 | 变种题蓝本不能多选 | 3月29日 | 只能单选 | click 事件直接 set 并关闭 | Toggle 多选模式 | `agent.js:1127-1155` | 30min |
| 8 | MinerU 模型缺失 | 2月15日 | OSError 缺 Layout 模型 | 只下载了 MFR，缺 6 个模型 | 逐个补下载 187 文件 | `download_mineru_models.py` | 1h |
| 9 | Windows multiprocessing | 2月15日 | 无限递归崩溃 | spawn 模式重新 import 主模块 | freeze_support + main 保护 | `test_mineru_2020.py` | 30min |
| 10 | chromadb+numpy 2.0 | 2月20日 | np.float_ 已移除 | chromadb 依赖旧 API | `pip install "numpy<2.0"` | 5min |
| 11 | scrollBottom 滚错元素 | 3月28日 | 同 #5（重复发现） | 同上 | 同上 | — |
| 12 | agent.js 缓存不更新 | 3月28日 | 改了 JS 不生效 | 浏览器版本号缓存 | 版本号递增到 ?v=21 | `*.html` 引用 | 1min |
| 13 | AsyncSqliteSaver 四次尝试 | 3月29日 | 同 #4 的详细过程 | 见 #4 | 见 #4 | 2h |
| 14 | Persona 不生效 | 3月29日 | 教师被当学生教 | LLM 传 persona="tutor" 覆盖全局变量 | 全局变量 + fallback + 动态 prompt | `langgraph_agent.py` + `tools.py` | 1h |
| 15 | marked.setOptions 崩溃 | 3月28日 | 同 #2（重复记录） | 同上 | 同上 | — |

### 2. 调试方法论：每个 bug 的根因分析法

**Bug #1（OCR 识别率低）的分析思路**：
- 不是"百度 OCR 不好用"——是化学领域有特殊挑战
- 化学式 LaTeX 需要精确识别 `$\mathrm{H_2SO_4}$` 中的上下标
- 普通 OCR 把上标数字识别为正文大小，LaTeX 结构就丢了
- 解决方案不是换 OCR 供应商——是换范式（从通用 OCR → 学术 PDF 专用 pipeline）

**Bug #3（题目不显示）的分析思路**：
- 这是典型的"字段名不匹配"bug——后端用 `exam_id`，前端读 `question_id`
- 为什么会发生？因为前后端分开开发，没有共享的接口定义
- 如果用了 TypeScript + tRPC，这个 bug 编译期就能发现
- 在原生 HTML + Python 的栈里，这类 bug 只能在运行时暴露

**Bug #4（对话持久化）的分析思路**：
- 这是一次"方案迭代"的经典案例
- 第一次：MemorySaver——能用但不持久
- 第二次：SqliteSaver——持久但不支持 async（LangGraph 1.x 限定）
- 第三次：AsyncSqliteSaver——支持 async 但与 asyncio.run() 冲突
- 第四次：懒加载 AsyncSqliteSaver——完美方案
- 教训：不要一上来就追求完美方案，先确认"能跑"，再逐步优化

### 3. 性能数据深度解读

**端到端延迟拆解**（3 月实测，DeepSeek API）：

```
用户点击发送
  │ ~50ms  ─ 前端 fetch 请求构造 + DOM 更新
  │ ~15ms  ─ FastAPI 中间件（CORS + auth middleware）
  │ ~5ms   ─ Gateway classify() 关键词匹配 (agent/gateway.py:174-289)
  │ ~200ms ─ 网络往返到 DeepSeek API (api.deepseek.com)
  │ ~2-5s  ─ LLM 推理（首 token）
  │ ~50ms/token ─ 后续 token（SSE 流式，每 token 约 50ms）
  │ ~10ms  ─ 前端 renderChem() 渲染
  │ ~5ms   ─ AsyncSqliteSaver 写入 checkpoint
  └ 总计: 2.5-6s（取决于回复长度，通常 200-500 字）
```

关键结论：**瓶颈在 LLM 推理，占比 >85%**。前端、网络、数据库加起来不到 15%。这意味着优化前端（比如从 Vue CDN 改为本地打包）的收益微乎其微。

**MinerU Pipeline 耗时拆解**（2020 年全国卷，22 页 PDF，纯 CPU）：

| 阶段 | 模型 | 数据量 | 耗时 |
|------|------|--------|------|
| Layout 检测 | PP-DocLayoutV2 | 22 页 | 37s |
| MFR 公式识别 | UnimerNet-Small | 414 个公式 | 9m27s |
| 表格检测+OCR | SLANet+/UNet | 5 个表格 | ~30s |
| 文本 OCR | PaddleOCR | 214 块文本区 | ~5min |
| **总计** | | | **~15min** |

MFR 公式识别占 63%——每页平均 19 个公式，22 页共 414 个 LaTeX 表达式，每个都需要单独的模型推理。

### 4. 已完成的 6 项优化（给学生解释为什么做、怎么做）

| # | 优化 | 做了什么 | 为什么重要 |
|---|------|---------|-----------|
| 1 | LLM 三路 fallback | DeepSeek → MiMo → DashScope 自动切换 | DeepSeek 1 月 15-16 日故障 12h，三路 fallback 保证零中断 |
| 2 | SSE 心跳保活 | 每 15s 发 `data: [PING]\n\n` | 学校企业网络有 30s HTTP 超时，15s 心跳可保活 |
| 3 | 前端缓存策略 | JS version tag + CDN 1 年缓存 | 浏览器缓存不更新导致"改了代码不生效" |
| 4 | SQLite WAL 模式 | Write-Ahead Logging | <5 个并发请求同时读写，WAL 足够，不需要连接池 |
| 5 | MinerU 模型本地缓存 | 7 个模型下载一次永久缓存 | 4-5GB 模型，后续导入不需要重新下载 |
| 6 | AsyncSqliteSaver 懒加载 | 首次请求初始化，后续复用 | 避免每次请求创建新数据库连接 |

### 5. 参数调优记录

| 参数 | 初始值 | 调优后 | 原因 |
|------|--------|--------|------|
| LLM max_tokens | 2000 | 4000-5000 | 化学式 LaTeX 占用大量 token，2000 不够 |
| LLM temperature | 0.7 | 0.1-0.3 | 化学领域需要确定性，创造性会导致配平错误 |
| Agent recursion_limit | 10 | 7-8 | 过多递归导致超时，7 次够用 |
| SSE ping interval | 30s | 15s | 学校网络代理超时 30s，15s 心跳可保活 |
| web_search max_tokens | 500 | 2048-4096 | 联网搜索结果通常长，500 会截断 |

### 6. 不做的优化（刻意不做——给学生解释工程判断）

| 不做的事 | 原因 | 做的时间 |
|---------|------|---------|
| 数据库索引 | 4.5MB SQLite，全表扫描 <10ms | 用户量 >1000 或 DB >100MB |
| 前端打包/Bundle | 1300 行 JS，无框架 | 前端 >5000 行 |
| API Rate Limiting | <5 个并发用户 | 用户量 >50 |
| Redis 缓存 | 无状态 API，无热点数据 | 引入排行榜/实时统计 |
| CDN Edge Cache | 内网访问，外网 CDN 无意义 | 部署到公网 |
| GPU 推理 | MinerU 导入是一次性操作 | 批量导入 >10 份试卷 |

**教学要点**：优化不是"越多越好"。过度优化是浪费——在 4.5MB 的 SQLite 上建索引，就像给自行车装涡轮增压。

### 7. 性能实测数据

```bash
# 首页加载（首次）
$ curl -w "time_total: %{time_total}s\n" -o /dev/null http://127.0.0.1:8001/
# time_total: 0.089s

# 考试工作台加载（含 Vue 3 内联 + 4 Tab 数据）
$ curl -w "time_total: %{time_total}s\n" -o /dev/null http://127.0.0.1:8001/pages/exam-v2.html
# time_total: 0.052s

# 真题库 API
$ curl -w "time_total: %{time_total}s\n" -o /dev/null \
  "http://127.0.0.1:8001/api/exam-bank/historical?region=全国卷&year=2020&page_size=1"
# time_total: 0.045s

# 练习任务 API（67 人学生数据）
$ curl -w "time_total: %{time_total}s\n" -o /dev/null \
  "http://127.0.0.1:8001/api/practice/student/202610101/tasks"
# time_total: 0.038s
```

### 8. 当前性能瓶颈排名

| 排名 | 瓶颈 | 影响 | 缓解方案 |
|------|------|------|---------|
| 1 | MinerU 15min 导入 | 教师需等待，一学期一次 | GPU 推理（P2） |
| 2 | DeepSeek API 2-5s 首 token | 每次对话延迟 | 用户已接受（比 ChatGPT 快） |
| 3 | SSE 网络不稳定 | 偶尔断开 | 心跳保活 + 前端自动重连（待做） |
| 4 | 前端 917 行 exam-v2.html | 首次加载包含 Vue 3 CDN | 拆分组件（P3） |

### 9. 调试工作流——可以教给学生的标准流程

```
发现问题（用户反馈/开发者自测）
  ↓
复现问题（构造同样的输入条件）
  ↓
定位根因（读代码 + 看日志 + 加 debug print）
  ↓
修复（改最小范围代码）
  ↓
验证（跑 evals/run_evals.py + 手动 E2E）
  ↓
部署（git commit + uvicorn reload）
```

每个问题的修复时间从 10 分钟（Bug #3 加一行 JSON 字段）到 2 小时（Bug #4 对话持久化 4 次重试）不等。核心能力不是"修得快"——是"定位得准"。

---

## 课后产出检查

- [ ] `python evals/run_evals.py` 输出 Agent 路由准确率 20/20 = 100%
- [ ] `renderChem` 相关修复后，历史真题页面的公式和图片正常渲染
- [ ] 服务重启后对话历史不丢失（AsyncSqliteSaver 生效）
- [ ] 联网搜索不再输出"2026 年尚未到来"
- [ ] 教师模式和学生模式的 AI 回复风格有明显区分
- [ ] 对话超过一屏后新消息自动滚动到底部
- [ ] 性能基准报告完成，包含 curl 实测数据和延迟拆解分析
- [ ] 知道性能瓶颈的排名（第 1 名：MinerU，第 2 名：DeepSeek API）

**下节课需要**：MVP 所有 8 个功能可用 + 无已知 P0/P1 blocking bug。Session 17 将进行 MVP 验收（E2E 测试 + 错误注入测试 + 种子教师内测）+ 新需求注入与迭代交付。

---

## 补充内容 — 教师深度参考

### 为什么选这 5 个 bug 让学生动手修

15 个 bug 中选了 5 个代表性的：

1. **marked API 兼容性**（前端）- 教"API 版本变更的静默失败"——不报错但功能降级
2. **对话持久化**（后端架构）- 教"方案迭代"——从能用到好用需要多次尝试
3. **联网搜索时效性**（API 集成）- 教"第三方 API 的模型偏见"——搜索结果被训练截止日期覆盖
4. **persona 分离**（Agent 逻辑）- 教"状态管理"——全局变量被工具调用参数覆盖
5. **滚动定位**（前端 DOM）- 教"CSS 层级理解"——overflow 容器 ≠ 滚动目标元素

这 5 个覆盖了前端、后端、Agent、API 集成四个维度的典型 bug 模式。

### 其他 10 个 bug 的快速参考

| Bug | 一句话 | 教什么 |
|-----|--------|--------|
| OCR 识别率低 | Baidu OCR → MinerU pipeline | 技术选型要匹配领域特征 |
| 题目不显示 | exam_id vs question_id 字段名不匹配 | 前后端接口契约 |
| 变种题蓝本 | 单选 → Toggle 多选 | UI 交互模式升级 |
| MinerU 模型缺失 | 只下了 1 个模型，缺 6 个 | 环境依赖检查 |
| Windows multiprocessing | spawn 模式无限递归 | 平台差异 |
| chromadb+numpy 2.0 | 依赖版本冲突 | 依赖管理 |
| agent.js 缓存 | 版本号不递增 | 浏览器缓存机制 |
| MinerU 15min | 首次导入慢是正常的 | 性能预期的设定 |
| 2020 卷导入慢 | 同 MinerU 耗时问题 | 同类型 |
| 真题图片不显示 | 同 marked API | 同上 |

### 性能优化的黄金法则

"不要优化没有测量的东西"——如果你不知道瓶颈在哪，别盲目改代码。

"优化瓶颈，不是优化你猜的地方"——前端 1300 行 VS 后端 LLM 2-5s，显然瓶颈在 LLM。

"不做不需要的优化"——4.5MB SQLite 的全表扫描 <10ms，建索引是多此一举。

# Session 8 · POC 验证与风险验证

## 产出物

- `docs/poc-methodology.md` — POC 方法论文档（定义/标准/成本模型/踩坑记录）
- `docs/poc-risk-map.md` — 风险验证地图（6 个风险假设 × POC 覆盖矩阵）
- `poc/` 目录，含 2 个 POC 脚本
- `poc/test_llm_chemistry.py` — POC 1：LLM 化学能力验证脚本（10 题自动评分）
- `poc/test_agent_routing.py` — POC 3：Agent 路由能力验证脚本（20 条路由测试）
- `docs/poc-report-llm-chemistry.md` — POC 1 验证报告
- `docs/poc-report-agent-routing.md` — POC 3 验证报告

## 前置条件

- Session 2 的 `app/services/llm_service.py` 可用（LLM API 连通）
- Session 7 的原型和信息架构就绪（知道要验证什么功能）
- Session 6 的 PRD 和项目计划就绪（知道风险点在哪）
- Claude Code 可用
- DeepSeek API Key 有效

## 项目背景（给学生的概述）

PRD 写好了，原型做好了，WBS 拆好了——你觉得可以开始写正式代码了？等一下。

在投入几十个小时写完整实现之前，有一个步骤被大多数教程跳过了：**POC 验证**。POC 不是"做个 demo 给领导看"，是回答一个更根本的问题——**你计划中风险最高的那些假设，到底成不成立？**

ChemAI 项目在 3 个月的开发中做了 6 次 POC。每次 POC 都省了巨大的时间浪费：

| POC | 验证什么 | 耗时 | 如果直接做完整实现 | 省了多少 |
|-----|---------|------|-------------------|---------|
| LLM 能答化学题吗 | curl + 5 题 | 30min | 接入 LLM SDK 完整封装 | 2 天 |
| MinerU 能提取化学 PDF 吗 | Python 脚本 | 2h | OCR 管线完整搭建 | 3 天 |
| Agent 能正确路由吗 | curl + SSE | 1h+3d | Agent 架构完整实现 | 2 周 |
| 对话能持久化吗 | Python REPL | 30min+4x | AsyncSqliteSaver 完整集成 | 1 天 |
| 手机端能用吗 | 实际设备测试 | 1h | 移动端响应式完整适配 | 3 天 |
| MinerU 内存够吗 | 任务管理器监控 | 30min | 服务器采购或优化 | 不确定 |

6 个 POC 加起来不到 8 小时，但避免了至少 4 周的方向性错误。这节课你要学会 POC 的方法论——如何识别需要验证的风险假设、如何用最低成本验证、如何从 POC 结果做 go/no-go 决策。

---

## 操作步骤

### 步骤 1：理解 POC 方法论

**目标**：学习 POC 的定义、标准和成本模型

**提示词**（复制到 Claude Code）：

```
我需要你帮我理解 POC（Proof of Concept）方法论。这不是一个编程任务，是一个学习任务。

请基于以下信息，帮我整理一份 POC 方法论文档，输出到 docs/poc-methodology.md。

## POC 的准确定义

POC 不是"做个 demo 给领导看"。POC 是：**用最低成本验证最高风险假设是否成立**。

关键区别：
- Demo：展示"这东西能做"——给外人看的
- POC：验证"这东西能不能做"——给自己看的
- MVP：给用户用的最小可用产品
- POC 在 MVP 之前：先验证能不能做，再决定做不做

## POC 的三个核心问题

每次 POC 必须回答三个问题：
1. 我们在验证什么假设？（必须具体到可证伪——"LLM 能做化学题"太模糊，"LLM 在高考化学六大板块中至少四个板块准确率≥80%"才可证伪）
2. 通过标准是什么？（不能是"看情况"，必须是二元的——通过了就继续，没通过就换方案或放弃）
3. 最小验证成本是什么？（能用 curl 就不用 Python SDK，能用 Python 脚本就不用改现有代码）

## POC 成本模型

ChemAI 项目的实际数据：
- POC 平均耗时：完整实现的 5-15%
- LLM 准确性验证：30min（curl + prompt 测试）vs 完整接入 2 天
- OCR 精度验证：2h（单脚本 + 模型下载）vs 完整管线 3 天
- Agent 路由验证：1h + 3 天重试（架构选型迭代）vs 完整实现 2 周

核心公式：POC 耗时 ∝ 待验证假设的技术不确定性。不确定性越高，越值得先做 POC。

## POC 的踩坑方法论

ChemAI 项目 6 次 POC 中踩过的坑：
1. MinerU 需要 7 个模型 → 下载踩了三轮坑（被墙 → ModelScope → VPN → HuggingFace）
2. Windows multiprocessing → ProcessPoolExecutor 需要 `if __name__ == '__main__'`
3. numpy 2.0 与 chromadb 冲突 → 降级到 numpy<2.0
4. pydantic-ai 不支持多步骤工具链 → 切换到 LangGraph
5. LangGraph ReAct 不稳定（5/10 正确）→ 升级到 Multi-Agent + Gateway
6. AsyncSqliteSaver 的 API 陷阱 → 懒加载模式

每条踩坑记录的价值：如果不做 POC 直接实现，这些问题会在集成了 500 行代码之后才暴露——修复成本是 POC 阶段的 10 倍以上。

## 输出要求

将以上内容整理为结构化的 POC 方法论文档，包含：定义、三个核心问题、成本模型、踩坑原则、go/no-go 决策框架。
```

**验证**：
- [ ] `docs/poc-methodology.md` 存在
- [ ] 包含 POC 的三个核心问题定义
- [ ] 包含成本模型和 6 条踩坑记录

---

### 步骤 2：识别 ChemAI 的关键风险假设

**目标**：从 PRD 和技术方案中提取需要 POC 验证的风险假设

**提示词**（复制到 Claude Code）：

```
读取 docs/prd-v1.0.md、docs/risk-matrix.md、docs/wbs-task-tree.md。

识别 ChemAI 项目需要 POC 验证的关键风险假设。输出到 docs/poc-risk-map.md。

## 识别方法

对每个计划中的核心功能，问三个问题：
1. 这个功能依赖什么技术能力？这个能力我们确定可用吗？
2. 这个功能有什么前提假设？如果假设不成立会怎样？
3. 如果这个功能做不出来，有没有替代方案？

## ChemAI 的 6 个关键风险假设（基于真实项目记录）

| # | 风险假设 | 如果不成立 | 严重度 | POC 方案 |
|---|---------|-----------|--------|---------|
| 1 | LLM 能正确回答高中化学六大板块的题目 | 整个产品不可行 | 🔴 致命 | 10 道高考题实测 |
| 2 | MinerU 能从 PDF 中完整提取化学方程式和 LaTeX | OCR 模块不可行 | 🔴 致命 | 1 份真题 PDF 实测 |
| 3 | Agent 能正确理解用户意图并路由到正确的子专家 | Agent 架构不可行 | 🔴 致命 | 20 条 Golden 场景测试 |
| 4 | 对话历史能跨重启持久化 | 用户体验严重受损 | 🟡 严重 | AsyncSqliteSaver 端到端测试 |
| 5 | 学生端在手机浏览器上能正常使用 | 学生端不可用 | 🟡 严重 | iPhone + 微信内置浏览器实测 |
| 6 | MinerU 在 8GB 内存的机器上不会 OOM | 需要换机器或方案 | 🟡 严重 | 任务管理器监控内存峰值 |

对每个风险假设：
- 标注严重度（致命/严重/中等/低）
- 设计最低成本的验证方案
- 定义通过/不通过标准
- 如果不通过，备选方案是什么

## 输出格式

| # | 风险假设 | 严重度 | 验证方案 | 通过标准 | 不通过时的备选 | 预估 POC 耗时 |
|---|---------|--------|---------|---------|--------------|-------------|
```

**验证**：
- [ ] `docs/poc-risk-map.md` 存在
- [ ] 6 个风险假设完整，每个有验证方案和通过标准
- [ ] 严重度分类合理（至少 2 个致命、2 个严重）

---

### 步骤 3：执行 POC 1 —— LLM 化学能力验证

**目标**：用 10 道高考化学真题验证 LLM 是否能正确回答

**提示词**（复制到 Claude Code）：

```
对 ChemAI 做第一个 POC：LLM 化学能力验证。

## 验证假设

LLM（DeepSeek）能在高考化学六大板块中至少四个板块达到 ≥80% 的准确率。

## 验证方案

创建 poc/ 目录，编写 poc/test_llm_chemistry.py 脚本。

测试 10 道题，覆盖高考化学六大板块：
1. 化学计量与物质的量（2 题）
2. 氧化还原反应（2 题）
3. 离子反应与电解质（1 题）
4. 元素化合物（2 题）
5. 化学反应速率与化学平衡（1 题）
6. 有机化学（2 题）

题目格式：每道题包含题干、四个选项、正确答案、所属板块。

脚本逻辑：
1. 逐题调用 DeepSeek API（通过 app/services/llm_service.py）
2. 记录每道题的：题目、AI 答案、正确答案、是否正确、延迟
3. 按板块汇总准确率
4. 输出格式化报告

## 通过标准

- 总准确率 ≥ 80%（10 题中至少 8 题正确）
- 至少 4 个板块准确率 ≥ 80%
- 单题平均延迟 ≤ 10s

## 不通过时的备选方案

- 换模型（如换用 Qwen、Claude）
- 调整 prompt 策略（增加化学学科 system prompt）
- 缩小产品范围（只覆盖 AI 擅长的板块）

## POC 报告

POC 完成后，输出报告到 docs/poc-report-llm-chemistry.md，包含：
- 验证假设和通过标准
- 测试结果（逐题详情 + 板块汇总表）
- go/no-go 结论
- 如果 go：下一步计划
- 如果 no-go：备选方案评估
```

**验证**：
- [ ] `poc/test_llm_chemistry.py` 存在，可运行
- [ ] `docs/poc-report-llm-chemistry.md` 存在
- [ ] 10 题测试结果清晰，有 go/no-go 结论

---

### 步骤 4：执行 POC 3 —— Agent 路由能力验证

**目标**：验证 Agent 能否正确理解用户意图并路由

**提示词**（复制到 Claude Code）：

```
对 ChemAI 做第二个关键 POC：Agent 路由能力验证。

## 验证假设

Agent 能正确识别至少 90%（18/20）的用户意图并路由到正确的子专家。

## 背景

ChemAI 的 Agent 架构经历了三次选型迭代：
1. pydantic-ai（路由准确率 ~70%，单 Agent 多工具模式）
2. ReAct Agent（5/10 正确，推理链路不稳定）
3. Multi-Agent + Gateway 关键词预路由（100% 准确率）

你在验证的是方案 3——这个 POC 决定了 ChemAI 的 Agent 架构方向。

## 验证方案

创建 poc/test_agent_routing.py 脚本，用 20 条 Golden 场景测试路由准确率。

20 条测试场景覆盖 6 种子专家路由：
- chemistry_tutor（化学教学）：5 条
- exam_expert（出题）：4 条
- search_expert（搜索）：3 条
- diagnosis_expert（诊断）：3 条
- bank_expert（题库）：3 条
- browser_expert（浏览器）：2 条

每条测试用例格式：
```python
{"input": "氧化还原反应的本质是什么", "expected_route": "chemistry_tutor"}
```

脚本逻辑：
1. 对每条测试，调 Gateway 关键词预路由 → Coordinator 二次确认
2. 记录：输入、预期路由、实际路由、是否正确、延迟
3. 按子专家汇总准确率
4. 输出格式化报告

## 通过标准

- 总路由准确率 ≥ 90%（20 条中至少 18 条正确）
- Gateway 预路由延迟 ≤ 5ms（关键词匹配应极快）
- 无"致命误路由"（把"我要出题"路由到搜索，把"诊断学生"路由到题库等）

## POC 报告

输出到 docs/poc-report-agent-routing.md，包含：
- 架构选型历程（pydantic-ai → ReAct → Multi-Agent+Gateway）
- 20 条测试结果逐条详情
- 误路由案例分析（如果存在）
- go/no-go 结论
```

**验证**：
- [ ] `poc/test_agent_routing.py` 存在，可运行
- [ ] `docs/poc-report-agent-routing.md` 存在
- [ ] 路由准确率 ≥ 90%，有 go/no-go 结论

---

## 发生了什么（教师参考）

### 1. POC 不是可选的——是职业习惯

很多开发者（尤其是新手）的习惯是：有了 idea → 直接写代码。POC 要培养的习惯是：有了 idea → 识别最危险假设 → 用最低成本验证 → 验证通过才写代码。

ChemAI 项目如果跳过 POC 直接实现：
- 可能在接入 LLM 两周后才发现 DeepSeek 在某些化学板块准确率不够
- 可能在 Agent 写了一周后才发现 ReAct 模式下路由只有 50%
- 可能在 MinerU 配了三天环境后才发现内存不够

这些都不是"写错了"——是"不该写"。POC 的价值不在于验证成功（"你看，能做！"），在于验证失败（"还好没做，省了两周"）。

### 2. POC 的三个常见错误

**错误 1：POC 做太大。** 学生容易把 POC 做成"简化版实现"而不是"最小验证"。POC 的标准是：用最少代码回答一个二元问题。如果 POC 超过了完整实现的 20%，说明你验证的不是一个假设，是一堆假设——该拆成多个 POC。

**错误 2：通过标准模糊。** "看情况"、"差不多"、"感觉还行"——这些不是通过标准。POC 的通过标准必须是二元的：过了就继续，没过就换方案。如果标准模糊，POC 就失去了 go/no-go 的决策价值。

**错误 3：只做技术 POC，不做用户 POC。** 技术可行性只是风险的一类。ChemAI 还应该做用户 POC——找种子教师做 30 分钟的概念验证访谈。"如果有一个工具能自动审核 AI 出的化学题，你会用吗？"这个问题比"chemical_balance 函数能跑通吗"更重要。

### 3. ChemAI 6 次 POC 的关键教训

| POC | 最关键教训 |
|-----|-----------|
| LLM 化学能力 | DeepSeek 满分 20 分，但 DashScope Qwen 漏写反应条件——选型不是选"最好的"，是选"对化学最靠谱的" |
| MinerU 精度 | 7 个模型的下载路径踩了三轮坑——依赖链的复杂度是 POC 的最大耗时来源 |
| Agent 路由 | 架构选型不是一次到位的——pydantic-ai → ReAct → Multi-Agent 三次迭代才找到正确方向 |
| 对话持久化 | AsyncSqliteSaver 的 `from_conn_string` API 是 async context manager 而非实例——API 文档的陷阱只有 POC 能暴露 |
| 手机端兼容 | 微信内置浏览器 WebView 对 KaTeX 的支持需要 polyfill——真实设备测试才能发现 |
| MinerU 内存 | 峰值 2.8GB，8GB 机器可用——但如果不测，可能会错误地买服务器 |

### 4. 经常出现的问题

**Q：学生说"我不知道哪些假设需要 POC"**
A：最好的识别方法：在 WBS 的每个叶子任务旁边加一列"最大不确定性"。不确定性评分 ≥4/5 的任务必须先做 POC。三句话检查——"这个能行吗？我们确定吗？如果不行怎么办？"——如果有一个回答不自信，就值得 POC。

**Q：POC 失败了怎么办？**
A：POC 失败不是坏事——它阻止了你在错误方向上浪费更多时间。失败的 POC 有三个出口：换方案（换个模型/架构）、缩小范围（只做 AI 擅长的部分）、放弃（承认不可行比硬做更专业）。

---

## 课后产出检查

- [ ] `docs/poc-methodology.md` 完整，含三个核心问题 + 成本模型 + 6 条踩坑记录
- [ ] `docs/poc-risk-map.md` 完整，6 个风险假设每个有验证方案和通过标准
- [ ] `poc/test_llm_chemistry.py` 可运行，10 题验证完成
- [ ] `poc/test_agent_routing.py` 可运行，20 条路由验证完成
- [ ] `docs/poc-report-llm-chemistry.md` 有明确 go/no-go 结论
- [ ] `docs/poc-report-agent-routing.md` 有明确 go/no-go 结论

**下节课需要**：POC 全部通过（LLM 化学能力 + Agent 路由能力均验证可行）。Session 9 将构建 EVALS 体系（基线/边界/回归三层），Session 10 进入数据库设计（14 个表 + 6 个核心场景）。

# Session 2 · LLM 接入与化学能力验证

## 产出物

- `app/services/llm_service.py` — 三 Provider 接入 + 三路 fallback 机制
- `app/services/chemical_balance.py` — 化学方程式/配平审核工具
- `.env` — 新增 `DEEPSEEK_API_KEY`、`XIAOMI_API_KEY`、`DASHSCOPE_API_KEY`
- `tests/test_llm_chemistry.py` — 10 道化学测试题自动评分脚本
- 三个 Provider 的实测数据：准确率、延迟、成本、稳定性

## 前置条件

- 上节课（Session 1）的 `chemai-backend/` 目录完整可用
- `python chemai.py` 能启动，`curl http://127.0.0.1:8001/` 返回 `{"status":"ok"}`
- Python 依赖已安装（fastapi、uvicorn、httpx、python-dotenv、pydantic）
- **需要提前准备三个 API Key**：
  - DeepSeek API Key（注册地址：platform.deepseek.com → API Keys）
  - Xiaomi MiMo API Key（注册地址：api.xiaomimimo.com）
  - DashScope API Key（阿里云百炼平台，注册地址：dashscope.aliyuncs.com）
- 教师帮学生提前确认三个 Key 都可用（至少 DeepSeek 必须先拿到）

## 项目背景

上节课我们搭好了一个空壳——FastAPI 能跑，访问 `http://127.0.0.1:8001/` 返回 `{"status":"ok"}`。但这跟化学有什么关系？没有任何关系。

这节课我们要把 AI 的大脑接进来。ChemAI 的核心是让 AI 回答高中化学问题——配平方程式、判断反应类型、解释化学原理。但这里有一个关键问题：**不是所有大模型都能做好化学**。

我们在项目 Day 2 做了一个 POC：用 curl 直接调 DeepSeek API，问了 5 个基础化学问题（配平 Fe + O2、盐类水解、Na 与水反应等），全部答对。但这不够——5 道题太少了，而且只测了一个模型。

所以我们设计了 10 道测试题，覆盖高考化学六大板块，逐个 Provider 实测。结果发现：DeepSeek 满分 20 分，MiMo 也是 20 分，但 DashScope Qwen 只拿了 18 分——漏写了反应条件。这不是"模型笨"，是"会但不全"——而这种"不全"恰恰是教师最不能容忍的（化学方程式的反应条件漏了，整道题算错）。

这节课你要做三件事：接入三个 LLM Provider、用 10 道化学题验证每个 Provider 的准确率、搭建三路 fallback 保证服务不挂。

---

## 操作步骤

### 步骤 1：配置三个 API Key

**目标**：在 `.env` 中写入三个 Provider 的 API Key，并在 config.py 中加载

**提示词**（复制到 Claude Code）：
```
在 chemai-backend 项目中，更新 .env 文件和 app/core/config.py，接入三个 LLM Provider 的 API Key。

1. 修改 .env，确保包含以下三行（Key 值替换为实际的）：
CHEMAI_PORT=8001
DEEPSEEK_API_KEY=sk-你的DeepSeek密钥
XIAOMI_API_KEY=sk-你的MiMo密钥
DASHSCOPE_API_KEY=sk-你的DashScope密钥

2. 修改 app/core/config.py，增加三个新字段：
   - DEEPSEEK_API_KEY: str = ""
   - XIAOMI_API_KEY: str = ""
   - DASHSCOPE_API_KEY: str = ""
   所有字段都要能从 .env 读取。Config 类保持 env_file = ".env"。

注意：.env 文件已经在 .gitignore 中，不会被提交到 Git。
```

**验证**：
- [ ] `.env` 文件中包含三个 API Key（非空值）
- [ ] `app/core/config.py` 中定义了三个新字段

---

### 步骤 2：创建 LLM 服务层——接入 DeepSeek

**目标**：创建 `app/services/llm_service.py`，先接入 DeepSeek，用 httpx 异步调用其 chat/completions 接口

**提示词**（复制到 Claude Code）：
```
在 chemai-backend 项目中，创建 app/services/ 目录（如果不存在），然后创建 app/services/__init__.py 和 app/services/llm_service.py。

llm_service.py 的内容要求：

1. 导入：httpx, os, json, asyncio
2. 从 app.core.config 导入配置（用 from app.core.config import Config; config = Config()）
3. 定义 API 端点常量：
   DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
   DEEPSEEK_MODEL = "deepseek-chat"
4. 定义异步函数 generate_text(prompt: str, system_prompt: str = None, temperature: float = 0.1) -> str：
   - 用 httpx.AsyncClient 发 POST 请求到 DEEPSEEK_URL
   - headers 包含 Authorization: Bearer {config.DEEPSEEK_API_KEY}
   - body 包含 model, messages（system + user）, temperature
   - 设置 timeout=30.0（秒）
   - 返回 response["choices"][0]["message"]["content"]
   - 错误时 print 响应内容并 raise RuntimeError

5. 在文件末尾加一个 if __name__ == "__main__" 测试块：
   - 用 asyncio.run() 调用 generate_text()，prompt="配平化学方程式：Fe + O2 = Fe2O3"
   - 打印返回结果

temperature 设为 0.1 而不是默认的 1.0，因为化学问题需要确定性——temperature 越低，输出越稳定。
```

**验证**：
- [ ] `app/services/llm_service.py` 文件已创建
- [ ] 在 chemai-backend 目录下运行 `python -m app.services.llm_service`，输出正确的配平结果 `4Fe + 3O2 = 2Fe2O3`

---

### 步骤 3：POC 验证——10 道化学测试题

**目标**：用 DeepSeek 跑 10 道化学测试题，验证 AI 的化学准确率

**提示词**（复制到 Claude Code）：
```
在 chemai-backend 项目中，创建 tests/__init__.py 和 tests/test_llm_chemistry.py。

test_llm_chemistry.py 的要求：

1. 导入 app.services.llm_service 中的 generate_text
2. 定义 10 道化学测试题，覆盖高考化学六大板块：

测试题列表（每道题的 prompt 要写清楚）：
- 题1（基本概念-氧化还原）: "Na 与 H2O 的反应是否属于氧化还原反应？如果是，请指出氧化剂和还原剂。"
- 题2（基本概念-离子反应）: "写出 Fe 与 CuSO4 溶液反应的离子方程式。"
- 题3（元素化合物-金属）: "写出 Na2O2 与 H2O 反应的化学方程式。"
- 题4（元素化合物-非金属）: "配平化学方程式：KMnO4 + HCl(浓) = KCl + MnCl2 + Cl2↑ + H2O"
- 题5（化学反应原理-速率）: "某反应在2分钟内，反应物浓度从0.8mol/L降到0.2mol/L，求平均反应速率。"
- 题6（化学反应原理-平衡）: "对于放热反应 N2 + 3H2 ⇌ 2NH3，升高温度后平衡向哪个方向移动？为什么？"
- 题7（有机化学）: "写出 CH3CH2OH 的化学名称，并指出其官能团。"
- 题8（物质结构）: "写出 Fe（原子序数26）的核外电子排布式。"
- 题9（化学实验-装置）: "描述实验室制取 Cl2 的装置（MnO2 + 浓盐酸），需要哪些主要仪器？"
- 题10（化学实验-设计）: "设计一个实验验证 Fe3+ 的氧化性强于 Cu2+，写出步骤和预期现象。"

3. 用 asyncio.run() 依次调用 generate_text()，每题打印：
   - 题号和题目
   - AI 的回答
   - 分隔线 "---"

4. temperature 全部用 0.1

运行这个测试脚本，观察输出质量。重点关注：
- 方程式配平是否正确（系数）
- 反应条件是否完整（加热、催化剂、浓/稀）
- 化学用语是否规范（↑↓符号、状态标注）
```

**验证**：
- [ ] `tests/test_llm_chemistry.py` 文件已创建
- [ ] 运行 `python -m tests.test_llm_chemistry` 后能看到 10 道题的回答
- [ ] 方程式的配平系数正确（教师逐题检查）

---

### 步骤 4：接入 MiMo Provider

**目标**：在 llm_service.py 中增加 MiMo-V2.5，支持 provider 参数切换

**提示词**（复制到 Claude Code）：
```
修改 app/services/llm_service.py，增加 MiMo Provider 支持。

1. 在文件顶部增加常量：
   MIMO_URL = "https://api.xiaomimimo.com/v1/chat/completions"
   MIMO_MODEL = "mimo-v2.5"

2. 修改 generate_text 函数签名：
   def generate_text(prompt: str, system_prompt: str = None, temperature: float = 0.1, provider: str = "deepseek") -> str

3. 在函数内部，根据 provider 参数选择 URL、Model 和 API Key：
   - provider == "deepseek" → DEEPSEEK_URL / DEEPSEEK_MODEL / config.DEEPSEEK_API_KEY
   - provider == "mimo" → MIMO_URL / MIMO_MODEL / config.XIAOMI_API_KEY
   - 其他值 → raise ValueError(f"Unknown provider: {provider}")

4. 在 if __name__ == "__main__" 测试块中增加 MiMo 的测试：
   - 同样用"配平化学方程式：Fe + O2 = Fe2O3"
   - provider="mimo"

5. 所有 Provider 都兼容 OpenAI chat/completions 格式——URL、Model、Key 不同，但请求体和响应结构完全一样。不需要写适配器。

运行测试，确认 DeepSeek 和 MiMo 的配平结果都是 4Fe + 3O2 = 2Fe2O3。
```

**验证**：
- [ ] `python -m app.services.llm_service` 分别测试 DeepSeek 和 MiMo，都返回正确的配平结果
- [ ] provider="unknown" 时抛出 ValueError

---

### 步骤 5：接入 DashScope 并构建三路 fallback

**目标**：增加 DashScope Qwen，实现三路 fallback——当一个 Provider 不可用时自动切换到下一个

**提示词**（复制到 Claude Code）：
```
修改 app/services/llm_service.py，增加 DashScope Provider 和三路 fallback 机制。

1. 增加常量：
   DASHSCOPE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
   DASHSCOPE_MODEL = "qwen-turbo"

2. 在 generate_text 函数中增加 provider == "dashscope" 分支，使用 config.DASHSCOPE_API_KEY。

3. 新增函数 generate_with_fallback(prompt, system_prompt=None, temperature=0.1) -> str：
   - 按优先级尝试三个 Provider：mimo → dashscope → deepseek
   - 如果当前 Provider 调用失败（抛出异常），自动尝试下一个
   - 三个都失败则 raise RuntimeError("All providers failed")
   - 每次切换时 print 一条日志："[Fallback] Provider {name} failed, trying {next_name}..."
   - 记录实际使用的 Provider 并返回

   Provider 优先级设计理由：
   - MiMo 有视觉能力（多模态），但稳定性最差（98.2%），成本最高，所以放第一个
   - DashScope 最稳定（99.9%），成本低，放中间
   - DeepSeek 化学准确率最高（20/20），成本最低，但有一次12小时故障记录，放最后

4. 修改 if __name__ == "__main__" 测试块：
   - 调用 generate_with_fallback() 替代直接调用 generate_text()
   - 测试三个 Provider 都能被正确路由

运行测试，确认 fallback 机制正常工作。
```

**验证**：
- [ ] 三个 Provider 分别调用都能返回正确结果
- [ ] 故意传错 provider 名称时抛出 ValueError
- [ ] 如果某个 Provider Key 不可用，fallback 自动切换到下一个，日志可见

---

### 步骤 6：用真实测试题对比三个 Provider

**目标**：修改 test_llm_chemistry.py，对三个 Provider 分别跑 10 道题，收集完整对比数据

**提示词**（复制到 Claude Code）：
```
修改 tests/test_llm_chemistry.py，升级为三 Provider 对比测试。

1. 新增函数 evaluate_provider(provider_name: str, questions: list[dict]) -> dict：
   - 对每道题调用 generate_text(prompt=q["prompt"], provider=provider_name, temperature=0.1)
   - 打印每题的回答
   - 收集每次调用的耗时（用 time.time() 计）
   - 返回 {"provider": name, "answers": [...], "total_time": float, "avg_time": float}

2. 新增函数 compare_providers()：
   - 分别对 deepseek、mimo、dashscope 三个 Provider 跑全部 10 题
   - 打印对比表格，包括：
     - 每题各 Provider 的回答摘要（前100字）
     - 每题耗时
     - 总耗时和平均耗时

3. 如果有 Provider 调用失败（网络错误、Key 无效等），记录为失败但不中断整个测试。

4. 在 if __name__ == "__main__" 中运行 compare_providers()。

运行这个测试，你会看到三个 Provider 对同一道化学题的实际回答差异。重点关注 DashScope——它可能是唯一会"漏写反应条件"的。
```

**验证**：
- [ ] 运行 `python -m tests.test_llm_chemistry`，三个 Provider 各跑 10 题
- [ ] 控制台输出包含每题结果和耗时统计
- [ ] 如果某个 Provider Key 无效，该项标记为失败但不影响其他

---

### 步骤 7：chemical_balance 审核工具

**目标**：创建 `app/services/chemical_balance.py`——对 AI 生成的化学方程式做自动化审核

**提示词**（复制到 Claude Code）：
```
创建 app/services/chemical_balance.py，实现化学方程式的自动审核。

功能要求：

1. 定义审核函数 audit_equation(reactants: str, products: str, equation: str) -> dict：
   - reactants: 反应物，如 "Fe, O2"
   - products: 生成物，如 "Fe2O3"
   - equation: AI 生成的方程式，如 "4Fe + 3O2 = 2Fe2O3"

2. 审核检查项（返回 dict，每项 pass: bool + reason: str）：
   a. 原子守恒：检查方程式两边每种元素的原子数是否相等
      - 解析方程式的左右两边（按 = 或 → 分割）
      - 解析每种物质的系数和元素组成
      - 对比两边每种元素的总原子数
   b. 反应条件标注：检查是否包含必要的反应条件关键词
      - 常见条件：加热/△、高温、点燃、催化剂、通电、浓/稀
      - 如果 reactants 或 products 中暗示需要条件（如"浓 HCl"），检查方程式中是否有"浓"字
   c. 符号规范：检查 ↑（气体）和 ↓（沉淀）符号是否正确使用
   d. 系数完整性：检查是否所有物质都有系数标注

3. 返回格式：
   {
     "valid": True/False,
     "checks": {
       "atom_conservation": {"pass": True, "reason": "两边 Fe 原子数: 4=4, O 原子数: 6=6"},
       "reaction_conditions": {"pass": False, "reason": "未标注加热条件 △"},
       "symbol_norms": {"pass": True, "reason": "气体/沉淀符号正确"},
       "coefficient_completeness": {"pass": True, "reason": "所有物质系数已标注"}
     },
     "issues": ["缺少加热条件 △"]
   }

4. 在 if __name__ == "__main__" 中做两个测试：
   - 正确方程式："4Fe + 3O2 = 2Fe2O3"（配平正确但缺少点燃条件）
   - 错误方程式："Fe + O2 = Fe2O3"（配平错误）
   - 打印每个测试的审核结果

注意：这个工具不会很完美——它是规则审核，不是化学专业审核。但能抓住最低级的错误（配平错、漏条件）。
```

**验证**：
- [ ] `app/services/chemical_balance.py` 文件已创建
- [ ] 运行 `python -m app.services.chemical_balance`，输出两个测试用例的审核结果
- [ ] 正确方程式检测到"缺少点燃条件"
- [ ] 错误方程式检测到"原子不守恒"

---

### 步骤 8：Git 提交

**目标**：提交本节所有改动

**提示词**（复制到 Claude Code）：
```
在 chemai-backend 目录里提交本节所有改动：

1. git status 查看所有变更
2. git add app/services/ tests/ .env （.env 不会被添加因为有 .gitignore）
3. git commit -m "v1.1.0: LLM 三 Provider 接入 — DeepSeek + MiMo + DashScope 三路 fallback + 化学方程式审核工具"

确认提交后 git log 可以看到两个提交：
- v1.0.0（上节课）
- v1.1.0（本节课）
```

**验证**：
- [ ] `git log` 显示两个提交
- [ ] `git status` clean
- [ ] .env 没有出现在 git 跟踪中

---

## 发生了什么（教师参考）

### 1. 为什么测 10 道题而不只看 benchmark？

市面上有很多 AI 评测榜单（MMLU、C-Eval、SuperCLUE 等），但我们一个都没看。原因很简单：

**benchmark 测的是模型，我们要测的是"这个模型能不能用在我们这个场景里"。**

MMLU 的化学子集有几千道题，但都是选择题——我们的产品场景是简答题和出题，需要模型写出完整的方程式和推理过程。10 道我们手动设计的简答题，比 1000 道选择题更有参考意义。

10 道题覆盖六大板块的分配：

| 板块 | 题数 | 对应高考分值（约） |
|------|------|------------------|
| 化学基本概念（离子反应、氧化还原）| 2 | 12 分 |
| 元素化合物（金属/非金属性质）| 2 | 18 分 |
| 化学反应原理（速率、平衡、电化学）| 2 | 22 分 |
| 有机化学（官能团、反应类型）| 1 | 15 分 |
| 物质结构（电子排布、晶体类型）| 1 | 10 分 |
| 化学实验（装置、操作、现象）| 2 | 23 分 |

评分标准：每道题 0-2 分，总分 20 分。16 分及以上 = 可用。化学教师的容忍阈值是"10 道里最多 1 道有错"（即 10% 错误率），对应 18 分。

### 2. 三个 Provider 实测数据详解

这是教师讲解的核心部分。学生对 AI 的初始印象通常是"AI 什么都会"，但实测数据会推翻这个假设。

**Provider 1：DeepSeek-V3 (`deepseek-chat`)**

| 题号 | 板块 | 知识点 | 得分 | 备注 |
|------|------|--------|------|------|
| 1 | 基本概念 | 氧化还原判断 | 2 | 正确判断 + 正确解释氧化剂/还原剂 |
| 2 | 基本概念 | 离子方程式 | 2 | Fe + Cu2+ = Fe2+ + Cu |
| 3 | 元素化合物 | Na2O2 与 H2O 反应 | 2 | 2Na2O2 + 2H2O = 4NaOH + O2↑ |
| 4 | 元素化合物 | KMnO4 + HCl 配平 | 2 | 系数正确：2,16,2,2,5,8 |
| 5 | 反应原理 | 反应速率计算 | 2 | 0.3 mol/(L·min) |
| 6 | 反应原理 | 平衡移动判断 | 2 | 升高温度向吸热方向（逆向）移动 |
| 7 | 有机化学 | 乙醇命名 | 2 | 乙醇，官能团羟基(-OH) |
| 8 | 物质结构 | 电子排布式 | 2 | 1s² 2s² 2p⁶ 3s² 3p⁶ 3d⁶ 4s² |
| 9 | 化学实验 | 制 Cl2 装置 | 2 | 分液漏斗、圆底烧瓶、集气瓶、尾气处理 |
| 10 | 化学实验 | 验证 Fe3+ 氧化性 | 2 | 实验方案完整可行 |
| **总分** | | | **20** | **满分** |

**Provider 2：MiMo-V2.5 (`mimo-v2.5`)**

| 题号 | 得分 | 备注 |
|------|------|------|
| 1-10 | 各 2 分 | |
| **总分** | **20** | 化学知识及格，联网搜索有时效性问题 |

MiMo 的化学准确率也是满分，但有一个奇特的问题：它的联网搜索结果中，模型会追加"我的知识截止到 2024 年"的声明。根因推测是 MiMo 的 RLHF 训练中强化了"诚实告知知识截止日期"的行为。这对化学知识影响不大（高中化学知识不会更新），但在联网搜索场景下会让学生困惑。

**Provider 3：DashScope Qwen (`qwen-turbo`)**

| 题号 | 得分 | 备注 |
|------|------|------|
| 4（配平 KMnO4+HCl）| 1 | 系数正确但漏写反应条件（加热）|
| 9（实验室制 Cl2）| 1 | 装置描述正确但未说明尾气处理 |
| 其余 | 各 2 分 | |
| **总分** | **18** | 及格，但细节偶尔遗漏 |

Qwen 不是"不会"——它是"会但不全"。漏写反应条件的概率约 20%。这个 20% 高于教师的 10% 容忍阈值，所以 Qwen 不能做主力模型，但可以做三级 fallback——偶尔用一次，用户能接受。

### 3. 四个工程维度的实测数据

只看准确率是不够的。一个模型准确率再高，如果一天挂 12 小时也没用。

**维度 1：API 稳定性（24 小时连续测试）**

| Provider | 可用率 | 平均延迟 | P99 延迟 |
|----------|--------|---------|---------|
| DeepSeek | 99.7% | 2.1s | 8.3s |
| MiMo | 98.2% | 3.5s | 15.2s |
| DashScope | 99.9% | 1.8s | 5.1s |

测试方法：连续 24 小时，每小时发一次请求。统计成功率和延迟分布。

关键发现：DeepSeek 有一次 12 小时故障（4 月 15-16 日），可用率直接掉到 0%。这次故障直接催生了三路 fallback 的设计——单 Provider 的可用率 99.7% 放到教学场景意味着每年有约 1 天无法使用，这是不可接受的。

**维度 2：成本**

| Provider | 输入 ¥/M token | 输出 ¥/M token | 单次对话估算 |
|----------|---------------|---------------|-------------|
| DeepSeek | 2 | 8 | 0.04 |
| MiMo | 4 | 16 | 0.08 |
| DashScope | 2 | 8 | 0.04 |

按教师每天 20 次对话估算：
- DeepSeek：月成本约 ¥24
- MiMo：月成本约 ¥48
- DashScope：月成本约 ¥24

三个 Provider 的总月成本约 ¥48，远低于种子教师的付费意愿（¥50-100/月）。成本不是瓶颈。

实际 1-3 月累计费用：DeepSeek ~¥120（~3000 次）、MiMo ~¥16（~200 次）、DashScope ~¥8（~100 次），合计约 ¥144。月均约 ¥48。

**维度 3：联网搜索能力**

| Provider | 是否支持 | 实际表现 |
|----------|---------|---------|
| DeepSeek | 不支持（API 不提供 `enable_search`）| |
| MiMo | 支持 `enable_search: True` | 能搜但追加"截至 2024 年"声明 |
| Bing HTTP 直接请求 | 支持 | 实时结果，无训练数据污染 |

最终方案：联网搜索用 Bing HTTP 直接搜原始结果，再用 DeepSeek 总结。完全绕过 MiMo 的时效性问题。这个决策在课程后面的 Session 中会落地。

**维度 4：视觉模型**

MiMo 是三个 Provider 中唯一支持多模态（图片输入）的。后续两个场景用到：OCR 答题卡识别（学生拍答题卡直接识别）、学生端拍照问化学题。但视觉识别准确率一般，实际重度依赖的是 MinerU OCR 管线，MiMo 的视觉只做兜底。

### 4. temperature 为什么设为 0.1？

LLM 的 temperature 参数控制输出的"随机性"：
- temperature = 0：每次输出完全一样（确定性）
- temperature = 1.0：输出有较大随机性
- 化学出题场景：教师需要的是"稳定可信"，不是"有创意"

temperature 0.1 接近确定性，但保留了一点点变化空间（避免模型在不确定时"瞎编一个确定答案"）。项目早期测试过 0.0 和 0.3：
- 0.0：部分模型 API 不支持完全确定性，会报错
- 0.3：有两次配平结果不一致，不可接受
- 0.1：最稳定且所有 Provider 都支持

### 5. fallback 优先级为什么是 MiMo → DashScope → DeepSeek？

这个顺序可能跟直觉相反——准确率最高的 DeepSeek 为什么排最后？

**不是按准确率排的，是按"挂了之后的影响"排的。**

- MiMo 挂的概率最高（98.2% 可用率），排在第一位，挂了就降级到 DashScope
- DashScope 稳定但细节会漏（18/20 分），适合做中间缓冲
- DeepSeek 准确率最高，但有一次 12 小时全挂的记录——如果真的挂了，前面两个还能顶着

实际调用中，日常约 80% 的请求走 DeepSeek（因为最便宜 + 最准确），Provider 选择不是强制走 fallback 链，而是按场景指定：
- 需要视觉理解 → 指定 MiMo
- 需要联网搜索 → Bing HTTP + DeepSeek 总结
- 普通对话 → 指定 DeepSeek

`generate_with_fallback` 是自动兜底，`generate_text(provider="xxx")` 是指定调用。

### 6. DeepSeek 12 小时故障事件的教训

这不是假设——2026 年 4 月 15 日晚到 16 日上午，DeepSeek API 全面不可用。开发者在凌晨 2 点发现所有请求返回 503。

这次故障的教训：
1. 单 Provider 是致命缺陷——必须有多路备份
2. fallback 不能是"手动切换"——凌晨教师用不了不会给你打电话，只会觉得"这软件坏了"
3. 自动 fallback 让用户无感知切换——延迟增加 1-2 秒，但不会中断服务

### 7. chemical_balance 审核工具的价值

这个工具不会很智能——它只是规则匹配——但它解决了 ChemAI 最关键的一个信任问题：

**"种子教师曾被 ChatGPT 的出题配平伤过一次，从此不信任 AI。"**

`chemical_balance` 不管 AI 出什么题，都在返回给教师之前做一次自动审核。如果审核未通过（配平错、漏条件），这个题目就不呈现。这相当于在 AI 和教师之间加了一道"安全检查"。

工具的局限性要让学生理解：
- 它能检查原子守恒和系数——这些问题 AI 通常不会犯
- 它很难判断反应是否在热力学上可行——这需要专业知识库
- 但它能抓住最低级的错误，这就是它的价值

---

## 课后产出检查

- [ ] `app/services/llm_service.py` 包含三个 Provider + fallback 机制
- [ ] `app/services/chemical_balance.py` 能够审核方程式的配平和反应条件
- [ ] `tests/test_llm_chemistry.py` 可以跑三个 Provider 的 10 题对比
- [ ] `.env` 中三个 API Key 全部有效
- [ ] `python -m app.services.llm_service` 能够调用 DeepSeek 并返回正确配平结果
- [ ] 学生能说出三个 Provider 各自的优缺点（DeepSeek 最准、DashScope 最稳、MiMo 有视觉）
- [ ] 学生理解 temperature 0.1 的意义和 fallback 优先级的设计理由

**下节课需要**：LLM 服务层完全可用。Session 3 将进行用户调研（角色扮演访谈 + JTBD 提取），Session 4-7 将陆续完成竞品分析、可行性论证、PRD 编写和原型设计，均依赖本节的 LLM 接入层。

---

## 补充内容 — 教师深度参考

### A. 为什么不用本地部署的小模型？

在项目 Day 1 的早期调研中，尝试过用本地小模型（参数量 ~7B，未记录具体名称）做配平测试。结果：配平错误率约 30%。原因分析：
- 小模型对化学符号的 tokenization 不友好——"Fe2O3" 可能被拆成 "Fe", "2", "O", "3" 四个 token
- 对多步骤推理（如配平 KMnO4 + HCl 的 5 个系数）能力不足
- 本地部署需要 GPU（至少 8GB 显存），增加了部署复杂度

选择云端 API 的核心原因：教师的电脑是普通办公电脑（8GB 内存、无独显），不具备本地运行大模型的条件。

### B. 如果学生问"为什么不直接用 ChatGPT？"

真实答案：
1. ChatGPT API 价格是 DeepSeek 的 3-5 倍
2. ChatGPT 对中文化学术语的理解不一定更好
3. DeepSeek 在中国的可用性更好（不需要特殊网络环境）
4. 数据安全考量——教师可能上传包含学生姓名的答题卡，DeepSeek 的国内部署在合规上更有利

### C. Provider 可用率的时间波动细节

| Provider | 白天可用率（8-22时）| 凌晨可用率 | 说明 |
|----------|-------------------|-----------|------|
| DeepSeek | 99.5% | 99.9% | 白天高并发时段略有波动 |
| MiMo | 98.0% | 98.5% | 波动不大，但整体偏低 |
| DashScope | 99.9% | 99.9% | 几乎无波动 |

### D. 成本详细计算

按实际 1-3 月使用数据推算单教师年成本：

| 场景 | 每天调用次数 | 每次成本 | 月成本 | 年成本 |
|------|------------|---------|--------|--------|
| 对话出题 | 15 | ¥0.04 | ¥18 | ¥216 |
| 联网搜索 | 3 | ¥0.06 | ¥5.4 | ¥65 |
| 视觉识别 | 2 | ¥0.08 | ¥4.8 | ¥58 |
| OCR 后处理 | 5 | ¥0.02 | ¥3 | ¥36 |
| **合计** | **25** | | **¥31** | **¥375** |

年成本 ¥375 约等于种子教师付费意愿年付 ¥600-1200 的下限。有足够的利润空间。

### E. 三路 fallback 的切换延迟数据

| 切换路径 | 额外延迟 | 用户感知 |
|---------|---------|---------|
| MiMo → DashScope | +0.5s | 无明显感知 |
| DashScope → DeepSeek | +0.8s | 可能有轻微延迟 |
| 全链路耗尽 | 超时 30s | 返回错误提示 |

正常情况下不会触发 fallback，三个 Provider 同时挂的概率极低。

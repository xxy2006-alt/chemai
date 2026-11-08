# ChemAgent OpenSpec — 第一期变更规划

## Change 概览

| # | Change | 大小 | 依赖 | 可独立验证 |
|---|--------|------|------|-----------|
| C1 | Provider 层 — LLM 适配器 | M | 无 | `pytest tests/agent/test_provider.py` |
| C2 | Agent 基础设施 — Registry + Memory + Persona | M | C1 | `pytest tests/agent/test_core.py` |
| C3 | Skills A — 配平/搜索/诊断/出题（复用现有代码）| M | C2 | `pytest tests/agent/test_skills_a.py` |
| C4 | Skills B — 答疑/实验/周报/试卷导入（新能力）| M | C2, C3 | `pytest tests/agent/test_skills_b.py` |
| C5 | Channel — FastAPI 端点 + 前端对接 | S | C3 | `curl /api/agent/chat` |
| C6 | MinerU — Docker 部署 + HTTP 服务封装 | S | 无 | `curl /api/import/paper` |
| C7 | P0/P1 修复 — 认证/假数据/curl/API | M | 无 | `curl /api/users/students` 应 401 |
| C8 | 前端 — AI 对话 UI | S | C5 | 浏览器打开 student_v2.html |

---

## C1: Provider 层 — LLM 适配器

### 目标
统一 LLM 调用接口，替换现有的 `subprocess.run(["curl", ...])`。

### 产出文件
```
agent/provider/
├── __init__.py
├── base.py          # LLMProvider 抽象类 (chat + chat_stream)
├── deepseek.py      # DeepSeek V4 Flash (deepseek-v4-flash)
├── zhipu.py         # 智谱 GLM-4.6V-FlashX (多模态) + GLM-4-Flash (文本)
└── dashscope.py     # 通义千问 qwen-turbo (备用)
```

### 接口规范
```python
class LLMProvider(ABC):
    @abstractmethod
    async def chat(self, messages, temperature, max_tokens, tools=None) -> ChatResult: ...
    @abstractmethod
    async def chat_stream(self, messages, temperature, max_tokens, tools=None) -> AsyncIterator[str]: ...
    @property
    @abstractmethod
    def model_name(self) -> str: ...

@dataclass
class ChatResult:
    content: str
    tool_calls: list[dict]
    usage: dict
    model: str
```

### 验收标准
- [ ] `DeepSeekProvider().chat([{"role":"user","content":"1+1=?"}])` 返回正确回答
- [ ] `ZhipuProvider().chat()` 文本调用正常
- [ ] `ZhipuProvider().chat()` 多模态（传入 image_url）正常
- [ ] `DashScopeProvider().chat()` 正常（已有 API Key）
- [ ] 流式 `chat_stream()` 三个 provider 都正常
- [ ] 3 次重试 + 指数退避（429 限流场景）
- [ ] 超时 60s 后抛出明确异常

---

## C2: Agent 基础设施 — Registry + Memory + Persona

### 目标
实现 Agent 核心调度层：Skill 装饰器注册、分层记忆、角色配置。

### 产出文件
```
agent/
├── __init__.py
├── skill_registry.py    # SkillRegistry + @skill.register() 装饰器
├── memory.py            # MemoryStack (working + episodic + profile)
├── core.py              # ChemAgent + AgentConfig + run/run_stream
├── personas/
│   ├── tutor.yaml
│   ├── teacher.yaml
│   └── parent.yaml
```

### 接口规范

**SkillRegistry:**
```python
registry = SkillRegistry()

@registry.register(
    name="balance_equation",
    description="审核化学方程式配平",
    parameters={"equation": "化学方程式字符串"}
)
async def balance_equation(equation: str) -> dict: ...

# 执行
result = await registry.execute("balance_equation", {"equation": "H2 + O2 = H2O"})

# 生成 LLM function calling 格式
tools = registry.to_openai_tools()
```

**MemoryStack:**
```python
memory = MemoryStack(max_working=20)
memory.add_turn("user", "盐类水解是什么")
memory.add_turn("assistant", "盐类水解是...")
memory.load_student("202610101")  # 从 DB 加载学生画像
ctx = memory.build_context("那怎么判断水解程度")  # → messages list
```

**ChemAgent:**
```python
agent = ChemAgent(AgentConfig(persona="tutor", provider="deepseek"))
result = await agent.run("Fe + O2 = Fe2O3 配平了吗")
# result.content = "这个方程式没有配平哦..."
# result.skill_calls = ["balance_equation"]
```

### 验收标准
- [ ] `@registry.register()` 装饰器正常注册
- [ ] `registry.to_openai_tools()` 生成正确的 function calling 格式
- [ ] `MemoryStack` 滑动窗口正常（超过 20 轮旧消息被丢弃）
- [ ] `memory.load_student()` 从数据库加载学生画像
- [ ] `ChemAgent.run()` Think → Route → Execute 循环正常
- [ ] `ChemAgent.run_stream()` SSE 流式输出正常
- [ ] 3 个 persona yaml 加载正常，system prompt 正确注入

---

## C3: Skills A — 复用现有代码

### 目标
将已有的 4 个能力封装为 Skill，零新逻辑，纯适配。

### 产出文件
```
agent/skills/
├── __init__.py
├── balance.py       # → app/services/chemical_balance.py
├── search.py        # → app/services/exam_bank.py
├── diagnose.py      # → app/services/llm_service.py + DB
└── generate.py      # → app/services/llm_service.py
```

### 各 Skill 规范

**balance_equation:**
```python
@registry.register(
    name="balance_equation",
    description="审核化学方程式是否配平。输入化学方程式字符串，返回配平结果。",
    parameters={"equation": "化学方程式，如 '2H2 + O2 = 2H2O'"}
)
async def balance_equation(equation: str) -> dict:
    from app.services.chemical_balance import audit_chemical_equation
    return audit_chemical_equation(equation)
```

**search_exam_bank:**
```python
@registry.register(
    name="search_exam_bank",
    description="搜索历年高考真题。按知识点、年份、难度筛选。",
    parameters={
        "keyword": "搜索关键词（知识点名称）",
        "year": "年份（可选）",
        "difficulty": "难度 easy/medium/hard（可选）",
        "limit": "返回数量，默认5"
    }
)
async def search_exam_bank(keyword: str, year: int = None, difficulty: str = None, limit: int = 5) -> dict:
    from app.services.exam_bank import exam_bank_service
    results = exam_bank_service.search_questions(
        knowledge_point=keyword, difficulty=difficulty, limit=limit
    )
    return {"total": len(results), "questions": [...]}
```

**diagnose_barrier:**
```python
@registry.register(
    name="diagnose_barrier",
    description="诊断学生的化学学习障碍类型（概念理解/审题/表述），给出干预建议。",
    parameters={
        "student_id": "学生ID",
        "exam_id": "考试ID（可选）"
    }
)
async def diagnose_barrier(student_id: str, exam_id: str = None) -> dict:
    # 1. 从 DB 查学生答题记录
    # 2. 调 LLM 分析障碍类型
    # 3. 返回诊断 + 干预建议
```

**generate_questions:**
```python
@registry.register(
    name="generate_questions",
    description="根据知识点和难度生成化学练习题。",
    parameters={
        "knowledge_points": "知识点列表，逗号分隔",
        "difficulty": "难度 easy/medium/hard",
        "quantity": "题目数量，默认5"
    }
)
async def generate_questions(knowledge_points: str, difficulty: str = "medium", quantity: int = 5) -> dict:
    # 调 DeepSeek LLM 生成题目
    # 自动调 balance_equation 审核生成的方程式
```

### 验收标准
- [ ] `balance_equation("2H2 + O2 = 2H2O")` → passed
- [ ] `balance_equation("H2 + O2 = H2O")` → blocked
- [ ] `search_exam_bank("盐类水解")` → 返回 N 条真题
- [ ] `diagnose_barrier("202610101")` → 返回障碍类型 + 置信度 + 建议
- [ ] `generate_questions("盐类水解", "medium", 3)` → 返回 3 道题 + 自动审核结果

---

## C4: Skills B — 新能力

### 目标
实现 4 个需要新逻辑的 Skill。

### 产出文件
```
agent/skills/
├── tutor.py          # 答疑辅导（引导式教学）
├── experiment.py     # 化学实验模拟
├── weekly_report.py  # 家长周报
└── import_exam.py    # 试卷导入（集成 MinerU）
```

### 各 Skill 规范

**chemistry_tutor:**
- 输入：学生问题文本 + 学生画像
- 行为：不直接给答案。分析学生卡在哪一步 → 引导思考 → 分步讲解
- 输出：教学对话文本
- 调用：DeepSeek LLM（纯文本）

**simulate_experiment:**
- 输入：实验名称（如"钠与水的反应"）
- 行为：生成实验步骤 → 预测现象 → 写化学方程式 → 解释原理 → 安全提醒
- 输出：结构化实验报告
- 调用：DeepSeek LLM + balance_equation 自动审核

**weekly_report:**
- 输入：student_id
- 行为：查 DB → 本周练习记录 → 正确率变化 → 薄弱知识点 → 生成家长版报告
- 输出：通俗易懂的周报（不含教育学术语）
- 调用：DB 聚合 + DeepSeek LLM

**import_exam_paper:**
- 输入：PDF 文件路径 + 试卷来源/年份
- 行为：调 MinerU 解析 PDF → 提取题目 → 化学审核 → 入库
- 输出：提取数量 + 审核通过数 + 待审核列表
- 调用：MinerU HTTP API（C6 提供）

### 验收标准
- [ ] `chemistry_tutor` 回答引导式，不直接给答案
- [ ] `simulate_experiment("钠与水反应")` 生成完整实验报告
- [ ] `weekly_report("202610101")` 生成家长可读的周报
- [ ] `import_exam_paper(pdf_path, "湖南卷", 2025)` 返回提取结果

---

## C5: Channel — FastAPI 端点 + 前端对接

### 目标
暴露 `/api/agent/chat` 端点，前端可调用。

### 产出文件
```
agent/channel/
├── __init__.py
└── fastapi_sse.py     # APIRouter + 请求/响应模型
```

### API 规范

**POST /api/agent/chat（非流式）**
```json
// Request
{
  "persona": "tutor",
  "message": "盐类水解是什么？",
  "student_id": "202610101",       // 可选，加载学生画像
  "history": [                      // 可选，对话历史
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}

// Response
{
  "content": "盐类水解是指...",
  "skill_calls": ["chemistry_tutor"],
  "tokens_used": 342
}
```

**POST /api/agent/chat/stream（流式 SSE）**
```json
// Request 同上
// Response: text/event-stream
// data: {"delta": "盐"} \n\n
// data: {"delta": "类"} \n\n
// ...
// data: [DONE] \n\n
```

### 前端对接
- `student_v2.html`：加"AI 助教"按钮 → 弹出聊天面板
- `teacher_v2.html`：加"AI 教研助手"入口
- 家长端暂时只有 API，前端后续

### 验收标准
- [ ] `curl -X POST /api/agent/chat -d '{"persona":"tutor","message":"你好"}'` → 200
- [ ] `curl -X POST /api/agent/chat/stream ...` → SSE 流式输出
- [ ] persona=tutor 时 system prompt 正确（引导式）
- [ ] persona=teacher 时 system prompt 正确（数据分析）
- [ ] persona=parent 时只返回自己孩子的数据

---

## C6: MinerU — Docker 部署 + HTTP 服务

### 目标
MinerU 独立容器化，ChemAI 通过 HTTP 调用。

### 产出文件
```
docker/
├── docker-compose.yml       # MinerU + ChemAI 编排
└── mineru/
    └── Dockerfile            # MinerU 容器（基于官方镜像）

app/services/
└── mineru_service.py         # MinerU HTTP 客户端封装
```

### mineru_service.py 接口
```python
class MinerUClient:
    def __init__(self, base_url: str = "http://mineru:8080"):
        ...

    async def extract_questions(self, pdf_path: str) -> list[dict]:
        """
        上传 PDF → MinerU 解析 → 返回结构化题目列表
        [{"number": "T1", "content": "...", "options": [...], "answer": "A", ...}, ...]
        """

    async def extract_text(self, pdf_path: str) -> str:
        """纯文本提取（用于非试卷 PDF）"""
```

### 验收标准
- [ ] `docker-compose up` 启动 MinerU + ChemAI
- [ ] `MinerUClient.extract_questions(pdf)` 返回结构化题目
- [ ] 化学方程式被正确识别（上下标、反应条件）
- [ ] 处理错误的 PDF（加密、扫描质量差、非试卷）返回明确错误

---

## C7: P0/P1 修复

### 目标
修验证报告中的关键问题。

### 修复清单

| # | 文件 | 问题 | 修复 |
|---|------|------|------|
| 7.1 | `app/main.py` | CORS * + JWT 不生效 | 白名单 + 中间件强制校验 |
| 7.2 | `app/services/ocr_service.py` | `_mock_*` 返回假数据 | 删除所有 mock 函数，失败返回错误 |
| 7.3 | `app/services/llm_service.py` | `subprocess.run(["curl",...])` | 替换为 `agent/provider/dashscope.py` |
| 7.4 | `app/api/diagnosis.py` | 硬编码学生数据 | 从 DB 读 |
| 7.5 | `app/api/question.py` | `generate` Pydantic 校验失败 | 修复 Pydantic 模型 |
| 7.6 | `app/api/exam_bank.py` | `search` Invalid HTTP request | 修复路由 |

### 验收标准
- [ ] `curl /api/users/students` 无 token → 401
- [ ] `curl -H "Authorization: Bearer $TOKEN" /api/users/students` → 200
- [ ] OCR 无 API Key 时返回 `{"success": false, "error": "OCR 服务未配置"}`
- [ ] `POST /api/question/generate` → 200（不再报 Pydantic 错误）
- [ ] `GET /api/exam-bank/search?keyword=盐` → 返回真题结果

---

## C8: 前端 — AI 对话 UI

### 目标
学生端和教师端各加一个 AI 对话入口。

### 产出文件
```
frontend/
├── components/
│   ├── chat-panel.js    # 可复用聊天组件
│   └── chat-panel.css   # 聊天面板样式
├── student_v2.html      # 修改：加 AI 助教按钮
└── teacher_v2.html      # 修改：加 AI 教研助手按钮
```

### UI 交互
```
[学生端]
┌─────────────────────────┐
│  练习区                  │
│                         │
│  ┌──────────────────┐   │
│  │  🤖 AI 助教      │   │
│  │  ─────────────── │   │
│  │  学生: 盐类水解.. │   │
│  │  助教: 好问题!   │   │
│  │  先想想：盐溶于  │   │
│  │  水后...         │   │
│  │  ─────────────── │   │
│  │  [输入框]  [发送] │   │
│  └──────────────────┘   │
└─────────────────────────┘
```

### 验收标准
- [ ] 学生端点击"AI 助教"打开聊天面板
- [ ] 发送消息 → 流式显示回复（逐字输出）
- [ ] 支持多轮对话（上下文保持）
- [ ] 教师端点击"AI 教研助手"打开面板
- [ ] 教师端可以问"三班电离平衡掌握情况"

---

## 执行顺序

```
C1 (Provider)
 │
 ├── C6 (MinerU) ← 并行，无依赖
 │
 └── C2 (Agent基础设施)
      │
      ├── C3 (Skills A — 复用)
      │    │
      │    └── C4 (Skills B — 新能力)
      │         │
      │         └── C5 (Channel + 前端)
      │
      └── C7 (P0/P1修复) ← 与 C2-C5 并行

C8 (前端UI) ← 等 C5 完成后做
```

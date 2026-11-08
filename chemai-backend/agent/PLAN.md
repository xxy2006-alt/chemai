# ChemAgent 详细实现计划

## 目录

1. [文件清单与接口](#1-文件清单与接口)
2. [数据流时序图](#2-数据流时序图)
3. [与现有 API 对接](#3-与现有-api-对接)
4. [迁移路径](#4-迁移路径)
5. [实施顺序](#5-实施顺序)

---

## 1. 文件清单与接口

### 1.1 `agent/core.py` — Agent Loop（~80 行）

```python
from dataclasses import dataclass, field
from typing import AsyncIterator

@dataclass
class AgentConfig:
    persona: str           # "tutor" / "teacher" / "parent"
    provider: str          # "dashscope" / "zhipu"
    max_turns: int = 5      # 防止无限循环
    temperature: float = 0.7

class ChemAgent:
    """
    核心循环：

    用户输入 → Think(LLM决策) → Route(意图分发)
                                  ├─ reply → 直接返回给用户
                                  └─ use_skill → Execute(工具) → Observe(观察结果)
                                       └─ 可能需要 LLM 再加工 → 返回给用户

    流式模式（stream=True）：
    Think 阶段流式输出思考过程，Execute 阶段发事件，最终回复流式输出
    """

    def __init__(self, config: AgentConfig):
        ...

    async def run(self, user_input: str, history: list[dict] = None) -> AgentResponse:
        """非流式执行"""
        ...

    async def run_stream(self, user_input: str, history: list[dict] = None) -> AsyncIterator[str]:
        """流式执行，SSE 输出"""
        ...
```

**AgentResponse 结构：**

```python
@dataclass
class AgentResponse:
    action: str            # "reply" | "use_skill"
    content: str           # 最终回复文本
    skill_calls: list      # 调用了哪些 skill
    tokens_used: int       # token 消耗
```

**Think 阶段 System Prompt 结构：**

```
你是 ChemAI 化学教学 Agent。

## 你的角色
{persona.description}

## 可用工具
{skill_registry.to_prompt()}   ← 自动从注册的 skill 生成

## 学生信息（如适用）
{memory.get_student_context()}

## 输出格式
决定下一步行动，返回 JSON:
- 直接回复: {"action": "reply", "content": "你的回复"}
- 调用工具: {"action": "use_skill", "skill": "技能名", "args": {...}}
```

---

### 1.2 `agent/skill_registry.py` — Skill 注册器（~50 行）

```python
from typing import Callable, Any

class SkillRegistry:
    """
    装饰器注册模式。每个 skill 是一个 async 函数。

    用法:
        registry = SkillRegistry()

        @registry.register(
            name="balance_equation",
            description="审核化学方程式是否配平，返回配平结果",
            parameters={"equation": "化学方程式字符串，如 'H2 + O2 = H2O'"}
        )
        async def balance_equation(equation: str) -> dict:
            from app.services.chemical_balance import audit_chemical_equation
            return audit_chemical_equation(equation)
    """

    def register(self, name: str, description: str, parameters: dict[str, str]):
        """装饰器：注册一个 skill"""
        ...

    async def execute(self, name: str, args: dict) -> dict:
        """执行指定 skill"""
        ...

    def to_prompt(self) -> str:
        """生成 LLM tool-use prompt（OpenAI function calling 格式）"""
        ...
```

**初始注册 7 个 Skill（全部第一期交付）：**

| Skill 名 | 功能 | 调用的现有代码 | 期数 |
|----------|------|---------------|------|
| `balance_equation` | 化学方程式配平审核 | `app/services/chemical_balance.py` | 第1期 |
| `diagnose_barrier` | 学生障碍诊断 | `app/services/llm_service.py` + DB | 第1期 |
| `generate_questions` | AI 出题 | `app/services/llm_service.py` | 第1期 |
| `search_exam_bank` | 历年真题搜索 | `app/services/exam_bank.py` | 第1期 |
| `chemistry_tutor` | 答疑辅导 | LLM + 知识图谱 | 第1期 |
| `simulate_experiment` | 化学实验模拟对话 | LLM 生成步骤/现象/结论 | 第1期 |
| `weekly_report` | 孩子本周学了什么 | DB 聚合 + LLM 生成 | 第1期 |

---

### 1.3 `agent/memory.py` — 记忆管理（~60 行）

```python
from collections import deque
import json, time

class MemoryStack:
    """
    分层记忆：
    - working: deque(maxlen=20) — 当前对话的最近 20 轮
    - episodic: dict — 关键事件（诊断结果、考试记录）
    - student_profile: dict — 学生画像（障碍类型、薄弱知识点）

    不引入向量数据库。20 轮对话 + 结构化 profile 对化学教学足够。
    """

    def __init__(self, max_working: int = 20):
        self.working = deque(maxlen=max_working)  # [(role, content), ...]
        self.episodic = {}    # {"last_diagnosis": {...}, "recent_exam": {...}}
        self.student_profile = {}  # {"barrier_type": "concept", "weak_kps": [...]}

    def add_turn(self, role: str, content: str):
        ...

    def build_context(self, user_input: str) -> list[dict]:
        """构建发送给 LLM 的完整上下文"""
        messages = []
        # 1. System prompt（由 persona 层注入）
        # 2. 学生画像（如果有）
        if self.student_profile:
            messages.append({"role": "system", "content": f"学生画像: {json.dumps(self.student_profile, ensure_ascii=False)}"})
        # 3. 最近对话
        for role, content in self.working:
            messages.append({"role": role, "content": content})
        # 4. 当前输入
        messages.append({"role": "user", "content": user_input})
        return messages

    def load_student(self, student_id: str):
        """从数据库加载学生画像"""
        ...
```

---

### 1.4 `agent/provider/base.py` — LLM Provider 抽象接口（~30 行）

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator

class LLMProvider(ABC):
    """LLM Provider 抽象。加新模型 = 实现这个接口。"""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        tools: list[dict] = None      # OpenAI function calling 格式
    ) -> dict:
        """非流式调用，返回 {"content": "...", "tool_calls": [...], "usage": {...}}"""
        ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        tools: list[dict] = None
    ) -> AsyncIterator[str]:
        """流式调用，yield SSE chunks"""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...
```

### 1.5 `agent/provider/dashscope.py` — 通义千问实现（~80 行）

```python
import httpx, json, os
from .base import LLMProvider

class DashScopeProvider(LLMProvider):
    """
    通义千问 / DashScope。

    API: https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
    模型: qwen-turbo / qwen-plus / qwen-max

    用 httpx.AsyncClient 替换现有的 subprocess.run(["curl", ...])
    """

    def __init__(self, model: str = "qwen-turbo"):
        self.api_key = os.getenv("DASHSCOPE_API_KEY", "")
        self.base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        self.model = model
        self._client = None  # lazy init

    @property
    def model_name(self) -> str:
        return f"dashscope/{self.model}"

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=60.0
            )
        return self._client

    async def chat(self, messages, temperature=0.7, max_tokens=2048, tools=None):
        client = await self._get_client()
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        for attempt in range(3):  # 重试 3 次
            try:
                resp = await client.post("/chat/completions", json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    choice = data["choices"][0]
                    return {
                        "content": choice["message"].get("content", ""),
                        "tool_calls": choice["message"].get("tool_calls", []),
                        "usage": data.get("usage", {}),
                        "model": data.get("model", "")
                    }
                elif resp.status_code == 429:
                    await asyncio.sleep(2 ** attempt)  # 指数退避
                else:
                    raise Exception(f"API error {resp.status_code}: {resp.text}")
            except httpx.TimeoutException:
                if attempt == 2:
                    raise
                await asyncio.sleep(1)

    async def chat_stream(self, messages, temperature=0.7, max_tokens=2048, tools=None):
        client = await self._get_client()
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }
        if tools:
            payload["tools"] = tools

        async with client.stream("POST", "/chat/completions", json=payload) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    yield data_str  # 原样透传 SSE
```

### 1.6 `agent/provider/zhipu.py` — 智谱 GLM 实现（~60 行）

```python
class ZhipuProvider(LLMProvider):
    """
    智谱 GLM。

    API: https://open.bigmodel.cn/api/paas/v4/chat/completions
    模型: glm-4-flash / glm-4 / glm-4-plus

    同 DashScopeProvider 结构，换 base_url 和认证方式。
    """

    def __init__(self, model: str = "glm-4-flash"):
        self.api_key = os.getenv("ZHIPU_API_KEY", "")
        self.base_url = "https://open.bigmodel.cn/api/paas/v4"
        self.model = model
        ...
```

---

### 1.7 `agent/personas/` — 角色配置（YAML，第一期 3 个）

**`tutor.yaml`：**

```yaml
name: 化学助教
description: 面向学生的 AI 化学辅导老师
system_prompt: |
  你是 ChemAI 的 AI 化学助教，正在辅导一名高中生。

  ## 你的教学原则
  1. 引导式教学：不直接给答案，先问学生"你是怎么想的？"
  2. 分步讲解：复杂问题拆成 2-3 步，每步确认学生理解后再继续
  3. 联系考点：提及这道题在高考/会考中的常见题型
  4. 适度鼓励：对的思路要肯定，错的要温和纠正
  5. 简洁清晰：单次回复不超过 500 字
  6. 不确定时说不知道：不要编造化学知识

  ## 学生画像
  {student_profile}

  ## 可用工具
  {tools}
available_skills:
  - chemistry_tutor
  - balance_equation
  - search_exam_bank
data_access:
  can_see: [own_scores, own_barriers, own_practice]
  cannot_see: [other_students, class_stats, teacher_notes]
```

**`teacher.yaml`：**

```yaml
name: 教研助手
description: 面向教师的 AI 教学分析助手
system_prompt: |
  你是 ChemAI 的 AI 教研助手，正在协助一名高中化学教师。

  ## 你的能力
  1. 分析班级学情数据，找出薄弱知识点
  2. 生成诊断报告和教学建议
  3. 审核 AI 生成的题目质量
  4. 推荐历年真题作为教学素材

  ## 原则
  - 数据驱动：建议基于实际学情数据
  - 可操作：给出具体的课堂干预建议
  - 简洁：不要教育理论长篇大论
available_skills:
  - diagnose_barrier
  - generate_questions
  - search_exam_bank
  - balance_equation
data_access:
  can_see: [class_stats, all_student_scores, barrier_distribution, exam_bank]
  cannot_see: []
```

**`parent.yaml`：**

```yaml
name: 家长助手
description: 面向家长的 AI 学情报告助手
system_prompt: |
  你是 ChemAI 的 AI 家长助手，正在向一位家长汇报孩子的化学学习情况。

  ## 你的能力
  1. 生成本周学习总结——学了哪些知识点，掌握情况如何
  2. 解释孩子的学习障碍类型，用通俗语言说明（不要用教育学术语）
  3. 给出家长可以在家配合的具体建议
  4. 对比班级平均水平，但重点放在孩子的进步上

  ## 原则
  - 鼓励为主：先肯定进步，再提建议
  - 通俗易懂：家长不一定懂化学，用生活化语言
  - 可操作：告诉家长具体做什么（如"每天检查孩子的错题本"）
  - 保护隐私：只汇报自己孩子的数据，不透露其他学生信息
  - 不制造焦虑：用"成长空间"代替"问题"
available_skills:
  - weekly_report
  - diagnose_barrier
data_access:
  can_see: [own_child_scores, own_child_barriers, own_child_practice]
  cannot_see: [other_students, class_stats, teacher_notes]
```

### 1.8 `agent/provider/deepseek.py` — DeepSeek 实现（~60 行）

```python
class DeepSeekProvider(LLMProvider):
    """
    DeepSeek — 处理所有纯文本任务（无多模态能力）。

    API: https://api.deepseek.com/v1/chat/completions
    模型: deepseek-v4-flash
    用途: 答疑、出题、诊断、报告等所有文本化学教学任务
    """

    def __init__(self, model: str = "deepseek-v4-flash"):
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = "https://api.deepseek.com/v1"
        self.model = model
        ...
```

---

### 1.8 `agent/channel/fastapi_sse.py` — Web 渠道适配（~40 行）

```python
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from agent.core import ChemAgent, AgentConfig

router = APIRouter(prefix="/api/agent", tags=["ChemAgent"])

@router.post("/chat")
async def agent_chat(request: ChatRequest):
    """
    非流式聊天。

    POST /api/agent/chat
    {"persona": "tutor", "message": "盐类水解是什么？", "history": [...]}
    """
    config = AgentConfig(persona=request.persona, provider="dashscope")
    agent = ChemAgent(config)
    agent.memory.working.extend(request.history or [])
    # 如果有 student_id，加载学生画像
    if request.student_id:
        agent.memory.load_student(request.student_id)
    result = await agent.run(request.message)
    return {"content": result.content, "skill_calls": result.skill_calls}


@router.post("/chat/stream")
async def agent_chat_stream(request: ChatRequest):
    """
    流式聊天（SSE）。

    POST /api/agent/chat/stream
    {"persona": "tutor", "message": "帮我配平 Fe + O2 = Fe2O3", "student_id": "202610101"}
    """
    config = AgentConfig(persona=request.persona, provider="dashscope")
    agent = ChemAgent(config)
    if request.student_id:
        agent.memory.load_student(request.student_id)

    async def generate():
        async for chunk in agent.run_stream(request.message, request.history):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

---

## 2. 数据流时序图

### 2.1 学生提问"帮我配平 Fe + O2 = Fe2O3"

```
  学生 (Web)          FastAPI           ChemAgent           DashScope       Skill
    │                   │                   │                   │             │
    │ POST /chat/stream │                   │                   │             │
    │──────────────────►│                   │                   │             │
    │                   │ AgentConfig(      │                   │             │
    │                   │   persona=tutor)  │                   │             │
    │                   │──────────────────►│                   │             │
    │                   │                   │                   │             │
    │                   │                   │ 1. Think          │             │
    │                   │                   │ messages=[system, │             │
    │                   │                   │   "学生画像:...", │             │
    │                   │                   │   "配平 Fe+O2=   │             │
    │                   │                   │    Fe2O3"]        │             │
    │                   │                   │──────────────────►│             │
    │                   │                   │                   │             │
    │                   │                   │  {"action":       │             │
    │                   │                   │   "use_skill",    │             │
    │                   │                   │   "skill":        │             │
    │                   │                   │   "balance_       │             │
    │                   │                   │   equation",      │             │
    │                   │                   │   "args": {       │             │
    │                   │                   │     "equation":   │             │
    │                   │                   │     "Fe+O2=Fe2O3" │             │
    │                   │                   │   }}              │             │
    │                   │                   │◄──────────────────│             │
    │                   │                   │                   │             │
    │                   │                   │ 2. Execute skill  │             │
    │                   │                   │──────────────────────────────────►│
    │                   │                   │                   │             │
    │                   │                   │  {"is_balanced":  │             │
    │                   │                   │   false,          │             │
    │                   │                   │   "message":      │             │
    │                   │                   │   "Fe:左1右2,     │             │
    │                   │                   │    O:左2右3"}     │             │
    │                   │                   │◄──────────────────────────────────│
    │                   │                   │                   │             │
    │                   │                   │ 3. Observe        │             │
    │                   │                   │ 把 skill 结果     │             │
    │                   │                   │ 喂回 LLM 生成     │             │
    │                   │                   │ 友好回复          │             │
    │                   │                   │──────────────────►│             │
    │                   │                   │                   │             │
    │                   │                   │  "这个方程式没有  │             │
    │                   │                   │   配平哦~ 让我    │             │
    │                   │                   │   教你：左边 Fe   │             │
    │                   │                   │   原子1个..."     │             │
    │                   │                   │◄──────────────────│             │
    │                   │                   │                   │             │
    │  SSE stream        │                   │                   │             │
    │◄──────────────────│                   │                   │             │
```

### 2.2 学生问"盐类水解是什么"（不需要工具）

```
  学生                ChemAgent              DashScope
    │                   │                      │
    │ "盐类水解是      │                      │
    │  什么？"         │                      │
    │──────────────────►│                      │
    │                   │ Think                │
    │                   │─────────────────────►│
    │                   │                      │
    │                   │ {"action": "reply",  │
    │                   │  "content": "盐类    │
    │                   │  水解就是..."}       │
    │                   │◄─────────────────────│
    │                   │                      │
    │  直接流式输出     │                      │
    │◄──────────────────│                      │
```

---

## 3. 与现有 API 对接

### 3.1 对接方式：共存，不破坏

```
现有前端 (student_v2.html)
    │
    ├── 调用现有 API（不变）
    │   ├── POST /api/practice/student/{id}/tasks
    │   ├── GET  /api/report/student/{exam_id}/{student_id}
    │   └── ...
    │
    └── 调用新 Agent API（新增）
        ├── POST /api/agent/chat          ← 对话式交互
        └── POST /api/agent/chat/stream   ← 流式对话（SSE）
```

### 3.2 前端集成示例

```javascript
// 在 student_v2.html 中加一个"AI 助教"对话框

async function askTutor(question) {
    const response = await fetch('/api/agent/chat/stream', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            persona: 'tutor',
            message: question,
            student_id: currentStudentId,
            history: conversationHistory
        })
    });

    // SSE 流式读取
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    while (true) {
        const {done, value} = await reader.read();
        if (done) break;
        const text = decoder.decode(value);
        // 逐字显示到聊天框
        appendToChatBubble(text);
    }
}
```

### 3.3 `app/main.py` 注册新路由

```python
# 在现有路由注册后加两行：
from agent.channel.fastapi_sse import router as agent_router
app.include_router(agent_router)
```

---

## 4. 迁移路径

### 4.1 不改的代码

| 文件 | 原因 |
|------|------|
| `app/models/database.py` | 数据模型完整，Agent 直接读 |
| `app/services/chemical_balance.py` | 作为 Skill 被调用，代码零改动 |
| `app/services/exam_bank.py` | 同上 |
| `app/api/*` (除 hermes_proxy) | 现有 API 保持不变，前端继续用 |
| `frontend/*` | 不改，Agent 是新增功能 |
| `data/*` | 题库、知识图谱不动 |

### 4.2 需要改的代码

| 文件 | 改什么 | 为什么 |
|------|--------|--------|
| `app/services/llm_service.py` | **重写** — 删除 subprocess+curl，改为调用 `agent/provider/dashscope.py` | 消除反模式 |
| `app/api/hermes_proxy.py` | **删除 /chemistry-chat 端点**，由 Agent 的 `/api/agent/chat` 替代 | 统一入口 |
| `app/main.py` | **加 2 行**注册 agent_router | — |

### 4.3 需要删除的代码

| 文件 | 原因 |
|------|------|
| `hermes-agent-main/` (整个目录) | Windows 不兼容，被 ChemAgent 替代 |
| `app/api/hermes_proxy.py` 中的 Hermes 代理部分 | 不再需要 |
| `app/services/ocr_service.py` 中的 `_mock_*` 函数 | 假数据删除 |
| `app/api/diagnosis.py` 中的硬编码学生数据 | 从数据库读 |

---

## 5. 实施顺序

### 第 1 批：地基（~60 分钟）

```
agent/
├── __init__.py
├── provider/
│   ├── __init__.py
│   ├── base.py          # LLMProvider 抽象
│   ├── dashscope.py     # 通义千问（httpx，替换 curl）
│   └── deepseek.py      # DeepSeek（第一期交付）
├── skill_registry.py    # 装饰器注册
├── memory.py            # 记忆栈
└── personas/
    ├── tutor.yaml       # 学生端
    ├── teacher.yaml     # 教师端
    └── parent.yaml      # 家长端（第一期交付）
```

**产出：** `DashScopeProvider` 可独立测试，不再依赖 subprocess+curl。

### 第 2 批：Agent Core（~30 分钟）

```
agent/
├── core.py              # ChemAgent + AgentConfig
└── channel/
    ├── __init__.py
    └── fastapi_sse.py   # /api/agent/chat, /api/agent/chat/stream
```

**产出：** `POST /api/agent/chat` 可被 curl 测试。

### 第 3 批：Skills 注册 + 迁移旧代码（~40 分钟）

```
agent/skills/
├── __init__.py
├── balance.py           # 调 chemical_balance.audit_chemical_equation
├── search.py            # 调 exam_bank.search_questions
├── tutor.py             # 答疑（调 LLM）
├── diagnose.py          # 调 llm_service + DB
├── generate.py          # 调 llm_service
├── experiment.py        # 化学实验模拟（第一期交付）
└── weekly_report.py     # 家长周报（第一期交付）
```

**同时：**
- 删 `app/services/llm_service.py` 中的 `subprocess.run(["curl", ...])`
- 删 `hermes_proxy.py` 中的 `/chemistry-chat` 端点
- `app/main.py` 注册 agent_router

### 第 4 批：修 P0/P1 问题（~30 分钟）

- P0: 认证中间件生效
- P0: 删 OCR mock 数据
- P1: 修 AI 出题 Pydantic 校验
- P1: 修真题搜索 API

### 第 5 批：前端对接（~20 分钟）

- `student_v2.html` 加 AI 助教对话框
- `teacher_v2.html` 加 AI 教研助手入口

### 第 6 批：测试（~20 分钟）

```
tests/agent/
├── test_core.py         # Agent Loop 单元测试
├── test_skills.py       # 每个 Skill 的单元测试
└── test_integration.py  # HTTP → Agent → Skill → LLM 端到端
```

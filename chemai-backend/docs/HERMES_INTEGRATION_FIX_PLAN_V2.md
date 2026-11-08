# ChemAI ChemAI Agent 集成修复计划 v2

> 创建日期：2026-04-16
> 基于：技术验证报告 v1
> 项目：智辅化学 ChemAI
> 目标：彻底解决所有架构断裂问题，建立完整工作流

---

## 一、技术验证结果汇总

### 1.1 发现的问题

| # | 问题 | 严重程度 | 根因 |
|---|------|----------|------|
| **P1** | chem_skills 未注册到 ChemAI Agent | 🔴 严重 | Skills 未调用 registry.register() |
| **P2** | SSE 事件格式完全不兼容 | 🔴 严重 | 前端期望 vs 后端发送的协议不匹配 |
| **P3** | 缺少 chemistry toolset 定义 | 🟡 中等 | toolsets.py 未包含化学 Tools |
| **P4** | chemistry_tools.py 未创建 | 🟡 中等 | 包装层缺失 |
| **P5** | 前端 TaskType prompt 可靠性 | 🟡 中等 | LLM 理解 prompt 并调用 Tool 的映射不确定 |

### 1.2 SSE 事件格式不兼容详解

**前端 `hermes.js` 期望的格式**：
```javascript
// 期望的事件结构
{ type: 'chunk', delta: { content: 'xxx' } }
{ type: 'tool_call', tool: 'xxx', params: {...} }
{ type: 'tool_result', result: {...} }
{ needs_confirmation: true, confirm_type: 'xxx' }
```

**ChemAI Agent `api_server.py` 实际发送的格式**：
```python
# OpenAI 兼容的 SSE 格式
{"id": "chatcmpl-xxx", "object": "chat.completion.chunk",
 "choices": [{"index": 0, "delta": {"content": "xxx"}, ...}]}

# Tool progress (非标准事件)
"event: hermes.tool.progress\ndata: {"tool": "xxx", ...}\n\n"
```

**结论**：这是两种完全不同的协议，前端无法正确解析 Agent 的响应。

---

## 二、解决方案架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Frontend (SPA)                                  │
│                         hermes.js (事件协议适配层)                           │
│                                                                             │
│  原设计: HermesEventType.{THINKING, TOOL_CALL, ...}                        │
│  新需求: 适配 ChemAI Agent 的 OpenAI SSE 格式                               │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │ OpenAI SSE 格式
              ┌──────────────────┴──────────────────┐
              │ 8642 (ChemAI Agent)               │ 8001 (FastAPI)
              ▼                                   ▼
┌─────────────────────────┐       ┌───────────────────────────────────────┐
│  hermes-agent-main      │       │        chemai-backend                  │
│                         │       │                                        │
│  新增: chemistry_tools  │       │  chem_skills/                        │
│  - parse_pdf_questions  │       │    - chemistry_parser                  │
│  - exam_generate        │       │    - chemistry_exam                    │
│  - exam_audit           │       │    - chemistry_diagnosis               │
│  - exam_search_historical│      │                                        │
│  - diagnosis_barrier_...│       │  FastAPI Backend:                       │
│                         │       │    - /api/ocr/*                        │
│  SSE: OpenAI 格式       │       │    - /api/question/*                   │
│  ⚠️ 需要验证 P2 适配    │       │    - /api/diagnosis/*                  │
└─────────────────────────┘       └───────────────────────────────────────┘
```

### 2.2 核心决策

**决策 1：修改前端 `hermes.js` 以适配 ChemAI Agent 的 OpenAI SSE 格式**

原因：
- ChemAI Agent 是第三方框架，修改其核心代码会导致升级困难
- 前端适配成本更低，且不影响其他项目使用 ChemAI Agent
- ChemAI Agent 的 `/v1/chat/completions` 是标准 OpenAI 格式，无法改变

**决策 2：使用 `/v1/chat/completions` 而非 `/v1/runs`**

原因：
- `/v1/runs` 是 Hermes 特有的 API，设计用于长时间运行任务
- `/v1/chat/completions` 是标准 OpenAI 格式，更通用
- 前端更容易适配标准 OpenAI SSE

---

## 三、详细实施步骤

### Phase 1: 创建 ChemAI Agent 化学工具模块 [预计 2-3 天]

#### Step 1.1: 创建 `tools/chemistry_tools.py`

**目标文件**：`D:\化学\hermes-agent-main\tools\chemistry_tools.py`

**内容结构**：

```python
"""
Chemistry Tools for ChemAI Agent
包装 chem_skills 为 Hermes 标准 Tools
"""

import sys
import json
from typing import Dict, Any, List, Optional

# ============================================================================
# 路径配置 - 确保能导入 chem_skills
# ============================================================================

CHEMAI_BACKEND_PATH = r"D:\化学\chemai-backend"
if CHEMAI_BACKEND_PATH not in sys.path:
    sys.path.insert(0, CHEMAI_BACKEND_PATH)

from tools.registry import registry
from tools.registry import tool_error, tool_result

# 导入 Skills Handlers
try:
    from chem_skills.chemistry_parser.handler import ParserHandler
    from chem_skills.chemistry_exam.handler import ExamHandler
    from chem_skills.chemistry_diagnosis.handler import DiagnosisHandler
    SKILLS_AVAILABLE = True
except ImportError as e:
    SKILLS_AVAILABLE = False
    import logging
    logging.warning(f"ChemAI skills not available: {e}")

# ============================================================================
# Tool Schemas (OpenAI Function Calling 格式)
# ============================================================================

PARSE_PDF_QUESTIONS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "parse_pdf_questions",
        "description": "使用MinerU解析PDF文档，提取其中的化学题目。支持LaTeX化学公式识别。",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "PDF文件的绝对路径"
                },
                "lang": {
                    "type": "string",
                    "description": "语言类型，默认 'ch' (中文)",
                    "default": "ch"
                },
                "start_page": {
                    "type": "integer",
                    "description": "起始页码，从0开始",
                    "default": 0
                },
                "backend": {
                    "type": "string",
                    "description": "MinerU解析后端",
                    "default": "hybrid-auto-engine"
                }
            },
            "required": ["file_path"]
        }
    }
}

EXAM_GENERATE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "exam_generate",
        "description": "使用AI生成化学练习题目，包含四维安全审核（政治安全、科学性、难度适宜性、格式规范性）。",
        "parameters": {
            "type": "object",
            "properties": {
                "knowledge_points": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "知识点列表，例如 ['氧化还原反应', '电化学']"
                },
                "difficulty": {
                    "type": "string",
                    "description": "题目难度",
                    "enum": ["easy", "medium", "hard", "competition"],
                    "default": "medium"
                },
                "quantity": {
                    "type": "integer",
                    "description": "生成题目数量",
                    "default": 10
                },
                "exam_type": {
                    "type": "string",
                    "description": "考试类型，例如 '单元练习', '期中考试', '期末考试'",
                    "default": "单元练习"
                }
            },
            "required": ["knowledge_points"]
        }
    }
}

EXAM_AUDIT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "exam_audit",
        "description": "对单道题目进行四维安全审核，检查政治安全性、科学性、难度适宜性和格式规范性。",
        "parameters": {
            "type": "object",
            "properties": {
                "question_content": {
                    "type": "string",
                    "description": "题目内容"
                },
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "选项列表（用于选择题）"
                }
            },
            "required": ["question_content"]
        }
    }
}

EXAM_SEARCH_HISTORICAL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "exam_search_historical",
        "description": "从历年真题库中检索符合条件的题目。",
        "parameters": {
            "type": "object",
            "properties": {
                "year": {
                    "type": "integer",
                    "description": "年份筛选，例如 2023"
                },
                "difficulty": {
                    "type": "string",
                    "description": "难度筛选"
                },
                "knowledge_point": {
                    "type": "string",
                    "description": "知识点筛选"
                },
                "keyword": {
                    "type": "string",
                    "description": "关键词搜索"
                }
            }
        }
    }
}

DIAGNOSIS_BARRIER_CLASS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "diagnosis_barrier_class",
        "description": "对班级所有学生进行障碍类型诊断，识别概念理解型、审题障碍型、表述障碍型等不同类型的学习障碍。",
        "parameters": {
            "type": "object",
            "properties": {
                "class_id": {
                    "type": "string",
                    "description": "班级ID"
                },
                "exam_record_id": {
                    "type": "string",
                    "description": "考试记录ID"
                }
            },
            "required": ["class_id", "exam_record_id"]
        }
    }
}

DIAGNOSIS_PLAN_GENERATE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "diagnosis_plan_generate",
        "description": "为学生生成个性化的学习计划，包含每日任务、每周目标和针对性干预策略。",
        "parameters": {
            "type": "object",
            "properties": {
                "student_id": {
                    "type": "string",
                    "description": "学生ID"
                },
                "barrier_type": {
                    "type": "string",
                    "description": "障碍类型：concept (概念理解型), reading (审题障碍型), expression (表述障碍型)"
                },
                "weak_knowledge_points": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "薄弱知识点列表"
                }
            },
            "required": ["student_id", "barrier_type", "weak_knowledge_points"]
        }
    }
}

STANDARDIZE_CHEMICAL_FORMULA_SCHEMA = {
    "type": "function",
    "function": {
        "name": "standardize_chemical_formula",
        "description": "标准化化学公式，将下标符号（如₂、₃）转换为数字格式。",
        "parameters": {
            "type": "object",
            "properties": {
                "formula": {
                    "type": "string",
                    "description": "化学公式，例如 'Ca(OH)₂' 或 'Ca(OH)2'"
                }
            },
            "required": ["formula"]
        }
    }
}

# ============================================================================
# Tool Handlers
# ============================================================================

def _handle_parse_pdf_questions(args: Dict, task_id: str) -> str:
    """处理 PDF 解析请求"""
    if not SKILLS_AVAILABLE:
        return tool_error("ChemAI skills not available. Please ensure chemai-backend is running.")

    handler = ParserHandler()
    result = handler.parse_pdf_questions(
        file_path=args.get("file_path"),
        lang=args.get("lang", "ch"),
        start_page=args.get("start_page", 0),
        end_page=args.get("end_page"),
        backend=args.get("backend", "hybrid-auto-engine")
    )
    return tool_result(result)


def _handle_exam_generate(args: Dict, task_id: str) -> str:
    """处理 AI 出题请求"""
    if not SKILLS_AVAILABLE:
        return tool_error("ChemAI skills not available. Please ensure chemai-backend is running.")

    handler = ExamHandler()
    result = handler.exam_generate(
        knowledge_points=args.get("knowledge_points", []),
        difficulty=args.get("difficulty", "medium"),
        quantity=args.get("quantity", 10),
        exam_type=args.get("exam_type", "单元练习")
    )
    return tool_result(result)


def _handle_exam_audit(args: Dict, task_id: str) -> str:
    """处理题目审核请求"""
    if not SKILLS_AVAILABLE:
        return tool_error("ChemAI skills not available. Please ensure chemai-backend is running.")

    handler = ExamHandler()
    result = handler.exam_audit(
        question_content=args.get("question_content"),
        options=args.get("options")
    )
    return tool_result(result)


def _handle_exam_search_historical(args: Dict, task_id: str) -> str:
    """处理真题检索请求"""
    if not SKILLS_AVAILABLE:
        return tool_error("ChemAI skills not available. Please ensure chemai-backend is running.")

    handler = ExamHandler()
    result = handler.exam_search_historical(
        year=args.get("year"),
        difficulty=args.get("difficulty"),
        knowledge_point=args.get("knowledge_point"),
        keyword=args.get("keyword")
    )
    return tool_result(result)


def _handle_diagnosis_barrier_class(args: Dict, task_id: str) -> str:
    """处理班级障碍诊断请求"""
    if not SKILLS_AVAILABLE:
        return tool_error("ChemAI skills not available. Please ensure chemai-backend is running.")

    handler = DiagnosisHandler()
    result = handler.diagnosis_barrier_class(
        class_id=args.get("class_id"),
        exam_record_id=args.get("exam_record_id")
    )
    return tool_result(result)


def _handle_diagnosis_plan_generate(args: Dict, task_id: str) -> str:
    """处理学习计划生成请求"""
    if not SKILLS_AVAILABLE:
        return tool_error("ChemAI skills not available. Please ensure chemai-backend is running.")

    handler = DiagnosisHandler()
    result = handler.diagnosis_plan_generate(
        student_id=args.get("student_id"),
        barrier_type=args.get("barrier_type"),
        weak_knowledge_points=args.get("weak_knowledge_points", [])
    )
    return tool_result(result)


def _handle_standardize_chemical_formula(args: Dict, task_id: str) -> str:
    """处理化学公式标准化请求"""
    if not SKILLS_AVAILABLE:
        return tool_error("ChemAI skills not available. Please ensure chemai-backend is running.")

    handler = ParserHandler()
    result = handler.standardize_chemical_formula(formula=args.get("formula"))
    return tool_result(result)


# ============================================================================
# Registry - 注册所有化学 Tools
# ============================================================================

registry.register(
    name="parse_pdf_questions",
    toolset="chemistry",
    schema=PARSE_PDF_QUESTIONS_SCHEMA,
    handler=_handle_parse_pdf_questions,
    emoji="📄",
    description="解析PDF提取化学题目"
)

registry.register(
    name="exam_generate",
    toolset="chemistry",
    schema=EXAM_GENERATE_SCHEMA,
    handler=_handle_exam_generate,
    emoji="📝",
    description="AI生成化学练习题"
)

registry.register(
    name="exam_audit",
    toolset="chemistry",
    schema=EXAM_AUDIT_SCHEMA,
    handler=_handle_exam_audit,
    emoji="🔍",
    description="题目四维安全审核"
)

registry.register(
    name="exam_search_historical",
    toolset="chemistry",
    schema=EXAM_SEARCH_HISTORICAL_SCHEMA,
    handler=_handle_exam_search_historical,
    emoji="📚",
    description="检索历年真题"
)

registry.register(
    name="diagnosis_barrier_class",
    toolset="chemistry",
    schema=DIAGNOSIS_BARRIER_CLASS_SCHEMA,
    handler=_handle_diagnosis_barrier_class,
    emoji="🏥",
    description="班级障碍类型诊断"
)

registry.register(
    name="diagnosis_plan_generate",
    toolset="chemistry",
    schema=DIAGNOSIS_PLAN_GENERATE_SCHEMA,
    handler=_handle_diagnosis_plan_generate,
    emoji="📋",
    description="生成个性化学习计划"
)

registry.register(
    name="standardize_chemical_formula",
    toolset="chemistry",
    schema=STANDARDIZE_CHEMICAL_FORMULA_SCHEMA,
    handler=_handle_standardize_chemical_formula,
    emoji="⚗️",
    description="标准化化学公式"
)
```

#### Step 1.2: 验证 chemistry_tools.py 能正确导入

执行以下验证：
```bash
cd D:\化学\hermes-agent-main
python -c "
import sys
sys.path.insert(0, r'D:\化学\chemai-backend')
from tools.chemistry_tools import SKILLS_AVAILABLE
print(f'Skills available: {SKILLS_AVAILABLE}')
"
```

### Phase 2: 更新 Toolsets 配置 [预计 0.5 天]

#### Step 2.1: 更新 `toolsets.py`

在 `TOOLSETS` 字典中添加：

```python
# 在 "homeassistant" toolset 之后添加

"chemistry": {
    "description": "化学领域工具 - PDF解析( MinerU)、AI出题、障碍诊断、学习计划生成、化学公式标准化",
    "tools": [
        "parse_pdf_questions",
        "exam_generate",
        "exam_audit",
        "exam_search_historical",
        "diagnosis_barrier_class",
        "diagnosis_plan_generate",
        "standardize_chemical_formula"
    ],
    "includes": []
},
```

在 `"hermes-api-server"` toolset 的 `includes` 中添加 `"chemistry"`：

```python
"hermes-api-server": {
    "description": "OpenAI-compatible API server — full agent tools accessible via HTTP",
    "tools": [
        # ... 原有 tools ...
    ],
    "includes": ["chemistry"]  # 新增
},
```

#### Step 2.2: 更新 `model_tools.py`

在 `_discover_tools()` 函数的 `_modules` 列表中，添加：

```python
_modules = [
    # ... 原有模块 ...
    "tools.chemistry_tools",  # 新增 - 化学领域 Tools
]
```

### Phase 3: 重构前端 hermes.js - 适配 OpenAI SSE 格式 [预计 2-3 天]

#### Step 3.1: 理解 ChemAI Agent 的 SSE 事件流

ChemAI Agent `/v1/chat/completions` 的 SSE 事件流：

```
1. 角色声明
   {"id": "xxx", "object": "chat.completion.chunk",
    "choices": [{"index": 0, "delta": {"role": "assistant"}}]}

2. 内容片段 (多次)
   {"id": "xxx", "object": "chat.completion.chunk",
    "choices": [{"index": 0, "delta": {"content": "xxx"}}]}

3. Tool Call (以内容片段形式，或通过 tool_calls)
   {"id": "xxx", "object": "chat.completion.chunk",
    "choices": [{"index": 0, "delta": {"tool_calls": [...]}}]}

4. Tool Result (通过 tool_progress 事件)
   "event: hermes.tool.progress\ndata: {...}\n\n"

5. 结束
   {"id": "xxx", "object": "chat.completion.chunk",
    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
   "data: [DONE]\n\n"
```

#### Step 3.2: 重构 `_processSSEvent()` 方法

**原实现** (`hermes.js` 第 257-313 行)：
```javascript
async _processSSEvent(data, onEvent) {
    // 期望 data.type === 'chunk'
    if (data.type === 'chunk' || data.type === 'content_chunk') {
        const content = data.delta?.content || data.content || '';
        // ...
    }
    // 期望 data.type === 'tool_call'
    if (data.type === 'tool_call' || data.tool_calls) {
        // ...
    }
    // ...
}
```

**问题**：ChemAI Agent 发送的是 OpenAI 格式，不是这种结构化格式。

#### Step 3.3: 新实现 - 适配 OpenAI SSE

```javascript
/**
 * 处理 OpenAI SSE 格式事件
 * ChemAI Agent api_server.py 发送的标准 OpenAI 格式
 */
async _processSSEvent(data, onEvent) {
    // 跳过空数据
    if (!data) return;

    // 处理 chat.completion.chunk 格式 (OpenAI 标准格式)
    if (data.object === 'chat.completion.chunk') {
        const delta = data.choices?.[0]?.delta;
        const finishReason = data.choices?.[0]?.finish_reason;

        // 1. 处理角色声明
        if (delta?.role) {
            onEvent({
                type: 'role',
                role: delta.role
            });
        }

        // 2. 处理内容片段
        if (delta?.content) {
            const event = {
                type: HermesEventType.THINKING,
                content: delta.content
            };
            onEvent(event);
            this.callbacks.onThinking?.(event);
        }

        // 3. 处理 Tool Calls (OpenAI function calling)
        if (delta?.tool_calls) {
            for (const toolCall of delta.tool_calls) {
                const event = {
                    type: HermesEventType.TOOL_CALL,
                    tool: toolCall.function?.name,
                    params: JSON.parse(toolCall.function?.arguments || '{}'),
                    toolCallId: toolCall.id
                };
                onEvent(event);
                this.callbacks.onToolCall?.(event);
            }
        }

        // 4. 处理结束
        if (finishReason === 'stop') {
            const event = {
                type: HermesEventType.FINAL,
                finishReason: 'stop'
            };
            onEvent(event);
            this.callbacks.onFinal?.(event);
        }

        // 5. 处理 Tool Call 结束 (finish_reason === 'tool_calls')
        if (finishReason === 'tool_calls') {
            // Agent 已发送所有 tool_calls，等待 tool results
        }
    }
}

/**
 * 处理 hermes.tool.progress 格式事件
 * 这是 ChemAI Agent 自定义的事件格式
 */
async _processToolProgress(data) {
    // hermes.tool.progress 事件格式:
    // {"tool": "xxx", "emoji": "📄", "label": "xxx"}

    if (data.type === 'hermes.tool.progress' || data.event === 'tool.started') {
        const event = {
            type: HermesEventType.TOOL_CALL,
            tool: data.tool,
            preview: data.label,
            status: 'started'
        };
        this.callbacks.onToolCall?.(event);
    }

    if (data.event === 'tool.completed') {
        const event = {
            type: HermesEventType.TOOL_RESULT,
            tool: data.tool,
            duration: data.duration,
            status: 'completed'
        };
        this.callbacks.onToolResult?.(event);
    }
}

/**
 * 处理 SSE 行数据
 * 支持两种格式: OpenAI JSON 和 hermes.tool.progress
 */
async _processSSELine(line, onEvent) {
    // 处理 hermes.tool.progress 格式 (SSE event line)
    if (line.startsWith('event:')) {
        const eventName = line.slice(6).trim();
        if (eventName === 'hermes.tool.progress') {
            return 'tool_progress';
        }
    }

    // 处理 hermes.tool.progress 数据行
    if (line.startsWith('data:')) {
        const dataStr = line.slice(5).trim();
        if (dataStr === '[DONE]') {
            this.callbacks.onFinal?.({ type: 'done' });
            return;
        }

        try {
            const data = JSON.parse(dataStr);

            // 检查是否是 tool_progress 事件
            if (data.event === 'hermes.tool.progress' || data.tool) {
                await this._processToolProgress(data);
            }

            // 检查是否是 OpenAI chunk 格式
            if (data.object === 'chat.completion.chunk') {
                await this._processSSEvent(data, onEvent);
            }

            // 检查是否是 run.completed 或 run.failed
            if (data.event === 'run.completed') {
                this.callbacks.onFinal?.({
                    type: HermesEventType.FINAL,
                    result: data.output
                });
            }

            if (data.event === 'run.failed') {
                this.callbacks.onError?.({
                    type: HermesEventType.ERROR,
                    error: data.error
                });
            }
        } catch (e) {
            console.warn('SSE解析失败:', e);
        }
    }
}
```

#### Step 3.4: 更新 `processStream()` 方法

```javascript
/**
 * 处理 SSE 流式响应
 */
async processStream(reader, onEvent) {
    const decoder = new TextDecoder();
    let buffer = '';
    let expectingDataForEvent = null;

    try {
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop(); // 保留未完成的行

            for (const line of lines) {
                // 处理 SSE 事件行 (event: xxx)
                if (line.startsWith('event:')) {
                    expectingDataForEvent = line.slice(6).trim();
                    continue;
                }

                // 处理 SSE 数据行 (data: xxx)
                if (line.startsWith('data:')) {
                    const dataStr = line.slice(5).trim();

                    if (dataStr === '[DONE]') {
                        this.callbacks.onFinal?.({ type: 'done' });
                        return;
                    }

                    try {
                        const data = JSON.parse(dataStr);

                        // 根据前一个 event: 行决定如何处理
                        if (expectingDataForEvent === 'hermes.tool.progress') {
                            await this._processToolProgress(data);
                        } else if (data.object === 'chat.completion.chunk') {
                            await this._processSSEvent(data, onEvent);
                        } else if (data.event === 'run.completed') {
                            this.callbacks.onFinal?.({ type: HermesEventType.FINAL, result: data.output });
                        } else if (data.event === 'run.failed') {
                            this.callbacks.onError?.({ type: HermesEventType.ERROR, error: data.error });
                        }

                    } catch (e) {
                        console.warn('SSE解析失败:', e);
                    }

                    expectingDataForEvent = null;
                }
            }
        }
    } catch (error) {
        this.callbacks.onError?.({ error: error.message });
    }
}
```

#### Step 3.5: 更新 `_buildPrompt()` 方法

确保 prompt 能引导 LLM 调用正确的 Tool：

```javascript
_buildPrompt(task, params) {
    // 为每个 Task 提供明确的 Tool 调用指令
    const toolInstructions = {
        [TaskType.OCR_RECOGNIZE]: `
请使用 OCR 技术识别这张答题卡图片。
调用 parse_pdf_questions 或调用相应的 OCR Tool 来完成识别。
返回每个学生的答题结果和置信度。`,

        [TaskType.PDF_PARSE]: `
请分析这个文档。
调用 parse_pdf_questions 工具提取化学题目。
返回提取到的题目列表。`,

        [TaskType.GENERATE_QUESTIONS]: `
请生成化学练习题。
调用 exam_generate 工具生成题目。
参数要求：
- knowledge_points: 知识点列表
- difficulty: 难度 (easy/medium/hard/competition)
- quantity: 题目数量
- exam_type: 考试类型`,

        [TaskType.ANALYZE_BARRIER]: `
请分析这次考试的学情数据。
调用 diagnosis_barrier_class 进行班级障碍诊断。
识别学生的障碍类型分布（概念理解型/审题障碍型/表述障碍型）。`,

        [TaskType.GENERATE_LEARNING_PLAN]: `
请为学生生成个性化学习计划。
调用 diagnosis_plan_generate 生成学习计划。
参数要求：
- student_id: 学生ID
- barrier_type: 障碍类型
- weak_knowledge_points: 薄弱知识点列表`,

        [TaskType.GENERATE_REPORT]: `
请生成学情报告。
首先调用 diagnosis_barrier_class 获取班级诊断结果，
然后生成包含班级整体分析和每个学生学习情况的报告。`
    };

    return toolInstructions[task] || task;
}
```

### Phase 4: 测试验证 [预计 1-2 天]

#### Step 4.1: 启动服务

```bash
# 终端1: 启动 FastAPI Backend
cd D:\化学\chemai-backend
python -m app.main
# 预期输出: Uvicorn running on http://0.0.0.0:8001

# 终端2: 启动 ChemAI Agent API Server
cd D:\化学\hermes-agent-main
python -m gateway.run --platform api_server
# 预期输出: API server listening on http://127.0.0.1:8642
```

#### Step 4.2: 验证 Tools 注册

```bash
# 检查 /v1/models 返回包含 chemistry tools
curl http://localhost:8642/v1/models

# 检查 Tool 调用是否工作
curl -X POST http://localhost:8642/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "hermes-agent",
    "messages": [{"role": "user", "content": "请用MinerU解析PDF文件 D:\\test.pdf"}],
    "tools": [{"type": "function", "function": {"name": "parse_pdf_questions"}}]
  }'
```

#### Step 4.3: 验证 SSE 事件格式

使用 `curl` 或 Postman 测试，注意观察：
1. 是否收到 `chat.completion.chunk` 格式的事件
2. 是否收到 `hermes.tool.progress` 事件
3. Tool calls 是否正确解析

#### Step 4.4: 端到端测试

1. 启动前端开发服务器
2. 测试完整工作流：
   - 教师上传 PDF → ChemAI Agent 解析 → 题目入库
   - AI 出题 → 题目生成 → 教师审核
   - 学情诊断 → 障碍分析 → 学习计划

---

## 四、问题-解决方案对照表

| 问题编号 | 问题描述 | 解决方案 | 涉及文件 |
|----------|----------|----------|----------|
| P1 | chem_skills 未注册到 Agent | 创建 chemistry_tools.py，调用 registry.register() | 新建: tools/chemistry_tools.py |
| P2 | SSE 事件格式完全不兼容 | 重构 hermes.js 的 _processSSEvent() 和 processStream() | 修改: hermes.js |
| P3 | 缺少 chemistry toolset 定义 | 在 toolsets.py 中添加 "chemistry" toolset | 修改: toolsets.py |
| P4 | chemistry_tools.py 未创建 | 实现完整的 chemistry_tools.py | 新建: tools/chemistry_tools.py |
| P5 | 前端 TaskType prompt 可靠性 | 更新 _buildPrompt() 提供明确的 Tool 调用指令 | 修改: hermes.js |

---

## 五、风险评估与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| LLM 不按预期调用 Tool | 高 | 在 prompt 中提供明确的 Tool 调用示例 |
| chem_skills 导入失败 | 中 | 添加 SKILLS_AVAILABLE 检查，返回友好错误 |
| OpenAI SSE 格式理解偏差 | 中 | 多次测试验证实际收到的格式 |
| 升级 ChemAI Agent 导致兼容性问题 | 低 | chemistry_tools.py 隔离，不修改 Agent 核心 |

---

## 六、验收标准

### 6.1 集成成功标准

- [ ] `curl http://localhost:8642/v1/models` 返回包含 hermes-agent
- [ ] Tool 注册成功，无 Python 导入错误
- [ ] 发送 test prompt 后，LLM 能正确调用 chemistry Tools

### 6.2 SSE 事件格式验收

- [ ] `processStream()` 能正确解析 OpenAI 格式的 chunk 事件
- [ ] `processStream()` 能正确解析 hermes.tool.progress 事件
- [ ] Tool call 和 Tool result 事件正确触发回调

### 6.3 端到端工作流验收

- [ ] 教师上传 PDF → ChemAI Agent 解析 → 题目入库
- [ ] AI 出题 → 题目生成 → 成功返回
- [ ] 学情诊断 → 障碍分析 → 学习计划生成

### 6.4 代码质量标准

- [ ] chemistry_tools.py 有完整的 docstring
- [ ] hermes.js 的事件处理有详细的注释
- [ ] 错误处理完善，无未捕获的异常

---

## 七、人员分工

| 角色 | 职责 | 阶段 |
|------|------|------|
| 后端开发 | 创建 chemistry_tools.py | Phase 1 |
| 后端开发 | 更新 toolsets.py 和 model_tools.py | Phase 2 |
| 前端开发 | 重构 hermes.js 适配 OpenAI SSE | Phase 3 |
| 测试 | 验证 Tools 注册和 SSE 事件格式 | Phase 4 |
| 测试 | 端到端工作流测试 | Phase 4 |

---

## 八、时间线

```
Week 1:
├── Day 1-2: Phase 1 - 创建 chemistry_tools.py
├── Day 3:   Phase 2 - 更新 toolsets 配置
├── Day 4-5: Phase 3 - 重构 hermes.js (SSE 适配)
└── Day 6-7: Phase 4 - 测试验证

Week 2:
├── Day 1-2: 修复发现的问题
├── Day 3-4: 端到端测试
├── Day 5:   编写集成文档
└── Day 6-7: 验收测试
```

---

## 九、附录

### A. 关键文件清单

| 文件 | 操作 | 路径 |
|------|------|------|
| chemistry_tools.py | 新建 | `D:\化学\hermes-agent-main\tools\chemistry_tools.py` |
| toolsets.py | 修改 | `D:\化学\hermes-agent-main\toolsets.py` |
| model_tools.py | 修改 | `D:\化学\hermes-agent-main\model_tools.py` |
| hermes.js | 修改 | `D:\化学\chemai-backend\frontend\src\services\hermes.js` |

### B. ChemAI Agent SSE 事件格式参考

**OpenAI 格式 (chat.completion.chunk)**：
```json
{"id": "chatcmpl-xxx", "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {"content": "xxx"}, "finish_reason": null}]}
```

**Tool Call 格式**：
```json
{"id": "chatcmpl-xxx", "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {"tool_calls": [{"id": "call_xxx", "type": "function", "function": {"name": "parse_pdf_questions", "arguments": "{}"}}]}, "finish_reason": null}]}
```

**Hermes 自定义格式 (hermes.tool.progress)**：
```
event: hermes.tool.progress
data: {"tool": "parse_pdf_questions", "emoji": "📄", "label": "正在解析PDF..."}
```

### C. registry.tool_result() 和 tool_error() 参考

```python
# tools/registry.py
def tool_result(content: Any) -> str:
    """格式化 Tool 执行结果"""
    if isinstance(content, dict):
        return json.dumps(content, ensure_ascii=False)
    return str(content)

def tool_error(message: str) -> str:
    """格式化 Tool 执行错误"""
    return json.dumps({"error": message})
```

---

## 版本历史

| 版本 | 日期 | 修改内容 |
|------|------|----------|
| 1.0 | 2026-04-16 | 初始版本 |
| 2.0 | 2026-04-16 | 基于技术验证结果，添加 SSE 事件格式适配 (Phase 3) |

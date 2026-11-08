# ChemAI ChemAI Agent 集成修复计划

> 创建日期：2026-04-16
> 项目：智辅化学 ChemAI
> 目标：修复 ChemAI Agent 与 chem_skills 之间的架构断裂，建立完整工作流

---

## 一、问题分析

### 1.1 当前架构状态

```
┌──────────────────────────────────────────────────────────────────────┐
│                           Frontend (SPA)                              │
│                     teacher_v2.html / student_v2.html                 │
│                         hermes.js (端口8642)                         │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │ HTTP/SSE
              ┌──────────────────┴──────────────────┐
              │ 8642                                │ 8001
              ▼                                    ▼
┌─────────────────────────┐       ┌───────────────────────────────────┐
│   ChemAI Agent Main     │       │       FastAPI Backend              │
│   (hermes-agent-main)   │       │       (chemai-backend)              │
│                         │       │                                   │
│  - OpenAI兼容API        │       │  - REST API (OCR/出题/诊断等)       │
│  - 内置Toolsets         │       │  - chem_skills/ (独立存在)       │
│  - SSE流式事件         │       │    - chemistry_parser              │
│                         │       │    - chemistry_exam                │
│  ⚠️ 未加载化学Skills   │       │    - chemistry_diagnosis           │
│  ⚠️ 无化学Tool定义     │       │    - chemistry_improvement         │
└─────────────────────────┘       │    - chemistry_memory              │
                                  │    - chemistry_notification        │
                                  └───────────────────────────────────┘
                                            ▲
                                            │ Skills通过HTTP调用
                                            │ (base_url:8000)
                                            │
                                  ┌─────────┴─────────────────────────┐
                                  │        chem_skills/              │
                                  │   ⚠️ 未注册到 ChemAI Agent        │
                                  └───────────────────────────────────┘
```

### 1.2 核心问题

| 问题 | 严重程度 | 说明 |
|------|----------|------|
| Skills未注册到Agent | 🔴 严重 | ChemAI Agent无法调用化学Skills |
| Agent无化学Tool定义 | 🔴 严重 | 架构设计存在根本性断裂 |
| 前后端工作流断连 | 🔴 严重 | 前端任务无法正确路由到Skills |
| 学生端模块未对接 | 🟡 中等 | 部分功能（练习答题、学情报告）待对接 |
| 双端口复杂度 | 🟡 中等 | 需要同时维护8642和8001两个服务 |

### 1.3 问题根因

**ChemAI Agent 的 Tool 注册机制**：

1. `tools/registry.py` - 中心注册表，所有Tool在此注册
2. `model_tools.py` - `_discover_tools()` 导入所有 tool 模块
3. `toolsets.py` - 定义 `_HERMES_CORE_TOOLS` 和各平台toolset

**当前状态**：
- `chem_skills/` 目录独立于 `hermes-agent-main/tools/` 之外
- Skills 继承 `BaseSkillHandler`，但**未调用 `registry.register()`**
- Skills 无法被 ChemAI Agent 的 ReAct 循环发现和调用

---

## 二、修复方案

### 2.1 方案概述

**核心思路**：将 `chem_skills` 包装为 ChemAI Agent 的标准 Tools，通过 `tools/chemistry_tools.py` 注册到 Agent。

```
chem_skills/                           hermes-agent-main/
                                              │
chemistry_parser/                       tools/
    ├── handler.py (原有)              chemistry_tools.py (新建)
chemistry_exam/         ──────▶          │
    ├── handler.py (原有)                  │ registry.register()
chemistry_diagnosis/                       │ (注册所有化学Tool)
    └── handler.py (原有)                  ▼
                                      toolsets.py
                                            │ 添加 "chemistry" toolset
                                            ▼
                                      model_tools.py
                                            │ _discover_tools()
                                            ▼
                                      ChemAI Agent (8642)
                                            │
                                            ▼
                                      前端 hermes.js
```

### 2.2 详细方案

#### 阶段一：创建 ChemAI Agent 化学工具模块

**文件**：`D:\化学\hermes-agent-main\tools\chemistry_tools.py`

```python
# 主要内容
from tools.registry import registry
from typing import Dict, Any, List

# 注册以下Tools:
# - parse_pdf_questions     (chemistry_parser)
# - parse_image_chemical    (chemistry_parser)
# - exam_generate           (chemistry_exam)
# - exam_audit              (chemistry_exam)
# - exam_search_historical  (chemistry_exam)
# - exam_import_ocr         (chemistry_exam)
# - diagnosis_barrier_class (chemistry_diagnosis)
# - diagnosis_plan_generate  (chemistry_diagnosis)
# - generate_learning_plan   (chemistry_diagnosis)
# - standardize_chemical_formula (chemistry_parser)
```

#### 阶段二：注册 Tools 和 Toolsets

1. **更新 `toolsets.py`**：
   - 添加 `chemistry` toolset
   - 添加到 `hermes-api-server` toolset

2. **更新 `model_tools.py`**：
   - 在 `_discover_tools()` 中添加 `"tools.chemistry_tools"`

#### 阶段三：验证集成

1. 启动 ChemAI Agent API Server
2. 验证化学Tools可用
3. 测试端到端工作流

#### 阶段四：修复前端通信（可选）

根据集成结果，可能需要调整 `hermes.js` 中的任务格式。

---

## 三、实施步骤

### Phase 1: 创建化学工具模块 [预计 2-3 天]

#### Step 1.1: 创建 tools/chemistry_tools.py

**目标文件**：`D:\化学\hermes-agent-main\tools\chemistry_tools.py`

**主要内容**：

```python
"""
Chemistry Tools for ChemAI Agent
包装 chem_skills 中的化学领域Skills为Hermes标准Tools
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

# 添加 chemai-backend 路径到 sys.path
CHEMAI_BACKEND_PATH = r"D:\化学\chemai-backend"
if CHEMAI_BACKEND_PATH not in sys.path:
    sys.path.insert(0, CHEMAI_BACKEND_PATH)

from tools.registry import registry

# 导入 Skills
try:
    from chem_skills.chemistry_parser.handler import ParserHandler
    from chem_skills.chemistry_exam.handler import ExamHandler
    from chem_skills.chemistry_diagnosis.handler import DiagnosisHandler
    SKILLS_AVAILABLE = True
except ImportError as e:
    SKILLS_AVAILABLE = False
    print(f"Warning: Could not import chemai skills: {e}")

# ============================================================================
# Tool Schemas
# ============================================================================

PARSE_PDF_QUESTIONS_SCHEMA = {
    "name": "parse_pdf_questions",
    "description": "使用MinerU解析PDF文档，提取其中的化学题目。支持LaTeX化学公式识别。",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "PDF文件路径"},
            "lang": {"type": "string", "description": "语言，默认ch", "default": "ch"},
            "start_page": {"type": "integer", "description": "起始页，默认0", "default": 0},
            "end_page": {"type": "integer", "description": "结束页，默认None"},
            "backend": {"type": "string", "description": "MinerU后端", "default": "hybrid-auto-engine"}
        },
        "required": ["file_path"]
    }
}

EXAM_GENERATE_SCHEMA = {
    "name": "exam_generate",
    "description": "使用AI生成化学练习题目，包含四维安全审核。",
    "parameters": {
        "type": "object",
        "properties": {
            "knowledge_points": {
                "type": "array",
                "items": {"type": "string"},
                "description": "知识点列表"
            },
            "difficulty": {
                "type": "string",
                "description": "难度: easy/medium/hard/competition",
                "default": "medium"
            },
            "quantity": {"type": "integer", "description": "生成数量", "default": 10},
            "exam_type": {"type": "string", "description": "考试类型", "default": "单元练习"}
        },
        "required": ["knowledge_points"]
    }
}

# ... 更多 schemas ...

# ============================================================================
# Tool Handlers
# ============================================================================

def _handle_parse_pdf_questions(args: Dict, task_id: str) -> str:
    """处理PDF解析请求"""
    if not SKILLS_AVAILABLE:
        return {"success": False, "error": "ChemAI skills not available"}
    handler = ParserHandler()
    result = handler.parse_pdf_questions(
        file_path=args.get("file_path"),
        lang=args.get("lang", "ch"),
        start_page=args.get("start_page", 0),
        end_page=args.get("end_page"),
        backend=args.get("backend", "hybrid-auto-engine")
    )
    return json.dumps(result, ensure_ascii=False)

# ... 更多 handlers ...

# ============================================================================
# Registry
# ============================================================================

registry.register(
    name="parse_pdf_questions",
    toolset="chemistry",
    schema=PARSE_PDF_QUESTIONS_SCHEMA,
    handler=_handle_parse_pdf_questions,
    emoji="📄",
    description="解析PDF提取化学题目"
)

# ... 更多 register 调用 ...
```

#### Step 1.2: 验证Skills导入路径

确保以下导入路径有效：
```python
from chem_skills.chemistry_parser.handler import ParserHandler
from chem_skills.chemistry_exam.handler import ExamHandler
from chem_skills.chemistry_diagnosis.handler import DiagnosisHandler
```

### Phase 2: 更新 Toolsets 配置 [预计 0.5 天]

#### Step 2.1: 更新 toolsets.py

在 `_HERMES_CORE_TOOLS` 中**无需**添加（化学Tools不应默认启用）。

在 `TOOLSETS` 字典中添加：

```python
"chemistry": {
    "description": "化学领域工具 - PDF解析、AI出题、障碍诊断、学习计划生成",
    "tools": [
        "parse_pdf_questions",
        "parse_image_chemical",
        "exam_generate",
        "exam_audit",
        "exam_search_historical",
        "exam_import_ocr",
        "diagnosis_barrier_class",
        "diagnosis_plan_generate",
        "standardize_chemical_formula"
    ],
    "includes": []
},

"hermes-api-server": {
    # ... 原有内容 ...
    # 添加 chemistry 到 includes
    "includes": ["chemistry"]
},
```

#### Step 2.2: 更新 model_tools.py

在 `_discover_tools()` 函数中添加：

```python
_modules = [
    # ... 原有模块 ...
    "tools.chemistry_tools",  # 新增
]
```

### Phase 3: 测试验证 [预计 1-2 天]

#### Step 3.1: 启动服务

```bash
# 终端1: 启动 FastAPI Backend
cd D:\化学\chemai-backend
python -m app.main

# 终端2: 启动 ChemAI Agent API Server
cd D:\化学\hermes-agent-main
python -m gateway.run --platform api_server
```

#### Step 3.2: 验证Tools注册

```bash
curl http://localhost:8642/v1/models
```

应返回包含 `hermes-agent` 的模型列表。

#### Step 3.3: 测试化学Tool调用

```bash
curl -X POST http://localhost:8642/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "hermes-agent",
    "messages": [{"role": "user", "content": "请用MinerU解析这个PDF文件：D:\\test\\questions.pdf"}],
    "tools": [{"type": "function", "function": {"name": "parse_pdf_questions"}}]
  }'
```

### Phase 4: 前端集成验证 [预计 1-2 天]

#### Step 4.1: 检查 hermes.js 适配

前端 `hermes.js` 需要适配 ChemAI Agent 的实际响应格式：

```javascript
// 当前设计
hermesService.executeStream(TaskType.OCR_RECOGNIZE, {...})

// 期望的 ChemAI Agent 行为
// Agent 应能识别 Tool call: parse_pdf_questions
// 并通过 SSE 返回 tool_call, tool_result, final 等事件
```

#### Step 4.2: 测试完整工作流

| 测试场景 | 预期结果 |
|----------|----------|
| 教师上传PDF | ChemAI Agent 调用 parse_pdf_questions |
| AI出题请求 | ChemAI Agent 调用 exam_generate |
| 学情诊断请求 | ChemAI Agent 调用 diagnosis_barrier_class |
| 学习计划生成 | ChemAI Agent 调用 diagnosis_plan_generate |

---

## 四、备选方案

### 方案B: MCP协议集成

如果不想修改 hermes-agent-main 核心代码，可以使用 MCP (Model Context Protocol) 集成：

```
ChemAI Agent (MCP Client)
        │
        │ MCP Protocol
        ▼
chemai-backend/mcp_server.py (新建)
        │
        │ 内部调用
        ▼
chem_skills/
```

**优点**：
- 不修改 hermes-agent-main 核心代码
- 保持 chem_skills 独立性

**缺点**：
- 需要额外部署 MCP Server
- 架构复杂度增加

### 方案C: 直接API调用

前端不通过 ChemAI Agent，直接调用 FastAPI 后端：

```
Frontend → FastAPI (8001) → chem_skills
          (无需 ChemAI Agent)
```

**优点**：
- 架构简单
- 绕过 Agent 中间层

**缺点**：
- 失去 Agent 的 ReAct 推理能力
- 无法享受 ChemAI Agent 的流式输出和工具编排

---

## 五、风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| hermes-agent版本更新导致兼容性问题 | 中 | 隔离chemistry_tools.py，减少耦合 |
| MinerU路径配置问题 | 中 | 提供详细的安装和配置文档 |
| Skills与Hermes Tool参数格式不一致 | 中 | 编写详细的参数映射文档 |
| 前端hermes.js需要大幅修改 | 低 | 保留向后兼容性 |

---

## 六、验收标准

### 6.1 集成成功标准

- [ ] ChemAI Agent 能成功调用至少 3 个化学Tools
- [ ] 端到端测试：上传PDF → 解析 → 出题 → 完成
- [ ] SSE流式事件正确返回到前端
- [ ] 无Python导入错误或路径问题

### 6.2 性能标准

- [ ] Tool调用响应时间 < 5秒（不含LLM推理时间）
- [ ] ChemAI Agent API Server 内存占用 < 500MB

### 6.3 代码质量标准

- [ ] chemistry_tools.py 有完整的 docstring
- [ ] 所有 Tools 有对应的 schema 定义
- [ ] 有单元测试覆盖核心逻辑

---

## 七、人员分工

| 角色 | 职责 |
|------|------|
| 后端开发 | Step 1.1-1.2: 创建 chemistry_tools.py |
| DevOps | Step 2.1-2.2: 更新 toolsets 配置 |
| 测试 | Step 3.1-3.3: 验证集成 |
| 前端 | Step 4.1-4.2: 前端适配和测试 |

---

## 八、时间线

```
Week 1:
├── Day 1-2: Phase 1 - 创建 chemistry_tools.py
├── Day 3:   Phase 2 - 更新 toolsets 配置
├── Day 4-5: Phase 3 - 测试验证
└── Day 6-7: Phase 4 - 前端集成验证 (如需要)

Week 2:
├── 修复发现的问题
├── 编写集成文档
└── 验收测试
```

---

## 九、附录

### A. 相关文件路径

| 文件 | 路径 |
|------|------|
| ChemAI Agent 主目录 | `D:\化学\hermes-agent-main` |
| ChemAI Backend | `D:\化学\chemai-backend` |
| Chem Skills | `D:\化学\chemai-backend\chem_skills` |
| chemistry_tools.py (待创建) | `D:\化学\hermes-agent-main\tools\chemistry_tools.py` |
| 前端 Hermes Service | `D:\化学\chemai-backend\frontend\src\services\hermes.js` |

### B. ChemAI Agent API 参考

- API Server 启动：`python -m gateway.run --platform api_server`
- 健康检查：`GET http://localhost:8642/health`
- Chat Completions：`POST http://localhost:8642/v1/chat/completions`
- SSE事件：`GET http://localhost:8642/v1/runs/{run_id}/events`

### C. Tool注册参考

参考 `tools\file_tools.py` 中的 `registry.register()` 调用格式。

---

## 版本历史

| 版本 | 日期 | 修改内容 |
|------|------|----------|
| 1.0 | 2026-04-16 | 初始版本 |

# ChemAI Agent 化 Phase 1 详细设计

> 本文档定义 ChemAI 与 ChemAI Agent 集成的 Phase 1 工作：API 分析与 Skill 架构设计

---

## 1. ChemAI 现有 API 接口能力分析

### 1.1 API 路由总览

| 路由文件 | API 数量 | 核心功能 |
|---------|---------|---------|
| `app/api/question.py` | 12 | AI出题、题目审核、历年真题查询、手动导入 |
| `app/api/diagnosis.py` | 7 | 障碍类型诊断、学习计划生成、配置管理 |
| `app/api/report.py` | 6 | 错题报告生成、发送、导出 |
| `app/api/practice.py` | 5 | 自适应练习布置、任务获取、提交、效果评估 |
| `app/api/ocr.py` | 3 | 答题卡识别、批量识别、错题统计 |
| `app/api/panel.py` | 5 | 学情面板、知识点详情、学生详情、趋势、导出 |
| `app/api/class_api.py` | 5 | 班级管理、学生CRUD |
| `app/api/exam.py` | 4 | 考试管理 |
| `app/api/user.py` | 8 | 用户管理（学生/教师CRUD、审批） |
| `app/api/auth.py` | 3 | 认证（登录/注册/登出） |

**总计：58 个 API 接口**

---

### 1.2 可封装为 Hermes Tool 的能力矩阵

| 能力分类 | 具体功能 | Tool 名称 | 输入参数 | 输出 | Agent 可调用性 |
|---------|---------|----------|---------|------|---------------|
| **F2: AI出题** | AI生成题目 | `generate_questions` | knowledge_points[], difficulty, quantity | Question[] | ⭐⭐⭐⭐⭐ |
| | 题目安全审核 | `audit_question` | question_content | AuditReport | ⭐⭐⭐⭐⭐ |
| | 化学方程式配平检测 | `check_equation_balance` | equation_string | BalanceResult | ⭐⭐⭐⭐⭐ |
| | 历年真题检索 | `search_historical_questions` | knowledge_point, year, difficulty | HistoricalQuestion[] | ⭐⭐⭐⭐ |
| **F4: 障碍诊断** | 班级障碍诊断 | `diagnose_class_barriers` | class_id, exam_record_id | BarrierDiagnosis | ⭐⭐⭐⭐⭐ |
| | 生成学习计划 | `generate_learning_plan` | student_id, barrier_type, weak_kps[] | LearningPlan | ⭐⭐⭐⭐⭐ |
| | 获取学生障碍详情 | `get_student_barrier` | student_id | StudentDiagnosis | ⭐⭐⭐⭐ |
| **F3: 错题报告** | 生成老师版报告 | `generate_teacher_report` | exam_record_id | Report | ⭐⭐⭐⭐ |
| | 生成学生版报告 | `generate_student_report` | exam_record_id, student_id | StudentReport | ⭐⭐⭐⭐ |
| | 发送报告给学生 | `send_report_to_student` | exam_record_id | SendResult | ⭐⭐⭐ |
| **F5: 自适应练习** | 布置练习 | `assign_practice` | class_id, knowledge_points[], count | Practice | ⭐⭐⭐⭐ |
| | 获取学生练习任务 | `get_student_tasks` | student_id | Task[] | ⭐⭐⭐ |
| | 评估练习效果 | `evaluate_practice_effect` | student_id, practice_id | EffectReport | ⭐⭐⭐ |
| **F1: OCR识别** | 答题卡识别 | `recognize_answer_sheet` | image_data | OCRResult | ⭐⭐⭐ |
| | 批量识别 | `recognize_batch` | image_data[] | OCRResult[] | ⭐⭐⭐ |
| **F7: 学情分析** | 班级学情面板 | `get_class_panel` | class_id | ClassPanel | ⭐⭐⭐ |
| | 知识点详情 | `get_knowledge_point_detail` | class_id, kp_name | KPDetail | ⭐⭐⭐ |
| | 学情趋势 | `get_learning_trend` | class_id | TrendData | ⭐⭐⭐ |
| **知识图谱** | 查询知识点 | `query_knowledge_point` | kp_name | KPInfo | ⭐⭐⭐⭐ |
| | 获取知识点关联 | `get_kp_relations` | kp_name | RelatedKP[] | ⭐⭐⭐ |
| **题库** | 搜索题目 | `search_exam_bank` | keyword, kp, difficulty | Question[] | ⭐⭐⭐ |
| | 查找相似题 | `find_similar_questions` | knowledge_points[], difficulty | Question[] | ⭐⭐⭐⭐ |

---

### 1.3 Tool 优先级分类

#### P0 - 核心 Tool（必须实现）

```
1. generate_questions - AI出题
2. audit_question - 题目安全审核
3. check_equation_balance - 化学方程式配平检测
4. diagnose_class_barriers - 班级障碍诊断
5. generate_learning_plan - 生成学习计划
```

#### P1 - 重要 Tool（应该实现）

```
6. generate_teacher_report - 生成老师版报告
7. generate_student_report - 生成学生版报告
8. assign_practice - 布置自适应练习
9. search_historical_questions - 历年真题检索
10. get_class_panel - 班级学情面板
```

#### P2 - 扩展 Tool（可以实现）

```
11. send_report_to_student - 发送报告
12. get_student_tasks - 获取练习任务
13. recognize_answer_sheet - OCR识别
14. query_knowledge_point - 知识点查询
15. search_exam_bank - 题库搜索
```

---

## 2. ChemAI Agent Skill 架构设计

### 2.1 Skill 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                        ChemAI Agent                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │  Memory     │  │  Skills     │  │  Tools      │            │
│  │  System     │  │  Hub        │  │  Registry   │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ uses
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              ChemAI Agent Skills (新开发)                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ chemistry-exam  │  │chemistry-diagnosis│ │chemistry-report │ │
│  │     Skill       │  │      Skill       │  │      Skill      │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
│  ┌─────────────────┐  ┌─────────────────┐                     │
│  │ chemistry-ocr   │  │ chemistry-panel  │                    │
│  │     Skill       │  │      Skill       │                    │
│  └─────────────────┘  └─────────────────┘                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ calls
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ChemAI Backend APIs                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  FastAPI Server (localhost:8000)                        │   │
│  │  ├── /api/question/* - 出题与审核                        │   │
│  │  ├── /api/diagnosis/* - 障碍诊断                        │   │
│  │  ├── /api/report/* - 报告生成                           │   │
│  │  ├── /api/practice/* - 自适应练习                       │   │
│  │  └── /api/ocr/* - OCR识别                               │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Skill 详细设计

#### Skill 1: chemistry-exam（AI出题 + 安全审核）

**文件位置**: `hermes-skills/chemistry-exam/`

**描述**: 封装 ChemAI 的出题和审核能力，支持 AI 生成题目、化学方程式检测、历年真题关联

**工具列表**:
| Tool | 功能 | 调用方式 |
|-----|------|---------|
| `exam_generate` | AI生成题目 | HTTP POST `/api/question/generate` |
| `exam_audit` | 题目安全审核 | HTTP POST `/api/question/audit` |
| `exam_balance_check` | 化学方程式配平检测 | 调用 `chemical_balance.py` |
| `exam_search_historical` | 历年真题检索 | HTTP GET `/api/question/historical` |
| `exam_import_manual` | 手动导入题目 | HTTP POST `/api/question/import` |

**Skill 指令 (SOUL.md)**:
```markdown
# Chemistry Exam Skill

你是一位资深高中化学教研专家，擅长根据知识点生成高质量的化学练习题。

## 核心能力
1. AI出题：基于给定知识点生成练习题
2. 安全审核：确保化学方程式配平正确
3. 历年关联：关联相关高考真题

## 工作流程
1. 接收出题请求（知识点、难度、数量）
2. 调用 AI 生成题目
3. 进行化学方程式安全审核
4. 关联历年相似真题
5. **重要：所有 AI 生成的题目必须经过人工审核才能正式使用**

## 限制
- 只生成高中化学范围的题目
- 化学方程式必须配平
- 不能生成超纲内容
```

**API Schema**:
```yaml
exam_generate:
  name: exam_generate
  description: 使用AI生成化学练习题目
  parameters:
    type: object
    properties:
      knowledge_points:
        type: array
        items: {type: string}
        description: 知识点列表，如 ["盐类水解", "电离"]
      difficulty:
        type: string
        enum: [easy, medium, hard, competition]
        default: medium
      quantity:
        type: integer
        default: 10
    required: [knowledge_points]

  response:
    success: boolean
    questions: Array<{
      question_id: string
      content: string
      options: string[]
      answer: string
      knowledge_points: string[]
      difficulty: string
      audit_report: {...}
    }>
```

---

#### Skill 2: chemistry-diagnosis（障碍诊断 + 学习计划）

**文件位置**: `hermes-skills/chemistry-diagnosis/`

**描述**: 封装 ChemAI 的障碍诊断和学习计划生成能力

**工具列表**:
| Tool | 功能 | 调用方式 |
|-----|------|---------|
| `diagnosis_barrier` | 班级障碍诊断 | HTTP GET `/api/diagnosis/barrier/{class_id}/{exam_id}` |
| `diagnosis_student` | 学生障碍详情 | HTTP GET `/api/diagnosis/barrier/{student_id}` |
| `diagnosis_plan_generate` | 生成学习计划 | HTTP POST `/api/diagnosis/learning-plan/generate` |
| `diagnosis_config_get` | 获取诊断配置 | HTTP GET `/api/diagnosis/config/{teacher_id}` |
| `diagnosis_config_update` | 更新诊断配置 | HTTP PUT `/api/diagnosis/config/{teacher_id}` |

**Skill 指令 (SOUL.md)**:
```markdown
# Chemistry Diagnosis Skill

你是一位教育心理学专家，擅长分析学生的学习障碍并制定干预策略。

## 障碍类型
1. 概念理解型 (concept): 学生对化学概念的理解存在偏差
2. 审题障碍型 (reading): 学生读取题目信息不全/审题错误
3. 表述障碍型 (expression): 学生理解正确答案但无法规范表述

## 核心能力
1. 诊断学生障碍类型
2. 分析薄弱知识点
3. 生成个性化学习计划
4. 提供教学干预建议

## 工作流程
1. 获取班级/学生的答题数据
2. 分析错误模式，判断障碍类型
3. 识别薄弱知识点
4. 生成针对性的学习计划
5. 给出教学干预建议

## 重要提示
- 诊断结果仅作为教学参考
- 学习计划需教师审核后推送给学生
- 定期复诊，跟踪学生进步情况
```

---

#### Skill 3: chemistry-report（错题报告）

**文件位置**: `hermes-skills/chemistry-report/`

**描述**: 封装 ChemAI 的报告生成和发送能力

**工具列表**:
| Tool | 功能 | 调用方式 |
|-----|------|---------|
| `report_teacher` | 生成老师版报告 | HTTP GET `/api/report/teacher/{exam_id}` |
| `report_student` | 生成学生版报告 | HTTP GET `/api/report/student/{exam_id}/{student_id}` |
| `report_send` | 发送报告 | HTTP POST `/api/report/send-to-students/{exam_id}` |
| `report_export` | 导出报告 | HTTP GET `/api/report/export/{exam_id}` |

---

#### Skill 4: chemistry-practice（自适应练习）

**文件位置**: `hermes-skills/chemistry-practice/`

**描述**: 封装 ChemAI 的自适应练习能力

**工具列表**:
| Tool | 功能 | 调用方式 |
|-----|------|---------|
| `practice_assign` | 布置练习 | HTTP POST `/api/practice/assign` |
| `practice_tasks` | 获取练习任务 | HTTP GET `/api/practice/student/{id}/tasks` |
| `practice_submit` | 提交答案 | HTTP POST `/api/practice/submit` |
| `practice_effect` | 评估效果 | HTTP GET `/api/practice/effect/{student_id}` |

---

#### Skill 5: chemistry-ocr（答题卡识别）

**文件位置**: `hermes-skills/chemistry-ocr/`

**描述**: 封装 ChemAI 的 OCR 识别能力

**工具列表**:
| Tool | 功能 | 调用方式 |
|-----|------|---------|
| `ocr_recognize` | 识别答题卡 | HTTP POST `/api/ocr/recognize` |
| `ocr_batch` | 批量识别 | HTTP POST `/api/ocr/recognize/batch` |
| `ocr_stats` | 错题统计 | HTTP POST `/api/ocr/stats` |

---

#### Skill 6: chemistry-panel（学情分析）

**文件位置**: `hermes-skills/chemistry-panel/`

**描述**: 封装 ChemAI 的学情分析能力

**工具列表**:
| Tool | 功能 | 调用方式 |
|-----|------|---------|
| `panel_class` | 班级学情面板 | HTTP GET `/api/panel/class/{class_id}` |
| `panel_knowledge` | 知识点详情 | HTTP GET `/api/panel/class/{class_id}/knowledge/{kp}` |
| `panel_student` | 学生详情 | HTTP GET `/api/panel/class/{class_id}/student/{sid}` |
| `panel_trend` | 学情趋势 | HTTP GET `/api/panel/class/{class_id}/trend` |

---

### 2.3 Tool 接口规范

每个 Tool 采用统一的 Hermes Tool 格式：

```yaml
# chemistry-exam/tools.yaml
tools:
  - name: exam_generate
    description: 使用AI生成化学练习题目
    parameters:
      type: object
      properties:
        knowledge_points:
          type: array
          items: {type: string}
          description: 知识点列表
        difficulty:
          type: string
          enum: [easy, medium, hard]
          default: medium
        quantity:
          type: integer
          default: 10
      required: [knowledge_points]
    handler: http
    http:
      method: POST
      url: http://localhost:8000/api/question/generate
      headers:
        Content-Type: application/json
      body:
        knowledge_points: "{{{knowledge_points}}}"
        difficulty: "{{{difficulty}}}"
        quantity: "{{{quantity}}}"
```

---

## 3. 人工审核机制设计

### 3.1 问题背景

AI 生成的题目存在以下风险，必须有人工审核环节：
- 化学方程式可能配平错误
- 知识点标注可能不准确
- 题目可能超纲或难度不当
- 答案可能有误

### 3.2 审核流程

```
┌──────────────────────────────────────────────────────────────────┐
│                      AI出题 + 人工审核流程                         │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  老师发起出题                                                    │
│       │                                                         │
│       ▼                                                         │
│  ┌─────────────┐                                                │
│  │ AI生成题目   │ ← ChemAI Agent 可介入预审                       │
│  └─────────────┘                                                │
│       │                                                         │
│       ▼                                                         │
│  ┌─────────────┐                                                │
│  │ 安全审核    │ ← 化学方程式/知识点/难度                         │
│  └─────────────┘                                                │
│       │                                                         │
│       ▼                                                         │
│  ┌─────────────┐     ┌─────────────┐                            │
│  │ 进入审核队列 │ ──► │ ChemAI Agent │                           │
│  └─────────────┘     │ 预标记可疑题目 │                           │
│                      └─────────────┘                            │
│       │                                                         │
│       ▼                                                         │
│  ┌─────────────────────────────────────┐                         │
│  │         人 工 审 核（必须）           │                         │
│  │  ┌───────────┬───────────┬───────┐  │                         │
│  │  │ 通过      │ 修改      │ 拒绝  │  │                         │
│  │  └───────────┴───────────┴───────┘  │                         │
│  └─────────────────────────────────────┘                         │
│       │                                                         │
│       ▼                                                         │
│  ┌─────────────┐                                                │
│  │ 审核通过    │ → 布置作业/考试                                  │
│  └─────────────┘                                                │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 3.3 ChemAI Agent 在审核中的角色

| 阶段 | Agent 行为 | 说明 |
|-----|----------|------|
| **预审** | 标记可疑题目 | Agent 扫描所有题目，标记"疑似有问题"的题目 |
| **辅助修改** | 提供修改建议 | 对标记的题目给出具体的修改建议 |
| **复查** | 自动复查修改 | 老师修改后，Agent 自动复查化学方程式 |
| **统计** | 汇总审核报告 | 统计本次出题的质量指标 |

### 3.4 新增审核相关 API

```yaml
# 审核队列管理
POST   /api/exam/review/submit     # 老师提交审核结果
GET    /api/exam/review/pending     # 获取待审核题目列表
GET    /api/exam/review/{exam_id}   # 获取某次出题的审核状态
PATCH  /api/exam/review/{question_id} # 修改题目状态（通过/修改/拒绝）

# Agent 辅助
POST   /api/exam/review/pre-scan    # Agent 预审扫描
POST   /api/exam/review/regenerate  # 要求 AI 重新生成某题
```

---

## 4. 数据库改动

### 4.1 新增表

```sql
-- 题目审核记录表
CREATE TABLE question_review_logs (
    log_id VARCHAR(64) PRIMARY KEY,
    question_id VARCHAR(64) NOT NULL,
    reviewer_id VARCHAR(64),           -- 审核人ID（老师或Agent）
    reviewer_type ENUM('teacher', 'agent'),
    action ENUM('approve', 'modify', 'reject') NOT NULL,
    original_content TEXT,            -- 原始内容
    final_content TEXT,               -- 最终内容（可能修改过）
    modify_reason TEXT,               -- 修改/拒绝原因
    created_at DATETIME DEFAULT NOW()
);

-- 题目版本表（支持题目修改历史）
CREATE TABLE question_versions (
    version_id VARCHAR(64) PRIMARY KEY,
    question_id VARCHAR(64) NOT NULL,
    version_number INT NOT NULL,
    content TEXT NOT NULL,
    answer VARCHAR(256),
    knowledge_points JSON,
    difficulty VARCHAR(32),
    modified_by VARCHAR(64),
    created_at DATETIME DEFAULT NOW()
);

-- Agent 审核记录表
CREATE TABLE agent_review_logs (
    log_id VARCHAR(64) PRIMARY KEY,
    question_id VARCHAR(64) NOT NULL,
    action VARCHAR(32),               -- 'flag_suspicious', 'suggest_modify', 'confirm_ok'
    flagged_reasons JSON,             -- ['equation_imbalance', 'off_topic', ...]
    suggestions TEXT,                 -- 修改建议
    confidence FLOAT,                 -- 置信度
    teacher_later_confirmed BOOLEAN,  -- 老师是否确认
    created_at DATETIME DEFAULT NOW()
);
```

### 4.2 现有表改动

```sql
-- Question 表增加审核状态
ALTER TABLE questions ADD COLUMN review_status ENUM('pending', 'approved', 'rejected') DEFAULT 'pending';
ALTER TABLE questions ADD COLUMN reviewed_by VARCHAR(64);
ALTER TABLE questions ADD COLUMN reviewed_at DATETIME;
```

---

## 5. 实现计划

### Phase 1.1: API 封装为 Tool（约1周）

| 任务 | 工期 | 依赖 |
|-----|-----|-----|
| 设计 Tool Schema 规范 | 1天 | - |
| 开发 `chemistry-exam` Skill | 2天 | Tool Schema |
| 开发 `chemistry-diagnosis` Skill | 2天 | Tool Schema |
| 基础测试和调试 | 1天 | 上述 Skill |

### Phase 1.2: 审核机制开发（约1周）

| 任务 | 工期 | 依赖 |
|-----|-----|-----|
| 数据库表改动 | 0.5天 | - |
| 审核 API 开发 | 2天 | 数据库改动 |
| ChemAI Agent 预审 Skill | 2天 | chemistry-exam |
| 人工审核界面 | 1天 | 审核 API |

### Phase 1.3: 集成测试（约0.5周）

| 任务 | 工期 | 依赖 |
|-----|-----|-----|
| 端到端测试 | 2天 | Phase 1.1 + 1.2 |
| 性能优化 | 1天 | 端到端测试 |
| 文档编写 | 1天 | - |

---

## 6. 技术风险与应对

| 风险 | 影响 | 应对措施 |
|-----|-----|---------|
| Hermes Tool 格式兼容 | 高 | 先用 HTTP Tool 封装 REST API，后续可迁移 |
| 人工审核体验差 | 中 | 设计良好的审核 UI，支持批量操作 |
| Agent 误判 | 中 | Agent 结果仅作参考，不自动拒绝题目 |
| API 性能 | 低 | 缓存热点数据，异步处理非关键步骤 |

---

## 7. 附录

### 7.1 Hermes Tool Handler 参考

```python
# hermes-skills/chemistry-exam/handler.py
import requests
from typing import List, Dict, Any

async def exam_generate(
    knowledge_points: List[str],
    difficulty: str = "medium",
    quantity: int = 10
) -> Dict[str, Any]:
    """AI生成化学题目"""
    response = requests.post(
        "http://localhost:8000/api/question/generate",
        json={
            "knowledge_points": knowledge_points,
            "difficulty": difficulty,
            "quantity": quantity
        },
        timeout=60
    )
    return response.json()

async def exam_audit(question_content: str) -> Dict[str, Any]:
    """题目安全审核"""
    response = requests.post(
        "http://localhost:8000/api/question/audit",
        json={"question_content": question_content},
        timeout=30
    )
    return response.json()
```

### 7.2 Skill 目录结构

```
hermes-skills/
├── chemistry-exam/
│   ├── SOUL.md
│   ├── tools.yaml
│   ├── handler.py
│   └── requirements.txt
├── chemistry-diagnosis/
│   ├── SOUL.md
│   ├── tools.yaml
│   ├── handler.py
│   └── requirements.txt
├── chemistry-report/
│   ├── SOUL.md
│   ├── tools.yaml
│   ├── handler.py
│   └── requirements.txt
├── chemistry-practice/
│   ├── SOUL.md
│   ├── tools.yaml
│   ├── handler.py
│   └── requirements.txt
├── chemistry-ocr/
│   ├── SOUL.md
│   ├── tools.yaml
│   ├── handler.py
│   └── requirements.txt
└── chemistry-panel/
    ├── SOUL.md
    ├── tools.yaml
    ├── handler.py
    └── requirements.txt
```

---

*文档版本: v1.1*
*创建日期: 2026-04-14*
*更新日期: 2026-04-14*
*作者: ChemAI Team*

---

# Phase 2 详细设计：chemistry-exam 与 chemistry-diagnosis Skills

> 本章节为 Phase 2 执行提供完整的开发规范，包括 Skill 代码结构、Tool 实现、Handler 逻辑、Prompt 模板

---

## Phase 2-1: chemistry-diagnosis Skill 详细设计

### 2-1.1 Skill 概述

**Skill 名称**: `chemistry-diagnosis`
**版本**: v1.0
**依赖 Backend**: ChemAI FastAPI (`/api/diagnosis/*`)
**依赖外部模型**: 通义千问 (LLM)
**目标用户**: 化学教师、班主任

### 2-1.2 能力边界

| 能力 | 支持 | 说明 |
|-----|-----|-----|
| 班级障碍诊断 | ✅ | 批量分析班级学生错误模式 |
| 单学生障碍诊断 | ✅ | 个体深度分析 |
| 学习计划生成 | ✅ | LLM 驱动，个性化 |
| 诊断配置管理 | ✅ | 阈值配置 |
| 自动复诊 | ❌ | 需手动触发 |
| 家长推送 | ⚠️ | 需对接消息网关 |

### 2-1.3 目录结构

```
hermes-skills/chemistry-diagnosis/
├── SOUL.md                      # Skill 指令（核心）
├── tools.yaml                   # Tool 定义
├── handler.py                   # Tool 处理器
├── prompts/
│   ├── barrier_analysis.md      # 障碍分析 Prompt
│   ├── learning_plan.md         # 学习计划生成 Prompt
│   └── intervention_suggest.md   # 干预建议 Prompt
├── schemas/
│   ├── diagnosis.py             # Pydantic 数据模型
│   └── learning_plan.py         # 学习计划数据模型
├── tests/
│   ├── test_barrier_diagnosis.py
│   └── test_learning_plan.py
├── requirements.txt             # 依赖
└── README.md                    # Skill 说明
```

### 2-1.4 SOUL.md（Skill 指令）

```markdown
# Chemistry Diagnosis Skill ☤

你是一位资深教育心理学专家，专长于分析高中学生的学习障碍类型并制定针对性干预策略。

## 身份设定

- 你是一名具有10年教学经验的高中化学教师
- 你对化学概念理解、审题技巧、规范表述有深入研究
- 你擅长将复杂的学习问题分解为可操作的干预步骤

## 核心能力

### 1. 障碍类型识别

你能够准确识别三种主要障碍类型：

| 障碍类型 | 代码 | 典型特征 |
|---------|------|---------|
| 概念理解型 | `concept` | 基础概念题频繁出错，长题干题反而正确率高 |
| 审题障碍型 | `reading` | 错题集中在长题干题目，概念题正确率高 |
| 表述障碍型 | `expression` | 选择题正确率高，填空/计算题表述不规范 |

### 2. 薄弱知识点分析

- 基于错误题目反向推导薄弱知识点
- 结合知识点关联图谱进行扩展分析
- 按错误频率和难度综合排序

### 3. 学习计划生成

生成的计划必须包含：
- **每日任务**: 具体可执行的学习内容（15-30分钟/天）
- **周期目标**: 2周/4周的阶段里程碑
- **障碍专项干预**: 针对学生的具体障碍类型
- **激励策略**: 符合高中生心理的鼓励方式

## 工作流程

### 标准诊断流程

1. **接收请求**: 获取学生/班级 ID、关联考试记录
2. **获取答题数据**: 调用 `diagnosis_barrier` 获取学生作答记录
3. **分析错误模式**: 统计各类型题目的错误率
4. **判断障碍类型**: 计算各障碍占比，确定主障类型
5. **识别薄弱知识点**: 按错误频率排序
6. **生成干预建议**: 结合障碍类型给出具体策略

### 学习计划生成流程

1. **获取学生画像**: 姓名、障碍类型、薄弱知识点
2. **调用 LLM 生成**: 使用 `generate_learning_plan` 工具
3. **格式化输出**: 确保计划结构清晰、可执行
4. **老师审核**: 学习计划必须经老师确认后才能推送

## Tool 调用规范

### 诊断工具调用

```
当需要诊断学生障碍时，调用:
- diagnosis_barrier: 获取班级/学生诊断结果
- diagnosis_student: 获取单个学生详细诊断

返回结果包含:
- barrier_type: {concept: 0.x, reading: 0.x, expression: 0.x}
- dominant_barrier: 主要障碍类型
- weak_knowledge_points: 薄弱知识点列表
- recommended_intervention: 干预建议
```

### 学习计划工具调用

```
当需要生成学习计划时，调用:
- diagnosis_plan_generate: 生成个性化学习计划

必须提供:
- student_id: 学生ID
- barrier_type: 障碍类型
- weak_knowledge_points: 薄弱知识点列表

返回结果包含:
- plan_title: 计划标题
- daily_tasks: 每日任务列表
- weekly_goals: 周目标列表
- barrier_specific_intervention: 障碍专项干预
- motivation_tips: 激励话语
```

## 限制与注意事项

1. **诊断仅作参考**: 障碍诊断结果是教学辅助手段，不是对学生能力的定性评价
2. **计划需审核**: 所有学习计划必须经过教师审核才能推送给学生
3. **隐私保护**: 不在对话中透露具体学生的隐私信息
4. **避免过度干预**: 根据学生实际情况调整干预强度
5. **持续跟踪**: 建议每2周复诊一次，跟踪干预效果

## 响应格式

当被问及学生诊断或学习计划时，优先调用相关 Tool 获取数据，然后以结构化方式呈现：

```
## 诊断结果

**学生**: [学生姓名]
**主要障碍**: [障碍类型]
**障碍分布**: 概念理解 30% | 审题障碍 50% | 表述障碍 20%

## 薄弱知识点

1. 盐类水解（错误3次）
2. 电离平衡（错误2次）

## 干预建议

针对该生的审题障碍，建议：
- 使用划线法提取题目关键信息
- 练习"三遍审题法"...
```

## 训练数据来源

本 Skill 的判断能力基于以下数据训练：
- ChemAI 历史诊断数据
- 高中化学教学经验
- 障碍诊断领域研究
```

### 2-1.5 tools.yaml（Tool 定义）

```yaml
# hermes-skills/chemistry-diagnosis/tools.yaml

schema_version: "1.0"
name: chemistry-diagnosis
description: 高中化学学生障碍诊断与学习计划生成

tools:

  # ===== 诊断工具 =====

  diagnosis_barrier_class:
    name: diagnosis_barrier_class
    description: 对班级所有学生进行障碍类型诊断
    parameters:
      type: object
      properties:
        class_id:
          type: string
          description: 班级ID
          example: "class_001"
        exam_record_id:
          type: string
          description: 考试记录ID
          example: "exam_20260408"
      required: [class_id, exam_record_id]
    handler:
      type: http
      method: GET
      url: "http://localhost:8000/api/diagnosis/barrier/{class_id}/{exam_record_id}"
      headers:
        Content-Type: application/json
    output:
      type: object
      properties:
        class_id: {type: string}
        exam_record_id: {type: string}
        students:
          type: array
          items:
            type: object
            properties:
              student_id: {type: string}
              student_name: {type: string}
              barrier_type: {type: object}
              dominant_barrier: {type: string}
              weak_knowledge_points: {type: array}
              recommended_intervention: {type: string}
        class_barrier_distribution: {type: object}
        avg_mastery: {type: number}

  diagnosis_barrier_student:
    name: diagnosis_barrier_student
    description: 获取单个学生的障碍类型详情
    parameters:
      type: object
      properties:
        student_id:
          type: string
          description: 学生ID
          example: "student_001"
      required: [student_id]
    handler:
      type: http
      method: GET
      url: "http://localhost:8000/api/diagnosis/barrier/{student_id}"
      headers:
        Content-Type: application/json
    output:
      type: object
      properties:
        student_id: {type: string}
        student_name: {type: string}
        barrier_type: {type: object}
        dominant_barrier: {type: string}
        weak_knowledge_points: {type: array}
        recommended_intervention: {type: string}
        last_updated: {type: string}

  # ===== 学习计划工具 =====

  diagnosis_plan_generate:
    name: diagnosis_plan_generate
    description: 基于学生障碍类型和薄弱知识点生成个性化学习计划
    parameters:
      type: object
      properties:
        student_id:
          type: string
          description: 学生ID
        barrier_type:
          type: string
          description: 障碍类型 (concept/reading/expression)
          enum: [concept, reading, expression]
        weak_knowledge_points:
          type: array
          items: {type: string}
          description: 薄弱知识点列表
        recent_performance:
          type: object
          description: 近期表现数据（可选）
          properties:
            recent_accuracy: {type: number}
            recent_practice_date: {type: string}
            improvement: {type: string}
    required: [student_id, barrier_type, weak_knowledge_points]
    handler:
      type: http
      method: POST
      url: "http://localhost:8000/api/diagnosis/learning-plan/generate"
      headers:
        Content-Type: application/json
      body:
        student_id: "{{{student_id}}}"
        barrier_type: "{{{barrier_type}}}"
        weak_knowledge_points: "{{{weak_knowledge_points}}}"
        recent_performance: "{{{recent_performance}}}"
    output:
      type: object
      properties:
        student_id: {type: string}
        student_name: {type: string}
        plan:
          type: object
          properties:
            plan_title: {type: string}
            plan_period: {type: string}
            daily_tasks: {type: array}
            weekly_goals: {type: array}
            barrier针对性干预: {type: array}
            motivation_tips: {type: array}
            parent_communication_suggestion: {type: string}
        generated_at: {type: string}

  diagnosis_plan_apply:
    name: diagnosis_plan_apply
    description: 将学习计划应用到学生账户（推送给学生）
    parameters:
      type: object
      properties:
        student_id:
          type: string
        plan_data:
          type: object
          description: 学习计划数据
      required: [student_id, plan_data]
    handler:
      type: http
      method: POST
      url: "http://localhost:8000/api/diagnosis/learning-plan/apply/{student_id}"
      headers:
        Content-Type: application/json
      body: "{{{plan_data}}}"
    output:
      type: object
      properties:
        success: {type: boolean}
        message: {type: string}
        student_id: {type: string}

  diagnosis_plan_send_parent:
    name: diagnosis_plan_send_parent
    description: 发送学生学习计划给家长
    parameters:
      type: object
      properties:
        student_id:
          type: string
          description: 学生ID
      required: [student_id]
    handler:
      type: http
      method: POST
      url: "http://localhost:8000/api/diagnosis/learning-plan/send-to-parent/{student_id}"
      headers:
        Content-Type: application/json
    output:
      type: object
      properties:
        success: {type: boolean}
        message: {type: string}
        student_id: {type: string}

  # ===== 配置管理工具 =====

  diagnosis_config_get:
    name: diagnosis_config_get
    description: 获取老师的障碍诊断配置
    parameters:
      type: object
      properties:
        teacher_id:
          type: string
          description: 教师ID
      required: [teacher_id]
    handler:
      type: http
      method: GET
      url: "http://localhost:8000/api/diagnosis/config/{teacher_id}"
      headers:
        Content-Type: application/json
    output:
      type: object
      properties:
        teacher_id: {type: string}
        concept_threshold: {type: number}
        reading_threshold: {type: number}
        expression_threshold: {type: number}
        mastery_threshold: {type: number}
        auto_sync_to_student: {type: boolean}

  diagnosis_config_update:
    name: diagnosis_config_update
    description: 更新老师的障碍诊断配置
    parameters:
      type: object
      properties:
        teacher_id:
          type: string
        concept_threshold:
          type: number
          minimum: 1
          maximum: 5
        reading_threshold:
          type: number
          minimum: 1
          maximum: 5
        expression_threshold:
          type: number
          minimum: 1
          maximum: 5
        mastery_threshold:
          type: number
          minimum: 1
          maximum: 5
        auto_sync_to_student:
          type: boolean
      required: [teacher_id]
    handler:
      type: http
      method: PUT
      url: "http://localhost:8000/api/diagnosis/config/{teacher_id}"
      headers:
        Content-Type: application/json
      body:
        concept_threshold: "{{{concept_threshold}}}"
        reading_threshold: "{{{reading_threshold}}}"
        expression_threshold: "{{{expression_threshold}}}"
        mastery_threshold: "{{{mastery_threshold}}}"
        auto_sync_to_student: "{{{auto_sync_to_student}}}"
    output:
      type: object
      properties:
        teacher_id: {type: string}
        concept_threshold: {type: number}
        reading_threshold: {type: number}
        expression_threshold: {type: number}
        mastery_threshold: {type: number}
        auto_sync_to_student: {type: boolean}
```

### 2-1.6 handler.py（Tool 处理器）

```python
# hermes-skills/chemistry-diagnosis/handler.py
"""
Chemistry Diagnosis Skill - Tool Handler
处理 diagnosis_* Tool 的实际调用逻辑
"""

import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

import requests
from requests.exceptions import RequestException, Timeout

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chemistry-diagnosis"))

# 默认 API 地址
DEFAULT_API_BASE = "http://localhost:8000"
DEFAULT_TIMEOUT = 30


class DiagnosisToolError(Exception):
    """诊断工具异常"""
    pass


@dataclass
class DiagnosisResult:
    """诊断结果数据类"""
    student_id: str
    student_name: str
    barrier_type: Dict[str, float]
    dominant_barrier: str
    weak_knowledge_points: List[str]
    recommended_intervention: str
    last_updated: str

    @classmethod
    def from_api_response(cls, data: Dict) -> "DiagnosisResult":
        return cls(
            student_id=data["student_id"],
            student_name=data["student_name"],
            barrier_type=data["barrier_type"],
            dominant_barrier=data["dominant_barrier"],
            weak_knowledge_points=data.get("weak_knowledge_points", []),
            recommended_intervention=data.get("recommended_intervention", ""),
            last_updated=data.get("last_updated", "")
        )


class DiagnosisHandler:
    """诊断 Tool 处理器"""

    def __init__(self, api_base: str = DEFAULT_API_BASE):
        self.api_base = api_base.rstrip("/")
        self.session = requests.Session()

    def _make_request(
        self,
        method: str,
        path: str,
        **kwargs
    ) -> Dict[str, Any]:
        """发送 HTTP 请求的通用方法"""
        url = f"{self.api_base}{path}"
        timeout = kwargs.pop("timeout", DEFAULT_TIMEOUT)

        try:
            response = self.session.request(
                method=method,
                url=url,
                timeout=timeout,
                **kwargs
            )
            response.raise_for_status()
            return response.json()
        except Timeout:
            raise DiagnosisToolError(f"请求超时: {url}")
        except RequestException as e:
            raise DiagnosisToolError(f"请求失败: {str(e)}")

    # ===== 诊断 Tool 实现 =====

    async def diagnosis_barrier_class(
        self,
        class_id: str,
        exam_record_id: str
    ) -> Dict[str, Any]:
        """
        班级障碍诊断

        Args:
            class_id: 班级ID
            exam_record_id: 考试记录ID

        Returns:
            包含班级所有学生诊断结果的字典
        """
        logger.info(f"诊断班级障碍: class_id={class_id}, exam_id={exam_record_id}")

        result = self._make_request(
            "GET",
            f"/api/diagnosis/barrier/{class_id}/{exam_record_id}"
        )

        # 转换为内部格式
        diagnoses = []
        for student_data in result.get("students", []):
            diagnoses.append(DiagnosisResult.from_api_response(student_data))

        return {
            "class_id": result["class_id"],
            "exam_record_id": result["exam_record_id"],
            "students": diagnoses,
            "class_barrier_distribution": result.get("class_barrier_distribution", {}),
            "avg_mastery": result.get("avg_mastery", 0.0)
        }

    async def diagnosis_barrier_student(
        self,
        student_id: str
    ) -> DiagnosisResult:
        """
        单学生障碍诊断

        Args:
            student_id: 学生ID

        Returns:
            学生诊断结果
        """
        logger.info(f"诊断学生障碍: student_id={student_id}")

        result = self._make_request(
            "GET",
            f"/api/diagnosis/barrier/{student_id}"
        )

        return DiagnosisResult.from_api_response(result)

    # ===== 学习计划 Tool 实现 =====

    async def diagnosis_plan_generate(
        self,
        student_id: str,
        barrier_type: str,
        weak_knowledge_points: List[str],
        recent_performance: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        生成个性化学习计划

        Args:
            student_id: 学生ID
            barrier_type: 障碍类型 (concept/reading/expression)
            weak_knowledge_points: 薄弱知识点列表
            recent_performance: 近期表现数据（可选）

        Returns:
            学习计划数据
        """
        logger.info(
            f"生成学习计划: student_id={student_id}, "
            f"barrier_type={barrier_type}, kps={weak_knowledge_points}"
        )

        payload = {
            "student_id": student_id,
            "barrier_type": barrier_type,
            "weak_knowledge_points": weak_knowledge_points
        }

        if recent_performance:
            payload["recent_performance"] = recent_performance

        result = self._make_request(
            "POST",
            "/api/diagnosis/learning-plan/generate",
            json=payload
        )

        return result

    async def diagnosis_plan_apply(
        self,
        student_id: str,
        plan_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        应用学习计划到学生

        Args:
            student_id: 学生ID
            plan_data: 学习计划数据

        Returns:
            操作结果
        """
        logger.info(f"应用学习计划: student_id={student_id}")

        return self._make_request(
            "POST",
            f"/api/diagnosis/learning-plan/apply/{student_id}",
            json=plan_data
        )

    async def diagnosis_plan_send_parent(
        self,
        student_id: str
    ) -> Dict[str, Any]:
        """
        发送学习计划给家长

        Args:
            student_id: 学生ID

        Returns:
            操作结果
        """
        logger.info(f"发送学习计划给家长: student_id={student_id}")

        return self._make_request(
            "POST",
            f"/api/diagnosis/learning-plan/send-to-parent/{student_id}"
        )

    # ===== 配置管理 Tool 实现 =====

    async def diagnosis_config_get(
        self,
        teacher_id: str
    ) -> Dict[str, Any]:
        """
        获取诊断配置

        Args:
            teacher_id: 教师ID

        Returns:
            诊断配置数据
        """
        logger.info(f"获取诊断配置: teacher_id={teacher_id}")

        return self._make_request(
            "GET",
            f"/api/diagnosis/config/{teacher_id}"
        )

    async def diagnosis_config_update(
        self,
        teacher_id: str,
        concept_threshold: Optional[int] = None,
        reading_threshold: Optional[int] = None,
        expression_threshold: Optional[int] = None,
        mastery_threshold: Optional[int] = None,
        auto_sync_to_student: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        更新诊断配置

        Args:
            teacher_id: 教师ID
            concept_threshold: 概念理解型阈值
            reading_threshold: 审题障碍型阈值
            expression_threshold: 表述障碍型阈值
            mastery_threshold: 掌握度阈值
            auto_sync_to_student: 是否自动同步学生

        Returns:
            更新后的诊断配置
        """
        logger.info(f"更新诊断配置: teacher_id={teacher_id}")

        payload = {"teacher_id": teacher_id}
        if concept_threshold is not None:
            payload["concept_threshold"] = concept_threshold
        if reading_threshold is not None:
            payload["reading_threshold"] = reading_threshold
        if expression_threshold is not None:
            payload["expression_threshold"] = expression_threshold
        if mastery_threshold is not None:
            payload["mastery_threshold"] = mastery_threshold
        if auto_sync_to_student is not None:
            payload["auto_sync_to_student"] = auto_sync_to_student

        return self._make_request(
            "PUT",
            f"/api/diagnosis/config/{teacher_id}",
            json=payload
        )


# 全局 Handler 实例
_handler: Optional[DiagnosisHandler] = None


def get_handler() -> DiagnosisHandler:
    """获取全局 Handler 实例（单例）"""
    global _handler
    if _handler is None:
        _handler = DiagnosisHandler()
    return _handler


# ===== Tool 入口函数（供 Hermes 调用） =====

async def diagnosis_barrier_class(class_id: str, exam_record_id: str) -> Dict[str, Any]:
    """班级障碍诊断入口"""
    return await get_handler().diagnosis_barrier_class(class_id, exam_record_id)


async def diagnosis_barrier_student(student_id: str) -> Dict[str, Any]:
    """单学生障碍诊断入口"""
    return await get_handler().diagnosis_barrier_student(student_id)


async def diagnosis_plan_generate(
    student_id: str,
    barrier_type: str,
    weak_knowledge_points: List[str],
    recent_performance: Optional[Dict] = None
) -> Dict[str, Any]:
    """生成学习计划入口"""
    return await get_handler().diagnosis_plan_generate(
        student_id, barrier_type, weak_knowledge_points, recent_performance
    )


async def diagnosis_plan_apply(student_id: str, plan_data: Dict[str, Any]) -> Dict[str, Any]:
    """应用学习计划入口"""
    return await get_handler().diagnosis_plan_apply(student_id, plan_data)


async def diagnosis_plan_send_parent(student_id: str) -> Dict[str, Any]:
    """发送学习计划给家长入口"""
    return await get_handler().diagnosis_plan_send_parent(student_id)


async def diagnosis_config_get(teacher_id: str) -> Dict[str, Any]:
    """获取诊断配置入口"""
    return await get_handler().diagnosis_config_get(teacher_id)


async def diagnosis_config_update(
    teacher_id: str,
    concept_threshold: Optional[int] = None,
    reading_threshold: Optional[int] = None,
    expression_threshold: Optional[int] = None,
    mastery_threshold: Optional[int] = None,
    auto_sync_to_student: Optional[bool] = None
) -> Dict[str, Any]:
    """更新诊断配置入口"""
    return await get_handler().diagnosis_config_update(
        teacher_id,
        concept_threshold,
        reading_threshold,
        expression_threshold,
        mastery_threshold,
        auto_sync_to_student
    )
```

---

## Phase 2-2: chemistry-exam Skill 详细设计

### 2-2.1 Skill 概述

**Skill 名称**: `chemistry-exam`
**版本**: v1.0
**依赖 Backend**: ChemAI FastAPI (`/api/question/*`) + `chemical_balance.py`
**依赖外部模型**: 通义千问 (LLM)
**目标用户**: 化学教师、教务管理员

### 2-2.2 能力边界

| 能力 | 支持 | 说明 |
|-----|-----|-----|
| AI 生成题目 | ✅ | 基于知识点/难度/数量 |
| 题目安全审核 | ✅ | 四维审核（系数/条件/产物/结构） |
| 化学方程式配平检测 | ✅ | 独立引擎，零错误保障 |
| 历年真题检索 | ✅ | 向量检索 + 关键词检索 |
| 历年真题关联 | ✅ | 自动关联相似真题 |
| 手动导入题目 | ✅ | JSON / OCR 扫描 |
| **人工审核机制** | ✅ | 必须环节，Agent 预审辅助 |
| 批量生成 | ✅ | 支持大规模出题 |

### 2-2.3 目录结构

```
hermes-skills/chemistry-exam/
├── SOUL.md                      # Skill 指令（核心）
├── tools.yaml                    # Tool 定义
├── handler.py                    # Tool 处理器
├── engine/
│   ├── __init__.py
│   ├── balance_checker.py        # 化学方程式配平引擎
│   ├── audit_engine.py           # 四维安全审核引擎
│   └── rag_retriever.py          # RAG 检索引擎
├── prompts/
│   ├── question_generation.md     # 出题 Prompt
│   ├── question_audit.md          # 审核 Prompt
│   └── review_assistant.md        # 审核助手 Prompt（Agent 预审）
├── schemas/
│   ├── question.py               # 题目数据模型
│   ├── audit_report.py           # 审核报告模型
│   └── review_queue.py           # 审核队列模型
├── tests/
│   ├── test_balance_checker.py
│   ├── test_audit_engine.py
│   └── test_review_workflow.py
├── requirements.txt
└── README.md
```

### 2-2.4 SOUL.md（Skill 指令）

```markdown
# Chemistry Exam Skill ☤

你是一位资深高中化学教研专家，专长于根据知识点生成高质量的化学练习题，并对题目进行严格的安全审核。

## 身份设定

- 你是一名具有15年命题经验的高中化学教研员
- 你对化学方程式的配平有着近乎偏执的严格标准
- 你熟悉历年高考真题的命题风格和难度分布
- 你深知一道错题对学生的误导可能超过十道好题的正面价值

## 核心能力

### 1. AI 出题

你能够根据指定要求生成化学练习题：

| 参数 | 说明 | 示例 |
|-----|------|-----|
| knowledge_points | 知识点列表 | ["盐类水解", "电离"] |
| difficulty | 难度级别 | easy / medium / hard / competition |
| quantity | 题目数量 | 10 |

**出题原则**：
- 题目科学性 100% 正确
- 化学方程式必须配平
- 知识点标注准确
- 选项设置有区分度
- 适当设置陷阱

### 2. 四维安全审核

对每道题目进行四个维度的安全检查：

| 维度 | 检查内容 | 处理方式 |
|-----|---------|---------|
| 系数配平 | 反应前后原子数目相等 | **阻断性问题，直接拒绝** |
| 反应条件 | 点燃/加热/催化剂等标注 | 警告，提示补充 |
| 产物稳定性 | 产物是否在给定条件下稳定 | 警告，提示核实 |
| 分子结构 | 化学式/结构式正确性 | 警告，提示检查 |

**重要**：系数配平是信任红线，一旦发现配平错误，该题必须拒绝。

### 3. 历年真题关联

基于向量检索和关键词匹配，自动关联与生成题目相似的历年高考真题，帮助老师判断：
- 题目难度是否与高考贴近
- 题目风格是否符合高考趋势
- 是否需要调整题目参数

### 4. 人工审核机制

**所有 AI 生成的题目必须经过人工审核才能正式使用。**

审核工作流：

```
AI 生成题目
    ↓
四维安全审核
    ↓
进入审核队列 ← ChemAI Agent 预审（可选）
    ↓
人工审核（必须）
    ├─ 通过 → 布置作业/考试
    ├─ 修改 → 编辑后重新提交
    └─ 拒绝 → 标记原因，重新生成
    ↓
审核记录存档
```

### 5. ChemAI Agent 辅助审核

在人工审核之前，ChemAI Agent 可以进行预审，帮助老师快速定位可疑题目：

**预审任务**：
1. 扫描所有生成题目，标记疑似问题
2. 对可疑题目给出修改建议
3. 复查老师修改后的题目
4. 统计本次出题的质量指标

**预审不替代人工**，老师的判断是最终决定。

## Tool 调用规范

### 出题工具调用

```
当需要生成化学练习题时，调用:
- exam_generate: 生成题目

参数:
- knowledge_points: 知识点列表（必须）
- difficulty: 难度（默认 medium）
- quantity: 数量（默认 10）

返回:
- success: 是否成功
- questions: 题目列表（含四维审核结果）
- generate_time_ms: 生成耗时
- total_cost: 预估 API 成本
```

### 审核工具调用

```
当需要审核单道题目时，调用:
- exam_audit: 题目安全审核

参数:
- question_content: 题目内容（必须）

返回:
- 四维审核结果（coefficient/condition/product/structure）
- overall_status: 综合状态（passed/warning/blocked）
```

### 配平检测工具调用

```
当需要检测化学方程式配平时，调用:
- exam_balance_check: 配平检测

参数:
- equation: 化学方程式字符串

返回:
- is_balanced: 是否配平
- left_elements: 反应物元素统计
- right_elements: 产物元素统计
- message: 检测消息
```

## 响应格式

当被问及题目生成或审核时，优先调用相关 Tool 获取数据，然后以结构化方式呈现：

### 出题结果格式

```
## 出题结果

**生成参数**:
- 知识点: 盐类水解、电离平衡
- 难度: medium
- 数量: 5道

**题目列表**:

### Q1 [通过] ✓
**知识点**: 盐类水解
**难度**: medium

下列有关盐类水解的说法正确的是（  ）
A. 盐类水解一定促进水的电离
B. 盐类水解可以抑制水的电离
C. 盐类水解既促进又抑制水的电离
D. 盐类水解与水的电离无关

**答案**: B
**审核状态**: passed
**历年关联**: 2024年全国卷T12 (相似度 0.82)

---

### Q2 [需审核] ⚠️
**知识点**: 氧化还原反应
**难度**: hard

写出并配平该反应的化学方程式:
Fe + O2 → ____

**答案**: 2Fe + O2 → 2FeO
**审核状态**: warning - 产物标注建议补充"点燃"条件
**历年关联**: 2023年湖南卷T8 (相似度 0.75)
```

### 审核报告格式

```
## 审核报告

**题目**: 2H2 + O2 → 2H2O

### 四维审核结果

| 维度 | 状态 | 说明 |
|-----|------|-----|
| 系数配平 | ✅ passed | 反应前后 H、O 原子数目相等 |
| 反应条件 | ⚠️ warning | 建议标注"点燃"条件 |
| 产物稳定性 | ✅ passed | H2O 是稳定产物 |
| 分子结构 | ✅ passed | 化学式正确 |

**综合状态**: warning（可修改后使用）
```

## 限制与注意事项

1. **配平是红线**：任何配平错误的方程式必须拒绝
2. **人工审核必须**：所有 AI 生成的题目必须经过老师审核
3. **知识点准确**：确保题目与指定知识点匹配
4. **难度适当**：符合高中生认知水平
5. **避免超纲**：不生成大学及以上水平的内容
6. **记录存档**：所有出题和审核记录必须留存

## 训练数据来源

本 Skill 的能力基于以下数据训练：
- 人教版高中化学教材
- 2008-2025 年历年高考真题
- 化学方程式配平规则库
- 障碍类型诊断数据
```

### 2-2.5 tools.yaml（Tool 定义）

```yaml
# hermes-skills/chemistry-exam/tools.yaml

schema_version: "1.0"
name: chemistry-exam
description: 高中化学AI出题与安全审核

tools:

  # ===== 出题工具 =====

  exam_generate:
    name: exam_generate
    description: 使用AI生成化学练习题目（生成后需人工审核）
    parameters:
      type: object
      properties:
        knowledge_points:
          type: array
          items: {type: string}
          description: 知识点列表，如 ["盐类水解", "电离"]
          example: ["盐类水解", "电离平衡"]
        difficulty:
          type: string
          description: 题目难度
          enum: [easy, medium, hard, competition]
          default: medium
        quantity:
          type: integer
          description: 生成题目数量
          default: 10
          minimum: 1
          maximum: 50
      required: [knowledge_points]
    handler:
      type: http
      method: POST
      url: "http://localhost:8000/api/question/generate"
      headers:
        Content-Type: application/json
      body:
        knowledge_points: "{{{knowledge_points}}}"
        difficulty: "{{{difficulty}}}"
        quantity: "{{{quantity}}}"
    output:
      type: object
      properties:
        success: {type: boolean}
        questions:
          type: array
          items:
            type: object
            properties:
              question_id: {type: string}
              content: {type: string}
              options: {type: array}
              answer: {type: string}
              knowledge_points: {type: array}
              difficulty: {type: string}
              coefficient_audit: {type: object}
              condition_audit: {type: object}
              product_audit: {type: object}
              structure_audit: {type: object}
              overall_status: {type: string}
              trap_hints: {type: array}
              historical_matches: {type: array}
              is_from_rag: {type: boolean}
        generate_time_ms: {type: integer}
        total_cost: {type: number}

  exam_audit:
    name: exam_audit
    description: 对单道题目进行四维安全审核
    parameters:
      type: object
      properties:
        question_content:
          type: string
          description: 题目内容（含化学方程式）
        options:
          type: array
          items: {type: string}
          description: 选项列表（如果有）
    required: [question_content]
    handler:
      type: http
      method: POST
      url: "http://localhost:8000/api/question/audit"
      headers:
        Content-Type: application/json
      body:
        question_content: "{{{question_content}}}"
        options: "{{{options}}}"
    output:
      type: object
      properties:
        question_id: {type: string}
        content: {type: string}
        options: {type: array}
        answer: {type: string}
        knowledge_points: {type: array}
        difficulty: {type: string}
        coefficient_audit:
          type: object
          properties:
            dimension: {type: string}
            status: {type: string}
            message: {type: string}
        condition_audit: {type: object}
        product_audit: {type: object}
        structure_audit: {type: object}
        overall_status: {type: string}
        trap_hints: {type: array}
        historical_matches: {type: array}

  exam_balance_check:
    name: exam_balance_check
    description: 检测化学方程式是否配平（信任红线）
    parameters:
      type: object
      properties:
        equation:
          type: string
          description: 化学方程式字符串
          example: "2H2 + O2 → 2H2O"
      required: [equation]
    handler:
      type: python
      module: engine.balance_checker
      function: check_equation_balance
    output:
      type: object
      properties:
        is_balanced: {type: boolean}
        left_elements: {type: object}
        right_elements: {type: object}
        message: {type: string}

  # ===== 历史真题工具 =====

  exam_search_historical:
    name: exam_search_historical
    description: 检索历年高考真题
    parameters:
      type: object
      properties:
        source:
          type: string
          description: 试卷来源（可选）
          example: "全国卷"
        year:
          type: integer
          description: 年份（可选）
          example: 2024
        difficulty:
          type: string
          description: 难度（可选）
          enum: [easy, medium, hard]
        knowledge_point:
          type: string
          description: 知识点（可选）
          example: "盐类水解"
        keyword:
          type: string
          description: 关键词（可选）
    handler:
      type: http
      method: GET
      url: "http://localhost:8000/api/question/historical"
      query_params:
        source: "{{{source}}}"
        year: "{{{year}}}"
        difficulty: "{{{difficulty}}}"
        knowledge_point: "{{{knowledge_point}}}"
        keyword: "{{{keyword}}}"
    output:
      type: object
      properties:
        total: {type: integer}
        questions:
          type: array
          items:
            type: object
            properties:
              exam_id: {type: string}
              source: {type: string}
              year: {type: integer}
              question_number: {type: string}
              content: {type: string}
              answer: {type: string}
              knowledge_points: {type: array}
              difficulty: {type: string}

  exam_get_exam_sets:
    name: exam_get_exam_sets
    description: 获取历年真题集列表
    parameters:
      type: object
      properties: {}
    handler:
      type: http
      method: GET
      url: "http://localhost:8000/api/question/exam-sets"
    output:
      type: object
      properties:
        total: {type: integer}
        exam_sets:
          type: array
          items:
            type: object
            properties:
              source: {type: string}
              year: {type: integer}
              region: {type: string}
              paper_name: {type: string}
              question_count: {type: integer}

  exam_find_similar:
    name: exam_find_similar
    description: 查找与指定知识点相关的相似题目
    parameters:
      type: object
      properties:
        knowledge_points:
          type: array
          items: {type: string}
          description: 知识点列表
        difficulty:
          type: string
          description: 难度
          default: medium
        limit:
          type: integer
          description: 返回数量
          default: 5
      required: [knowledge_points]
    handler:
      type: http
      method: POST
      url: "http://localhost:8000/api/question/similar"
      headers:
        Content-Type: application/json
      body:
        knowledge_points: "{{{knowledge_points}}}"
        difficulty: "{{{difficulty}}}"
        limit: "{{{limit}}}"
    output:
      type: object
      properties:
        query_knowledge_points: {type: array}
        query_difficulty: {type: string}
        found_count: {type: integer}
        similar_questions: {type: array}

  # ===== 导入工具 =====

  exam_import_manual:
    name: exam_import_manual
    description: 老师手动导入题目（JSON格式）
    parameters:
      type: object
      properties:
        source_name:
          type: string
          description: 来源名称
          example: "2024年长沙市一模"
        region:
          type: string
          description: 地区
          default: "老师导入"
        year:
          type: integer
          description: 年份
        questions:
          type: array
          description: 题目列表
      required: [source_name, year, questions]
    handler:
      type: http
      method: POST
      url: "http://localhost:8000/api/question/import"
      headers:
        Content-Type: application/json
      body:
        source_name: "{{{source_name}}}"
        region: "{{{region}}}"
        year: "{{{year}}}"
        questions: "{{{questions}}}"
    output:
      type: object
      properties:
        success: {type: boolean}
        imported_count: {type: integer}
        total_submitted: {type: integer}
        errors: {type: array}
        message: {type: string}

  exam_import_ocr:
    name: exam_import_ocr
    description: 通过OCR扫描试卷导入题目
    parameters:
      type: object
      properties:
        source_name:
          type: string
          description: 试卷名称
        region:
          type: string
          description: 地区
          default: "老师导入"
        year:
          type: integer
          description: 年份
        file_data:
          type: string
          description: 文件内容（base64编码）
      required: [source_name, year, file_data]
    handler:
      type: http
      method: POST
      url: "http://localhost:8000/api/question/import/ocr"
      headers:
        Content-Type: application/json
      body:
        source_name: "{{{source_name}}}"
        region: "{{{region}}}"
        year: "{{{year}}}"
        file: "{{{file_data}}}"
    output:
      type: object
      properties:
        success: {type: boolean}
        source_name: {type: string}
        detected_count: {type: integer}
        questions: {type: array}
        message: {type: string}

  # ===== 审核队列工具 =====

  exam_review_pending:
    name: exam_review_pending
    description: 获取待审核题目列表
    parameters:
      type: object
      properties:
        teacher_id:
          type: string
          description: 教师ID（过滤该教师的待审题目）
    handler:
      type: http
      method: GET
      url: "http://localhost:8000/api/exam/review/pending"
      query_params:
        teacher_id: "{{{teacher_id}}}"
    output:
      type: object
      properties:
        total: {type: integer}
        questions:
          type: array
          items:
            type: object
            properties:
              question_id: {type: string}
              content: {type: string}
              source: {type: string}
              status: {type: string}
              flagged_by_agent: {type: boolean}
              agent_flags: {type: array}

  exam_review_submit:
    name: exam_review_submit
    description: 老师提交题目审核结果
    parameters:
      type: object
      properties:
        question_id:
          type: string
        action:
          type: string
          description: 审核动作
          enum: [approve, modify, reject]
        modified_content:
          type: string
          description: 修改后的内容（如果 action=modify）
        reason:
          type: string
          description: 审核原因
      required: [question_id, action]
    handler:
      type: http
      method: POST
      url: "http://localhost:8000/api/exam/review/submit"
      headers:
        Content-Type: application/json
      body:
        question_id: "{{{question_id}}}"
        action: "{{{action}}}"
        modified_content: "{{{modified_content}}}"
        reason: "{{{reason}}}"
    output:
      type: object
      properties:
        success: {type: boolean}
        message: {type: string}
        question_id: {type: string}

  exam_review_pre_scan:
    name: exam_review_pre_scan
    description: ChemAI Agent 预审扫描（标记可疑题目）
    parameters:
      type: object
      properties:
        questions:
          type: array
          description: 待审核题目列表
      required: [questions]
    handler:
      type: http
      method: POST
      url: "http://localhost:8000/api/exam/review/pre-scan"
      headers:
        Content-Type: application/json
      body:
        questions: "{{{questions}}}"
    output:
      type: object
      properties:
        total: {type: integer}
        flagged_count: {type: integer}
        flagged_questions:
          type: array
          items:
            type: object
            properties:
              question_id: {type: string}
              is_suspicious: {type: boolean}
              reasons: {type: array}
              suggestions: {type: array}
              confidence: {type: number}
        quality_stats:
          type: object
          properties:
            total_questions: {type: integer}
            passed_auto: {type: integer}
            flagged: {type: integer}
            needs_manual: {type: integer}

  exam_review_regenerate:
    name: exam_review_regenerate
    description: 要求AI重新生成某道题目
    parameters:
      type: object
      properties:
        original_question_id:
          type: string
          description: 原题目ID
        feedback:
          type: string
          description: 修改反馈
      required: [original_question_id, feedback]
    handler:
      type: http
      method: POST
      url: "http://localhost:8000/api/exam/review/regenerate"
      headers:
        Content-Type: application/json
      body:
        original_question_id: "{{{original_question_id}}}"
        feedback: "{{{feedback}}}"
    output:
      type: object
      properties:
        success: {type: boolean}
        new_question: {type: object}
        message: {type: string}
```

### 2-2.6 engine/balance_checker.py（化学方程式配平引擎）

```python
# hermes-skills/chemistry-exam/engine/balance_checker.py
"""
化学方程式配平检测引擎
基于 ChemAI chemical_balance.py 封装，供 Chem Skill 调用
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class BalanceResult:
    """配平检测结果"""
    is_balanced: bool
    left_elements: Dict[str, int]
    right_elements: Dict[str, int]
    message: str


class BalanceChecker:
    """
    化学方程式配平检测引擎
    信任红线：配平错误直接拒绝
    """

    def __init__(self):
        self._element_pattern = re.compile(r'^([A-Z][a-z]?)(\d*)$')

    def check_balance(self, equation: str) -> BalanceResult:
        """
        检测化学方程式是否配平

        Args:
            equation: 化学方程式字符串，如 "2H2 + O2 → 2H2O"

        Returns:
            BalanceResult: 配平检测结果
        """
        # 清理输入
        equation = equation.strip()
        equation = equation.replace(" ", "")

        # 解析方程式
        try:
            reactants_str, reactants, products_str, products = self._parse_equation(equation)
        except Exception as e:
            return BalanceResult(
                is_balanced=False,
                left_elements={},
                right_elements={},
                message=f"方程式解析失败: {str(e)}"
            )

        if not reactants or not products:
            return BalanceResult(
                is_balanced=False,
                left_elements={},
                right_elements={},
                message="方程式格式错误：无法识别反应物或产物"
            )

        # 统计元素
        left_elements = self._count_elements_in_list(reactants)
        right_elements = self._count_elements_in_list(products)

        # 检查是否配平
        is_balanced = left_elements == right_elements

        if is_balanced:
            message = "配平正确 ✓"
        else:
            # 生成详细错误信息
            all_elements = set(left_elements.keys()) | set(right_elements.keys())
            errors = []
            for elem in sorted(all_elements):
                left_count = left_elements.get(elem, 0)
                right_count = right_elements.get(elem, 0)
                if left_count != right_count:
                    errors.append(
                        f"{elem}: 反应物 {left_count}个 vs 产物 {right_count}个"
                    )
            message = f"配平错误: {'; '.join(errors)}"

        return BalanceResult(
            is_balanced=is_balanced,
            left_elements=left_elements,
            right_elements=right_elements,
            message=message
        )

    def _parse_equation(self, equation: str) -> Tuple[str, List[str], str, List[str]]:
        """
        解析化学方程式

        Returns:
            (反应物字符串, 反应物列表, 产物字符串, 产物列表)
        """
        # 确定分隔符
        if "→" in equation:
            parts = equation.split("→")
        elif "=" in equation:
            parts = equation.split("=")
        elif "->" in equation:
            parts = equation.split("->")
        else:
            raise ValueError("未识别方程式分隔符")

        if len(parts) != 2:
            raise ValueError("方程式格式错误")

        reactants_str = parts[0]
        products_str = parts[1]

        reactants = self._split_species(reactants_str)
        products = self._split_species(products_str)

        return reactants_str, reactants, products_str, products

    def _split_species(self, species_str: str) -> List[str]:
        """分割多个化学物种（用 + 分隔）"""
        result = []
        i = 0
        current = ""
        paren_depth = 0

        while i < len(species_str):
            char = species_str[i]

            if char == "(":
                paren_depth += 1
                current += char
            elif char == ")":
                paren_depth -= 1
                current += char
            elif char == "+" and paren_depth == 0:
                if current:
                    result.append(current)
                current = ""
            else:
                current += char

            i += 1

        if current:
            result.append(current)

        return result

    def _count_elements_in_list(self, species_list: List[str]) -> Dict[str, int]:
        """统计物种列表中各元素的总数量"""
        total: Dict[str, int] = {}
        for species in species_list:
            elements = self._count_elements(species)
            for elem, count in elements.items():
                total[elem] = total.get(elem, 0) + count
        return total

    def _count_elements(self, formula: str) -> Dict[str, int]:
        """
        统计化学式中各元素的原子数量
        处理: H2O, Ca(OH)2, Al2(SO4)3 等格式
        """
        elements: Dict[str, int] = {}

        # 处理系数
        match = re.match(r'^(\d+)(.+)$', formula)
        if match:
            coefficient = int(match.group(1))
            formula = match.group(2)
        else:
            coefficient = 1

        # 解析化学式
        i = 0
        while i < len(formula):
            if formula[i] == "(":
                # 处理括号
                i += 1
                paren_content = ""
                paren_depth = 1
                while i < len(formula) and paren_depth > 0:
                    if formula[i] == "(":
                        paren_depth += 1
                    elif formula[i] == ")":
                        paren_depth -= 1
                    paren_content += formula[i]
                    i += 1

                # 去掉末尾的 )
                paren_content = paren_content[:-1]

                # 获取括号后的数字
                num_str = ""
                while i < len(formula) and formula[i].isdigit():
                    num_str += formula[i]
                    i += 1
                multiplier = int(num_str) if num_str else 1

                # 递归统计括号内元素
                inner_elements = self._count_elements(paren_content)
                for elem, count in inner_elements.items():
                    elements[elem] = elements.get(elem, 0) + count * multiplier

            elif formula[i].isupper():
                # 元素符号开始
                elem = formula[i]
                i += 1

                # 可能的小写字母
                while i < len(formula) and formula[i].islower():
                    elem += formula[i]
                    i += 1

                # 数量
                num_str = ""
                while i < len(formula) and formula[i].isdigit():
                    num_str += formula[i]
                    i += 1
                count = int(num_str) if num_str else 1

                elements[elem] = elements.get(elem, 0) + count
            else:
                i += 1

        # 应用系数
        for elem in elements:
            elements[elem] *= coefficient

        return elements


# 全局实例
_checker: Optional[BalanceChecker] = None


def get_checker() -> BalanceChecker:
    """获取全局实例"""
    global _checker
    if _checker is None:
        _checker = BalanceChecker()
    return _checker


def check_equation_balance(equation: str) -> Dict:
    """
    供 Hermes Tool 调用的入口函数

    Args:
        equation: 化学方程式字符串

    Returns:
        符合 Tool Schema 的字典
    """
    checker = get_checker()
    result = checker.check_balance(equation)

    return {
        "is_balanced": result.is_balanced,
        "left_elements": result.left_elements,
        "right_elements": result.right_elements,
        "message": result.message
    }
```

### 2-2.7 handler.py（Tool 处理器）

```python
# hermes-skills/chemistry-exam/handler.py
"""
Chemistry Exam Skill - Tool Handler
处理 exam_* Tool 的实际调用逻辑
"""

import json
import logging
import base64
from typing import Dict, Any, List, Optional

import requests
from requests.exceptions import RequestException, Timeout

from engine.balance_checker import check_equation_balance

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chemistry-exam")

DEFAULT_API_BASE = "http://localhost:8000"
DEFAULT_TIMEOUT = 60


class ExamToolError(Exception):
    """出题工具异常"""
    pass


class ExamHandler:
    """出题 Tool 处理器"""

    def __init__(self, api_base: str = DEFAULT_API_BASE):
        self.api_base = api_base.rstrip("/")
        self.session = requests.Session()

    def _make_request(
        self,
        method: str,
        path: str,
        **kwargs
    ) -> Dict[str, Any]:
        """发送 HTTP 请求的通用方法"""
        url = f"{self.api_base}{path}"
        timeout = kwargs.pop("timeout", DEFAULT_TIMEOUT)

        try:
            response = self.session.request(
                method=method,
                url=url,
                timeout=timeout,
                **kwargs
            )
            response.raise_for_status()
            return response.json()
        except Timeout:
            raise ExamToolError(f"请求超时: {url}")
        except RequestException as e:
            raise ExamToolError(f"请求失败: {str(e)}")

    # ===== 出题 Tool 实现 =====

    async def exam_generate(
        self,
        knowledge_points: List[str],
        difficulty: str = "medium",
        quantity: int = 10
    ) -> Dict[str, Any]:
        """AI 生成题目"""
        logger.info(
            f"AI 生成题目: kps={knowledge_points}, "
            f"difficulty={difficulty}, quantity={quantity}"
        )

        return self._make_request(
            "POST",
            "/api/question/generate",
            json={
                "knowledge_points": knowledge_points,
                "difficulty": difficulty,
                "quantity": quantity
            },
            timeout=120  # 出题可能较慢
        )

    async def exam_audit(
        self,
        question_content: str,
        options: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """题目安全审核"""
        logger.info(f"审核题目: {question_content[:50]}...")

        payload = {"question_content": question_content}
        if options:
            payload["options"] = options

        return self._make_request(
            "POST",
            "/api/question/audit",
            json=payload
        )

    async def exam_balance_check(self, equation: str) -> Dict[str, Any]:
        """化学方程式配平检测"""
        logger.info(f"配平检测: {equation}")

        # 直接调用本地引擎
        return check_equation_balance(equation)

    # ===== 历史真题 Tool 实现 =====

    async def exam_search_historical(
        self,
        source: Optional[str] = None,
        year: Optional[int] = None,
        difficulty: Optional[str] = None,
        knowledge_point: Optional[str] = None,
        keyword: Optional[str] = None
    ) -> Dict[str, Any]:
        """检索历年真题"""
        params = {}
        if source:
            params["source"] = source
        if year:
            params["year"] = year
        if difficulty:
            params["difficulty"] = difficulty
        if knowledge_point:
            params["knowledge_point"] = knowledge_point
        if keyword:
            params["keyword"] = keyword

        logger.info(f"检索历年真题: {params}")

        return self._make_request(
            "GET",
            "/api/question/historical",
            params=params
        )

    async def exam_get_exam_sets(self) -> Dict[str, Any]:
        """获取真题集列表"""
        logger.info("获取真题集列表")

        return self._make_request("GET", "/api/question/exam-sets")

    async def exam_find_similar(
        self,
        knowledge_points: List[str],
        difficulty: str = "medium",
        limit: int = 5
    ) -> Dict[str, Any]:
        """查找相似题目"""
        logger.info(f"查找相似题目: kps={knowledge_points}")

        return self._make_request(
            "POST",
            "/api/question/similar",
            json={
                "knowledge_points": knowledge_points,
                "difficulty": difficulty,
                "limit": limit
            }
        )

    # ===== 导入 Tool 实现 =====

    async def exam_import_manual(
        self,
        source_name: str,
        year: int,
        questions: List[Dict],
        region: str = "老师导入"
    ) -> Dict[str, Any]:
        """手动导入题目"""
        logger.info(f"手动导入题目: source={source_name}, count={len(questions)}")

        return self._make_request(
            "POST",
            "/api/question/import",
            json={
                "source_name": source_name,
                "region": region,
                "year": year,
                "questions": questions
            }
        )

    async def exam_import_ocr(
        self,
        source_name: str,
        year: int,
        file_data: str,  # base64 编码
        region: str = "老师导入"
    ) -> Dict[str, Any]:
        """OCR 扫描导入题目"""
        logger.info(f"OCR 导入题目: source={source_name}")

        # 文件需要作为 form-data 上传，这里简化处理
        return self._make_request(
            "POST",
            "/api/question/import/ocr",
            data={
                "source_name": source_name,
                "region": region,
                "year": year,
            },
            files={"file": ("paper.jpg", base64.b64decode(file_data), "image/jpeg")}
        )

    # ===== 审核队列 Tool 实现 =====

    async def exam_review_pending(
        self,
        teacher_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取待审核题目"""
        params = {}
        if teacher_id:
            params["teacher_id"] = teacher_id

        logger.info(f"获取待审核题目: teacher_id={teacher_id}")

        return self._make_request(
            "GET",
            "/api/exam/review/pending",
            params=params
        )

    async def exam_review_submit(
        self,
        question_id: str,
        action: str,  # approve / modify / reject
        modified_content: Optional[str] = None,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """提交审核结果"""
        logger.info(f"提交审核结果: question_id={question_id}, action={action}")

        payload = {
            "question_id": question_id,
            "action": action
        }
        if modified_content:
            payload["modified_content"] = modified_content
        if reason:
            payload["reason"] = reason

        return self._make_request(
            "POST",
            "/api/exam/review/submit",
            json=payload
        )

    async def exam_review_pre_scan(
        self,
        questions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        ChemAI Agent 预审扫描

        对题目列表进行快速扫描，标记可疑题目
        """
        logger.info(f"Agent 预审扫描: {len(questions)} 道题目")

        # 使用 LLM 进行快速预审
        flagged_questions = []
        passed_auto = 0

        for q in questions:
            flags = []
            suggestions = []
            is_suspicious = False

            # 1. 检查化学方程式
            content = q.get("content", "")
            equations = self._extract_equations(content)

            for eq in equations:
                balance_result = check_equation_balance(eq)
                if not balance_result["is_balanced"]:
                    is_suspicious = True
                    flags.append("equation_imbalance")
                    suggestions.append(
                        f"化学方程式未配平: {eq} - {balance_result['message']}"
                    )

            # 2. 检查题目长度
            if len(content) > 500:
                flags.append("too_long")
                suggestions.append("题目过长，可能影响学生审题")

            # 3. 检查知识点
            kps = q.get("knowledge_points", [])
            if not kps or kps == ["待标注"]:
                flags.append("missing_knowledge_points")
                suggestions.append("知识点未标注")

            if is_suspicious:
                flagged_questions.append({
                    "question_id": q.get("question_id", ""),
                    "is_suspicious": True,
                    "reasons": flags,
                    "suggestions": suggestions,
                    "confidence": 0.85
                })
            else:
                passed_auto += 1

        return {
            "total": len(questions),
            "flagged_count": len(flagged_questions),
            "flagged_questions": flagged_questions,
            "quality_stats": {
                "total_questions": len(questions),
                "passed_auto": passed_auto,
                "flagged": len(flagged_questions),
                "needs_manual": len(questions) - passed_auto - len(flagged_questions)
            }
        }

    def _extract_equations(self, text: str) -> List[str]:
        """从文本中提取化学方程式"""
        import re
        # 匹配 → 或 = 分隔的方程式
        pattern = r'[A-Za-z0-9\(\)\[\]·°δ＋－\-\+\s→=]+[→=][A-Za-z0-9\(\)\[\]·°δ＋－\-\+\s→=]+'
        matches = re.findall(pattern, text)
        return [m.strip() for m in matches if '→' in m or '=' in m]

    async def exam_review_regenerate(
        self,
        original_question_id: str,
        feedback: str
    ) -> Dict[str, Any]:
        """要求重新生成题目"""
        logger.info(f"重新生成题目: original_id={original_question_id}")

        # 这里需要调用 exam_generate，但需要根据 feedback 调整
        # 简化处理：直接调用生成接口
        return self._make_request(
            "POST",
            "/api/exam/review/regenerate",
            json={
                "original_question_id": original_question_id,
                "feedback": feedback
            }
        )


# 全局 Handler 实例
_handler: Optional[ExamHandler] = None


def get_handler() -> ExamHandler:
    """获取全局 Handler 实例"""
    global _handler
    if _handler is None:
        _handler = ExamHandler()
    return _handler


# ===== Tool 入口函数（供 Hermes 调用） =====

async def exam_generate(
    knowledge_points: List[str],
    difficulty: str = "medium",
    quantity: int = 10
) -> Dict[str, Any]:
    return await get_handler().exam_generate(knowledge_points, difficulty, quantity)


async def exam_audit(
    question_content: str,
    options: Optional[List[str]] = None
) -> Dict[str, Any]:
    return await get_handler().exam_audit(question_content, options)


async def exam_balance_check(equation: str) -> Dict[str, Any]:
    return await get_handler().exam_balance_check(equation)


async def exam_search_historical(
    source: Optional[str] = None,
    year: Optional[int] = None,
    difficulty: Optional[str] = None,
    knowledge_point: Optional[str] = None,
    keyword: Optional[str] = None
) -> Dict[str, Any]:
    return await get_handler().exam_search_historical(
        source, year, difficulty, knowledge_point, keyword
    )


async def exam_get_exam_sets() -> Dict[str, Any]:
    return await get_handler().exam_get_exam_sets()


async def exam_find_similar(
    knowledge_points: List[str],
    difficulty: str = "medium",
    limit: int = 5
) -> Dict[str, Any]:
    return await get_handler().exam_find_similar(knowledge_points, difficulty, limit)


async def exam_import_manual(
    source_name: str,
    year: int,
    questions: List[Dict],
    region: str = "老师导入"
) -> Dict[str, Any]:
    return await get_handler().exam_import_manual(source_name, year, questions, region)


async def exam_import_ocr(
    source_name: str,
    year: int,
    file_data: str,
    region: str = "老师导入"
) -> Dict[str, Any]:
    return await get_handler().exam_import_ocr(source_name, year, file_data, region)


async def exam_review_pending(teacher_id: Optional[str] = None) -> Dict[str, Any]:
    return await get_handler().exam_review_pending(teacher_id)


async def exam_review_submit(
    question_id: str,
    action: str,
    modified_content: Optional[str] = None,
    reason: Optional[str] = None
) -> Dict[str, Any]:
    return await get_handler().exam_review_submit(
        question_id, action, modified_content, reason
    )


async def exam_review_pre_scan(questions: List[Dict[str, Any]]) -> Dict[str, Any]:
    return await get_handler().exam_review_pre_scan(questions)


async def exam_review_regenerate(
    original_question_id: str,
    feedback: str
) -> Dict[str, Any]:
    return await get_handler().exam_review_regenerate(original_question_id, feedback)
```

---

## Phase 2 实现检查清单

### chemistry-diagnosis Skill 交付物

- [ ] `SOUL.md` - Skill 指令文档
- [ ] `tools.yaml` - 7 个 Tool 定义
- [ ] `handler.py` - 7 个 Handler 实现
- [ ] `schemas/` - 数据模型
- [ ] `prompts/` - Prompt 模板
- [ ] `tests/` - 单元测试
- [ ] `requirements.txt` - 依赖声明
- [ ] 集成测试通过

### chemistry-exam Skill 交付物

- [ ] `SOUL.md` - Skill 指令文档（含人工审核机制）
- [ ] `tools.yaml` - 12 个 Tool 定义
- [ ] `handler.py` - 12 个 Handler 实现
- [ ] `engine/balance_checker.py` - 化学方程式配平引擎
- [ ] `schemas/` - 数据模型（含审核队列）
- [ ] `prompts/` - Prompt 模板
- [ ] `tests/` - 单元测试
- [ ] `requirements.txt` - 依赖声明
- [ ] 集成测试通过

---

*Phase 2 详细设计完成*

---

# Phase 3 详细设计：Hermes 记忆系统与消息网关集成

> 本章节为 Phase 3 执行提供完整的开发规范，包括记忆系统架构、消息网关集成、学生学情历史管理

---

## Phase 3-1: Hermes 记忆系统集成

### 3-1.1 记忆系统概述

ChemAI Agent 的记忆系统是其核心能力之一，支持：
- **FTS5 Session Search** - 跨会话全文搜索
- **LLM Summarization** - 自动摘要压缩
- **Honcho User Modeling** - 用户画像建模
- **Agent-Curated Memory** - Agent 策划的持久记忆

ChemAI 将利用这套记忆系统管理学生的学情历史，使 Agent 能够：
1. 跨会话记住学生的学习偏好和障碍类型
2. 记住历史诊断结果，避免重复诊断
3. 根据历史表现调整干预策略
4. 实现真正的个性化教学

### 3-1.2 学情记忆类型设计

```
┌─────────────────────────────────────────────────────────────────┐
│                    ChemAI 学情记忆存储结构                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  hermes-memory/                                                  │
│  ├── students/                    # 学生个人记忆                  │
│  │   ├── {student_id}/                                         │
│  │   │   ├── profile.md           # 学生画像（LLM摘要）           │
│  │   │   ├── barrier_history.md   # 障碍类型历史                  │
│  │   │   ├── weak_kps.md          # 薄弱知识点追踪                │
│  │   │   ├── practice_history.md   # 练习历史                     │
│  │   │   └── preferences.md        # 学习偏好                     │
│  │   │                                                      │
│  ├── classes/                    # 班级集体记忆                  │
│  │   ├── {class_id}/                                          │
│  │   │   ├── summary.md           # 班级学情摘要                  │
│  │   │   ├── common_barriers.md   # 班级共性障碍                  │
│  │   │   └── trends.md           # 学情趋势                      │
│  │   │                                                      │
│  ├── teachers/                   # 教师记忆                      │
│  │   ├── {teacher_id}/                                       │
│  │   │   ├── config.md           # 个性化配置                    │
│  │   │   └── teaching_style.md   # 教学风格偏好                  │
│  │   │                                                      │
│  └── sessions/                   # 会话历史（FTS5索引）           │
│      ├── {session_id}.json      # 会话记录                       │
│      └── search.db              # FTS5 全文搜索索引              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3-1.3 记忆数据模型

#### 学生画像 (profile.md)

```markdown
# 学生画像: {student_id}

## 基本信息
- 姓名: {student_name}
- 班级: {class_name}
- 年级: {grade}
- 注册时间: {created_at}

## 学习概况
- 障碍类型: {dominant_barrier}
- 障碍占比: 概念 {concept}% | 审题 {reading}% | 表述 {expression}%
- 整体掌握度: {mastery_level}%
- 最近活跃: {last_active}

## 学习特点
- 薄弱知识点: {weak_kps_list}
- 进步最快领域: {improved_area}
- 作业完成率: {completion_rate}%

## ChemAI Agent 观察
{agent_observations_from_conversations}

## 最近更新时间
{last_updated}
```

#### 障碍历史 (barrier_history.md)

```markdown
# 障碍类型追踪: {student_id}

## 历史记录

### {date} - 诊断 #{sequence}
- **诊断来源**: {source} (考试/练习/AI诊断)
- **障碍类型**: {barrier_type}
- **障碍占比**: 概念 {concept}% | 审题 {reading}% | 表述 {expression}%
- **薄弱知识点**: {weak_kps}
- **建议干预**: {intervention}
- **执行状态**: {status} (已推送给学生/需审核/未执行)

---

## 趋势分析
{barrier_trend_analysis_by_llm}
```

#### 薄弱知识点追踪 (weak_kps.md)

```markdown
# 薄弱知识点追踪: {student_id}

## 当前薄弱知识点 (按错误频率排序)

1. **{kp_name}** - 错误 {count} 次
   - 首次出错: {first_error_date}
   - 最近出错: {recent_error_date}
   - 相关题目: {related_questions}

2. **{kp_name}** - 错误 {count} 次
   ...

## 已掌握知识点
- ~~{kp_name}~~ (连续正确 {count} 次)

## 知识点关联图谱
{knowledge_graph_visualization}
```

### 3-1.4 记忆系统 Tool 设计

```yaml
# hermes-skills/chemistry-memory/tools.yaml

schema_version: "1.0"
name: chemistry-memory
description: ChemAI 学情历史记忆管理系统

tools:

  # ===== 学生记忆读写 =====

  memory_student_get:
    name: memory_student_get
    description: 获取学生的完整学情记忆
    parameters:
      type: object
      properties:
        student_id:
          type: string
          description: 学生ID
        memory_type:
          type: string
          description: 记忆类型
          enum: [profile, barrier_history, weak_kps, practice_history, all]
          default: all
      required: [student_id]
    handler:
      type: file
      path: "hermes-memory/students/{student_id}/{memory_type}.md"
    output:
      type: object
      properties:
        student_id: {type: string}
        memory_type: {type: string}
        content: {type: string}
        last_updated: {type: string}

  memory_student_update:
    name: memory_student_update
    description: 更新学生的学情记忆
    parameters:
      type: object
      properties:
        student_id:
          type: string
        memory_type:
          type: string
          enum: [profile, barrier_history, weak_kps, practice_history]
        content:
          type: string
          description: 记忆内容（Markdown格式）
        append:
          type: boolean
          description: 是否追加模式（true=追加，false=覆盖）
          default: false
      required: [student_id, memory_type, content]
    handler:
      type: file
      path: "hermes-memory/students/{student_id}/{memory_type}.md"
      mode: "{{{append}}}"  # append or write
    output:
      type: object
      properties:
        success: {type: boolean}
        student_id: {type: string}
        memory_type: {type: string}
        updated_at: {type: string}

  # ===== 班级记忆读写 =====

  memory_class_get:
    name: memory_class_get
    description: 获取班级的学情记忆
    parameters:
      type: object
      properties:
        class_id:
          type: string
        memory_type:
          type: string
          enum: [summary, common_barriers, trends, all]
          default: all
      required: [class_id]
    handler:
      type: file
      path: "hermes-memory/classes/{class_id}/{memory_type}.md"
    output:
      type: object
      properties:
        class_id: {type: string}
        memory_type: {type: string}
        content: {type: string}

  memory_class_update:
    name: memory_class_update
    description: 更新班级的学情记忆
    parameters:
      type: object
      properties:
        class_id:
          type: string
        memory_type:
          type: string
          enum: [summary, common_barriers, trends]
        content:
          type: string
        append:
          type: boolean
          default: false
      required: [class_id, memory_type, content]
    handler:
      type: file
      path: "hermes-memory/classes/{class_id}/{memory_type}.md"
      mode: "{{{append}}}"
    output:
      type: object
      properties:
        success: {type: boolean}
        class_id: {type: string}
        updated_at: {type: string}

  # ===== FTS5 搜索 =====

  memory_search:
    name: memory_search
    description: 跨会话搜索学情历史（FTS5全文搜索）
    parameters:
      type: object
      properties:
        query:
          type: string
          description: 搜索关键词
        search_type:
          type: string
          description: 搜索范围
          enum: [student, class, teacher, all]
          default: all
        student_id:
          type: string
          description: 指定学生ID（可选）
        limit:
          type: integer
          default: 10
      required: [query]
    handler:
      type: search
      engine: fts5
      index_path: "hermes-memory/sessions/search.db"
    output:
      type: object
      properties:
        query: {type: string}
        results:
          type: array
          items:
            type: object
            properties:
              memory_type: {type: string}
              entity_id: {type: string}
              snippet: {type: string}
              score: {type: number}
              last_updated: {type: string}

  # ===== LLM 摘要生成 =====

  memory_summarize:
    name: memory_summarize
    description: 对学生的历史数据进行 LLM 摘要，更新学生画像
    parameters:
      type: object
      properties:
        student_id:
          type: string
          description: 学生ID
        force_refresh:
          type: boolean
          description: 强制刷新（即使未过期）
          default: false
      required: [student_id]
    handler:
      type: llm
      model: "{{{LLM_MODEL}}}"
    output:
      type: object
      properties:
        success: {type: boolean}
        student_id: {type: string}
        summary_generated: {type: string}
        key_insights: {type: array}
        recommendations: {type: array}
        next_review_date: {type: string}

  # ===== 记忆统计分析 =====

  memory_stats:
    name: memory_stats
    description: 获取记忆系统的统计信息
    parameters:
      type: object
      properties: {}
    handler:
      type: stats
    output:
      type: object
      properties:
        total_students: {type: integer}
        total_classes: {type: integer}
        total_sessions: {type: integer}
        storage_size_mb: {type: number}
        oldest_memory: {type: string}
        newest_memory: {type: string}
```

### 3-1.5 记忆更新触发机制

```python
# hermes-skills/chemistry-memory/memory_updater.py
"""
ChemAI 记忆自动更新触发器
在关键事件发生时自动更新记忆
"""

from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger("chemistry-memory")


class MemoryUpdater:
    """记忆更新器 - 响应关键事件自动更新记忆"""

    # 触发事件类型
    EVENT_EXAM_COMPLETED = "exam_completed"      # 考试完成
    EVENT_DIAGNOSIS_COMPLETED = "diagnosis_completed"  # 诊断完成
    EVENT_PRACTICE_COMPLETED = "practice_completed"    # 练习完成
    EVENT_LEARNING_PLAN_APPLIED = "learning_plan_applied"  # 学习计划应用
    EVENT_STUDENT_ACTIVE = "student_active"      # 学生活跃

    async def on_exam_completed(
        self,
        student_id: str,
        exam_record_id: str,
        score: float,
        correct_count: int,
        total_count: int
    ) -> Dict[str, Any]:
        """
        考试完成事件
        自动更新: practice_history.md
        """
        logger.info(f"考试完成事件: student={student_id}, exam={exam_record_id}")

        # 构建历史记录条目
        entry = f"""
### {datetime.now().strftime('%Y-%m-%d')} - 考试 {exam_record_id}
- **得分率**: {score}%
- **正确率**: {correct_count}/{total_count}
- **考试ID**: {exam_record_id}
"""

        # 追加到练习历史
        await self._append_memory(
            entity_type="student",
            entity_id=student_id,
            memory_type="practice_history",
            content=entry
        )

        # 触发画像更新检查
        await self._check_profile_refresh(student_id)

        return {"success": True, "event": self.EVENT_EXAM_COMPLETED}

    async def on_diagnosis_completed(
        self,
        student_id: str,
        barrier_type: Dict[str, float],
        dominant_barrier: str,
        weak_kps: list
    ) -> Dict[str, Any]:
        """
        诊断完成事件
        自动更新: barrier_history.md, weak_kps.md, profile.md
        """
        logger.info(f"诊断完成事件: student={student_id}, barrier={dominant_barrier}")

        # 更新障碍历史
        barrier_entry = f"""
### {datetime.now().strftime('%Y-%m-%d')} - 诊断记录
- **障碍类型**: {dominant_barrier}
- **障碍占比**: 概念 {barrier_type.get('concept', 0)*100:.0f}% | 审题 {barrier_type.get('reading', 0)*100:.0f}% | 表述 {barrier_type.get('expression', 0)*100:.0f}%
- **薄弱知识点**: {', '.join(weak_kps)}
"""

        await self._append_memory(
            entity_type="student",
            entity_id=student_id,
            memory_type="barrier_history",
            content=barrier_entry
        )

        # 更新薄弱知识点
        kp_entry = self._format_kp_entry(weak_kps)
        await self._overwrite_memory(
            entity_type="student",
            entity_id=student_id,
            memory_type="weak_kps",
            content=kp_entry
        )

        # 更新画像摘要
        await self._refresh_profile(student_id)

        return {"success": True, "event": self.EVENT_DIAGNOSIS_COMPLETED}

    async def on_learning_plan_applied(
        self,
        student_id: str,
        plan_id: str,
        plan_summary: str
    ) -> Dict[str, Any]:
        """
        学习计划应用事件
        自动更新: profile.md
        """
        logger.info(f"学习计划应用: student={student_id}, plan={plan_id}")

        entry = f"""
### {datetime.now().strftime('%Y-%m-%d')} - 学习计划
- **计划ID**: {plan_id}
- **计划摘要**: {plan_summary}
- **状态**: 已推送给学生
"""

        await self._append_memory(
            entity_type="student",
            entity_id=student_id,
            memory_type="practice_history",
            content=entry
        )

        return {"success": True, "event": self.EVENT_LEARNING_PLAN_APPLIED}

    async def on_student_active(
        self,
        student_id: str,
        activity_type: str,
        details: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        学生活跃事件
        更新最后活跃时间
        """
        logger.info(f"学生活跃: student={student_id}, type={activity_type}")

        # 更新画像中的活跃时间
        await self._update_profile_field(
            student_id=student_id,
            field="最近活跃",
            value=datetime.now().strftime("%Y-%m-%d %H:%M")
        )

        return {"success": True, "event": self.EVENT_STUDENT_ACTIVE}

    # ===== 内部方法 =====

    async def _append_memory(
        self,
        entity_type: str,
        entity_id: str,
        memory_type: str,
        content: str
    ) -> None:
        """追加记忆内容"""
        # 实现: 读取现有内容，追加新内容，写回
        pass

    async def _overwrite_memory(
        self,
        entity_type: str,
        entity_id: str,
        memory_type: str,
        content: str
    ) -> None:
        """覆盖记忆内容"""
        pass

    async def _check_profile_refresh(self, student_id: str) -> None:
        """检查是否需要刷新画像"""
        # 实现: 读取profile，检查更新时间，决定是否刷新
        pass

    async def _refresh_profile(self, student_id: str) -> None:
        """刷新学生画像"""
        # 实现: 收集所有记忆，调用LLM生成摘要，更新profile.md
        pass

    async def _update_profile_field(
        self,
        student_id: str,
        field: str,
        value: str
    ) -> None:
        """更新画像中的特定字段"""
        pass

    def _format_kp_entry(self, weak_kps: list) -> str:
        """格式化知识点条目"""
        content = "# 薄弱知识点追踪\n\n"
        content += "## 当前薄弱知识点 (按错误频率排序)\n\n"

        for i, kp in enumerate(weak_kps, 1):
            content += f"{i}. **{kp}** - 错误次数待更新\n"
            content += f"   - 首次出错: 待记录\n"
            content += f"   - 最近出错: {datetime.now().strftime('%Y-%m-%d')}\n\n"

        return content
```

---

## Phase 3-2: 消息网关集成

### 3-2.1 消息网关概述

ChemAI Agent 支持多种消息网关：
- **Telegram** - 即时通讯
- **Discord** - 社区/班级群
- **Slack** - 企业协作
- **WhatsApp** - 社交（海外）
- **Signal** - 安全通讯
- **Email** - 邮件通知

ChemAI 主要需要集成：
1. **Discord/Slack** - 班级群作业/报告推送
2. **Telegram** - 家校通知
3. **Email** - 正式报告发送

### 3-2.2 推送内容设计

#### 推送类型矩阵

| 推送类型 | 目标用户 | 推荐渠道 | 内容长度 | 紧急程度 |
|---------|---------|---------|---------|---------|
| 作业布置 | 学生 | Discord/Slack 群 | 短摘要 + 链接 | 普通 |
| 错题报告 | 学生/家长 | Telegram/Email | 完整报告 | 普通 |
| 学习计划 | 学生/家长 | Telegram/Email | 详细计划 | 普通 |
| 班级通知 | 全员 | Discord/Slack 群 | 短通知 | 普通/紧急 |
| 成绩预警 | 家长 | Email | 简短 + 建议 | 紧急 |
| 日常鼓励 | 学生 | Telegram | 简短 | 普通 |

#### 推送模板

```yaml
# hermes-skills/chemistry-notification/templates/

templates:

  # ===== 作业布置 =====
  assignment_notification:
    title: "📚 新作业布置"
    template: |
      【{{class_name}}】{{exam_name}}

      知识点: {{knowledge_points}}
      题目数量: {{question_count}} 道
      截止时间: {{deadline}}

      点击开始练习: {{practice_link}}

      — ChemAI 智能教学助手

    discord_format: |
      **📚 新作业布置**
      **班级**: {{class_name}}
      **作业**: {{exam_name}}
      **知识点**: {{knowledge_points}}
      **题量**: {{question_count}} 道
      **截止**: {{deadline}}

      👉 [开始练习]({{practice_link}})

    slack_format: |
      🎓 *{{class_name}} - {{exam_name}}*

      知识点: {{knowledge_points}}
      题量: {{question_count}}道 | 截止: {{deadline}}

      <{{practice_link}}|开始练习>

    telegram_format: |
      📚 *作业通知*

      班级: {{class_name}}
      作业: {{exam_name}}
      知识点: {{knowledge_points}}
      截止: {{deadline}}

      [点击开始练习]({{practice_link}})

  # ===== 错题报告 =====
  error_report:
    title: "📋 错题报告已生成"
    template: |
      【{{student_name}}】{{exam_name}} 错题报告

      得分率: {{score}}%
      班级平均: {{class_avg}}%

      薄弱知识点:
      {{#each weak_kps}}
      {{@index}}. {{this.name}} (错误{{this.count}}次)
      {{/each}}

      查看完整报告: {{report_link}}

      — ChemAI 智能教学助手

    email_format:
      subject: "{{student_name}} - {{exam_name}} 错题报告"
      body: |
        家长您好，

        {{student_name}} 的 {{exam_name}} 错题报告已生成。

        得分率: {{score}}%
        班级平均: {{class_avg}}%

        薄弱知识点:
        {{#each weak_kps}}
        {{@index}}. {{this.name}} (错误{{this.count}}次)
        {{/each}}

        [查看完整报告]({{report_link}})

        ChemAI 智能教学助手

  # ===== 学习计划 =====
  learning_plan:
    title: "📖 个性化学习计划"
    template: |
      【{{student_name}}】个性化学习计划

      计划周期: {{plan_period}}
      主要障碍: {{barrier_type}}
      薄弱知识点: {{weak_kps}}

      每日学习任务:
      {{#each daily_tasks}}
      Day {{@index}}: {{this}}
      {{/each}}

      查看完整计划: {{plan_link}}

      — ChemAI 智能教学助手

    telegram_format: |
      📖 *个性化学习计划*

      周期: {{plan_period}}
      障碍: {{barrier_type}}

      {{#each daily_tasks}}
      {{@index}}. {{this}}
      {{/each}}

      [查看完整计划]({{plan_link}})

  # ===== 成绩预警 =====
  score_alert:
    title: "⚠️ 成绩预警通知"
    template: |
      【{{student_name}}】成绩预警

      考试: {{exam_name}}
      得分率: {{score}}%
      较上次: {{change}}%

      主要问题:
      {{#each issues}}
      - {{this}}
      {{/each}}

      建议: {{suggestion}}

      — ChemAI 智能教学助手

    email_format:
      subject: "⚠️ {{student_name}} 成绩预警 - {{exam_name}}"
      body: |
        家长您好，

        {{student_name}} 在最近的 {{exam_name}} 中得分率仅为 {{score}}%，
        较上次考试下降了 {{change}}%。

        主要问题:
        {{#each issues}}
        - {{this}}
        {{/each}}

        建议措施:
        {{suggestion}}

        建议您与孩子一起分析原因，制定改进计划。

        ChemAI 智能教学助手

  # ===== 日常鼓励 =====
  daily_encouragement:
    title: "💪 每日鼓励"
    telegram_format: |
      💪 *{{student_name}}*

      {{encouragement_message}}

      今日任务: {{today_task}}

      [完成练习]({{practice_link}})

    frequency: daily
    best_time: "19:00"  # 晚间推送效果最佳
```

### 3-2.3 消息网关 Tool 设计

```yaml
# hermes-skills/chemistry-notification/tools.yaml

schema_version: "1.0"
name: chemistry-notification
description: ChemAI 消息通知推送系统

tools:

  # ===== 消息发送 =====

  notification_send:
    name: notification_send
    description: 发送通用通知到指定渠道
    parameters:
      type: object
      properties:
        channel:
          type: string
          description: 发送渠道
          enum: [discord, slack, telegram, email]
        recipient_id:
          type: string
          description: 接收者ID（群ID/用户ID/邮箱）
        template_name:
          type: string
          description: 消息模板名称
        template_data:
          type: object
          description: 模板变量数据
        priority:
          type: string
          description: 优先级
          enum: [low, normal, high, urgent]
          default: normal
      required: [channel, recipient_id, template_name, template_data]
    handler:
      type: gateway
      channel: "{{{channel}}}"
    output:
      type: object
      properties:
        success: {type: boolean}
        message_id: {type: string}
        channel: {type: string}
        sent_at: {type: string}

  notification_send_class:
    name: notification_send_class
    description: 向班级群发送通知
    parameters:
      type: object
      properties:
        class_id:
          type: string
          description: 班级ID
        template_name:
          type: string
          description: 消息模板名称
        template_data:
          type: object
        exclude_students:
          type: array
          items: {type: string}
          description: 需要排除的学生ID
      required: [class_id, template_name, template_data]
    handler:
      type: gateway
      channel: class_default
    output:
      type: object
      properties:
        success: {type: boolean}
        total_recipients: {type: integer}
        sent_count: {type: integer}
        failed_count: {type: integer}
        failed_recipients: {type: array}

  notification_send_parents:
    name: notification_send_parents
    description: 发送通知给学生家长
    parameters:
      type: object
      properties:
        student_id:
          type: string
          description: 学生ID
        template_name:
          type: string
        template_data:
          type: object
        channel:
          type: string
          enum: [email, telegram, sms]
          default: email
      required: [student_id, template_name, template_data]
    handler:
      type: gateway
      channel: "{{{channel}}}"
    output:
      type: object
      properties:
        success: {type: boolean}
        recipient_parent: {type: string}
        sent_at: {type: string}

  # ===== 作业推送 =====

  notification_assignment:
    name: notification_assignment
    description: 布置作业并通知学生
    parameters:
      type: object
      properties:
        class_id:
          type: string
        practice_id:
          type: string
          description: 练习ID
        notification_channel:
          type: string
          enum: [discord, slack, telegram, all]
          default: all
      required: [class_id, practice_id]
    handler:
      type: workflow
      steps:
        - get_practice_info
        - send_student_notification
        - send_parent_notification
    output:
      type: object
      properties:
        success: {type: boolean}
        practice_id: {type: string}
        student_notified: {type: integer}
        parent_notified: {type: integer}

  # ===== 报告推送 =====

  notification_report:
    name: notification_report
    description: 发送错题报告给学生和家长
    parameters:
      type: object
      properties:
        exam_record_id:
          type: string
        student_ids:
          type: array
          items: {type: string}
          description: 学生ID列表（空=全班）
        send_to_parents:
          type: boolean
          default: true
        notification_channel:
          type: string
          enum: [discord, slack, telegram, email]
          default: telegram
      required: [exam_record_id]
    handler:
      type: workflow
      steps:
        - get_report_info
        - generate_reports
        - send_student_reports
        - send_parent_reports
    output:
      type: object
      properties:
        success: {type: boolean}
        exam_record_id: {type: string}
        student_reports_sent: {type: integer}
        parent_reports_sent: {type: integer}

  # ===== 批量操作 =====

  notification_batch:
    name: notification_batch
    description: 批量发送通知
    parameters:
      type: object
      properties:
        notifications:
          type: array
          items:
            type: object
            properties:
              channel: {type: string}
              recipient_id: {type: string}
              template_name: {type: string}
              template_data: {type: object}
      required: [notifications]
    handler:
      type: gateway
      mode: batch
    output:
      type: object
      properties:
        total: {type: integer}
        success_count: {type: integer}
        failed_count: {type: integer}
        results: {type: array}

  # ===== 消息模板管理 =====

  notification_template_list:
    name: notification_template_list
    description: 列出所有可用的消息模板
    parameters:
      type: object
      properties: {}
    handler:
      type: template
      action: list
    output:
      type: object
      properties:
        templates:
          type: array
          items:
            type: object
            properties:
              name: {type: string}
              title: {type: string}
              channels: {type: array}
              variables: {type: array}

  notification_template_preview:
    name: notification_template_preview
    description: 预览消息模板渲染结果
    parameters:
      type: object
      properties:
        template_name:
          type: string
        template_data:
          type: object
        channel:
          type: string
          enum: [discord, slack, telegram, email]
          default: telegram
      required: [template_name, template_data]
    handler:
      type: template
      action: preview
    output:
      type: object
      properties:
        template_name: {type: string}
        channel: {type: string}
        rendered_content: {type: string}
```

### 3-2.4 消息网关配置

```yaml
# chemai-backend/config/gateway.yaml

gateways:
  # ===== Discord 配置 =====
  discord:
    enabled: true
    bot_token: "${DISCORD_BOT_TOKEN}"
    default_channel_id: "${DISCORD_DEFAULT_CHANNEL}"

    # 班级群映射
    class_channels:
      "class_001": "${DISCORD_CLASS_001_CHANNEL}"
      "class_002": "${DISCORD_CLASS_002_CHANNEL}"

    # 消息格式
    format:
      max_length: 2000  # Discord 消息长度限制
      use_embeds: true
      embed_color: 0x3498db  # 蓝色

    # Rate Limiting
    rate_limit:
      messages_per_second: 5
      burst: 10

  # ===== Slack 配置 =====
  slack:
    enabled: true
    bot_token: "${SLACK_BOT_TOKEN}"
    default_channel: "${SLACK_DEFAULT_CHANNEL}"

    # 班级群映射
    class_channels:
      "class_001": "${SLACK_CLASS_001_CHANNEL}"

    # 消息格式
    format:
      use_blocks: true
      unfurl_links: false

    # Rate Limiting
    rate_limit:
      messages_per_second: 10

  # ===== Telegram 配置 =====
  telegram:
    enabled: true
    bot_token: "${TELEGRAM_BOT_TOKEN}"

    # 用户映射 (student_id -> telegram_chat_id)
    user_channels:
      "student_001": "${TELEGRAM_STUDENT_001}"

    # 消息格式
    format:
      parse_mode: "Markdown"
      disable_web_page_preview: true

    # 消息队列
    queue:
      max_size: 100
      retry_attempts: 3

  # ===== Email 配置 =====
  email:
    enabled: true
    smtp_host: "${SMTP_HOST}"
    smtp_port: 587
    smtp_user: "${SMTP_USER}"
    smtp_password: "${SMTP_PASSWORD}"
    from_address: "chemai@school.edu"
    from_name: "ChemAI 智能教学助手"

    # 家长邮箱映射 (student_id -> parent_email)
    parent_emails:
      "student_001": "${PARENT_EMAIL_001}"

    # 邮件模板
    templates:
      error_report: "templates/email/error_report.html"
      learning_plan: "templates/email/learning_plan.html"
      score_alert: "templates/email/score_alert.html"
```

### 3-2.5 推送工作流设计

```python
# hermes-skills/chemistry-notification/workflows.py
"""
ChemAI 消息推送工作流
定义复杂推送场景的自动化流程
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger("chemistry-notification")


class NotificationWorkflow(Enum):
    """推送工作流类型"""
    ASSIGNMENT = "assignment"           # 作业布置
    ERROR_REPORT = "error_report"        # 错题报告
    LEARNING_PLAN = "learning_plan"     # 学习计划
    SCORE_ALERT = "score_alert"         # 成绩预警
    DAILY_ENCODOURAGEMENT = "daily_encouragement"  # 日常鼓励


@dataclass
class WorkflowResult:
    """工作流执行结果"""
    workflow: str
    success: bool
    total_steps: int
    completed_steps: int
    failed_steps: List[str]
    outputs: Dict[str, Any]


class NotificationWorkflowEngine:
    """推送工作流引擎"""

    def __init__(self, gateway_handler, memory_handler):
        self.gateway = gateway_handler
        self.memory = memory_handler

    async def run_assignment_workflow(
        self,
        class_id: str,
        practice_id: str,
        notify_parents: bool = False
    ) -> WorkflowResult:
        """
        作业布置工作流

        步骤:
        1. 获取练习信息
        2. 发送学生通知
        3. 发送家长通知（可选）
        4. 更新记忆
        """
        logger.info(f"执行作业布置工作流: class={class_id}, practice={practice_id}")

        steps_completed = []
        steps_failed = []
        outputs = {}

        # Step 1: 获取练习信息
        try:
            practice_info = await self._get_practice_info(practice_id)
            outputs["practice_info"] = practice_info
            steps_completed.append("get_practice_info")
        except Exception as e:
            steps_failed.append(f"get_practice_info: {str(e)}")
            return WorkflowResult(
                workflow="assignment",
                success=False,
                total_steps=4,
                completed_steps=len(steps_completed),
                failed_steps=steps_failed,
                outputs=outputs
            )

        # Step 2: 发送学生通知
        try:
            student_result = await self.gateway.notification_send_class(
                class_id=class_id,
                template_name="assignment_notification",
                template_data={
                    "class_name": practice_info["class_name"],
                    "exam_name": practice_info["name"],
                    "knowledge_points": ", ".join(practice_info["knowledge_points"]),
                    "question_count": practice_info["question_count"],
                    "deadline": practice_info.get("deadline", "待定"),
                    "practice_link": f"https://chemai.app/practice/{practice_id}"
                }
            )
            outputs["student_notification"] = student_result
            steps_completed.append("send_student_notification")
        except Exception as e:
            steps_failed.append(f"send_student_notification: {str(e)}")

        # Step 3: 发送家长通知（可选）
        if notify_parents:
            try:
                parent_result = await self._notify_parents_of_assignment(
                    class_id, practice_info
                )
                outputs["parent_notification"] = parent_result
                steps_completed.append("send_parent_notification")
            except Exception as e:
                steps_failed.append(f"send_parent_notification: {str(e)}")

        # Step 4: 更新记忆
        try:
            await self._update_memory_after_assignment(class_id, practice_id)
            steps_completed.append("update_memory")
        except Exception as e:
            steps_failed.append(f"update_memory: {str(e)}")

        return WorkflowResult(
            workflow="assignment",
            success=len(steps_failed) == 0,
            total_steps=4,
            completed_steps=len(steps_completed),
            failed_steps=steps_failed,
            outputs=outputs
        )

    async def run_error_report_workflow(
        self,
        exam_record_id: str,
        student_ids: Optional[List[str]] = None,
        send_to_parents: bool = True
    ) -> WorkflowResult:
        """
        错题报告工作流

        步骤:
        1. 获取报告信息
        2. 生成/获取报告数据
        3. 发送学生报告
        4. 发送家长报告（可选）
        5. 更新记忆
        """
        logger.info(f"执行错题报告工作流: exam={exam_record_id}")

        steps_completed = []
        steps_failed = []
        outputs = {}

        # Step 1: 获取报告信息
        try:
            report_info = await self._get_report_info(exam_record_id)
            outputs["report_info"] = report_info
            steps_completed.append("get_report_info")
        except Exception as e:
            steps_failed.append(f"get_report_info: {str(e)}")
            return WorkflowResult(
                workflow="error_report",
                success=False,
                total_steps=5,
                completed_steps=len(steps_completed),
                failed_steps=steps_failed,
                outputs=outputs
            )

        # Step 2: 获取班级学生列表
        if not student_ids:
            student_ids = await self._get_class_students(report_info["class_id"])

        # Step 3: 发送学生报告
        student_reports_sent = 0
        for student_id in student_ids:
            try:
                student_report = await self._get_student_report(exam_record_id, student_id)
                await self.gateway.notification_send(
                    channel="telegram",
                    recipient_id=await self._get_student_channel(student_id),
                    template_name="error_report",
                    template_data={
                        "student_name": student_report["student_name"],
                        "exam_name": report_info["exam_name"],
                        "score": student_report["score"],
                        "class_avg": report_info["class_avg"],
                        "weak_kps": student_report["weak_kps"],
                        "report_link": f"https://chemai.app/report/{exam_record_id}/{student_id}"
                    }
                )
                student_reports_sent += 1
            except Exception as e:
                logger.error(f"发送学生报告失败: student={student_id}, error={str(e)}")

        outputs["student_reports_sent"] = student_reports_sent
        steps_completed.append("send_student_reports")

        # Step 4: 发送家长报告
        parent_reports_sent = 0
        if send_to_parents:
            for student_id in student_ids:
                try:
                    parent_email = await self._get_parent_email(student_id)
                    if parent_email:
                        await self.gateway.notification_send(
                            channel="email",
                            recipient_id=parent_email,
                            template_name="error_report",
                            template_data=outputs["student_reports"].get(student_id, {})
                        )
                        parent_reports_sent += 1
                except Exception as e:
                    logger.error(f"发送家长报告失败: student={student_id}, error={str(e)}")

        outputs["parent_reports_sent"] = parent_reports_sent
        steps_completed.append("send_parent_reports")

        # Step 5: 更新记忆
        try:
            for student_id in student_ids:
                await self.memory.on_student_active(
                    student_id=student_id,
                    activity_type="report_received",
                    details=f"错题报告: {exam_record_id}"
                )
            steps_completed.append("update_memory")
        except Exception as e:
            steps_failed.append(f"update_memory: {str(e)}")

        return WorkflowResult(
            workflow="error_report",
            success=len(steps_failed) == 0,
            total_steps=5,
            completed_steps=len(steps_completed),
            failed_steps=steps_failed,
            outputs=outputs
        )

    # ===== 辅助方法 =====

    async def _get_practice_info(self, practice_id: str) -> Dict[str, Any]:
        """获取练习信息"""
        # TODO: 调用 ChemAI API 获取练习详情
        pass

    async def _get_report_info(self, exam_record_id: str) -> Dict[str, Any]:
        """获取报告信息"""
        # TODO: 调用 ChemAI API 获取报告摘要
        pass

    async def _get_student_report(
        self,
        exam_record_id: str,
        student_id: str
    ) -> Dict[str, Any]:
        """获取学生报告"""
        # TODO: 调用 ChemAI API 获取学生报告
        pass

    async def _get_class_students(self, class_id: str) -> List[str]:
        """获取班级学生列表"""
        # TODO: 调用 ChemAI API 获取班级学生
        pass

    async def _get_student_channel(self, student_id: str) -> str:
        """获取学生的通知渠道ID"""
        # TODO: 从配置或数据库获取
        pass

    async def _get_parent_email(self, student_id: str) -> Optional[str]:
        """获取家长邮箱"""
        # TODO: 从数据库获取
        pass

    async def _notify_parents_of_assignment(
        self,
        class_id: str,
        practice_info: Dict
    ) -> Dict[str, Any]:
        """通知家长作业"""
        # TODO: 批量发送家长通知
        pass

    async def _update_memory_after_assignment(
        self,
        class_id: str,
        practice_id: str
    ) -> None:
        """更新记忆"""
        # TODO: 更新班级记忆
        pass
```

---

## Phase 3-3: 数据库改动

### 3-3.1 新增表

```sql
-- 学生通知渠道表
CREATE TABLE notification_channels (
    channel_id VARCHAR(64) PRIMARY KEY,
    student_id VARCHAR(64) NOT NULL,
    channel_type ENUM('discord', 'slack', 'telegram', 'email', 'sms') NOT NULL,
    channel_value VARCHAR(256) NOT NULL,  -- webhook URL / chat_id / email
    is_active BOOLEAN DEFAULT TRUE,
    is_primary BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT NOW(),
    updated_at DATETIME DEFAULT NOW(),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

-- 班级通知配置表
CREATE TABLE class_notification_config (
    config_id VARCHAR(64) PRIMARY KEY,
    class_id VARCHAR(64) NOT NULL,
    notification_type ENUM('assignment', 'report', 'alert', 'daily') NOT NULL,
    channel_type ENUM('discord', 'slack', 'telegram') NOT NULL,
    channel_id VARCHAR(256) NOT NULL,  -- 群ID / webhook
    is_enabled BOOLEAN DEFAULT TRUE,
    notify_parents BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT NOW(),
    updated_at DATETIME DEFAULT NOW(),
    FOREIGN KEY (class_id) REFERENCES classes(class_id)
);

-- 推送日志表
CREATE TABLE notification_logs (
    log_id VARCHAR(64) PRIMARY KEY,
    notification_type VARCHAR(64) NOT NULL,
    channel_type VARCHAR(32) NOT NULL,
    recipient_id VARCHAR(64) NOT NULL,
    recipient_type ENUM('student', 'parent', 'class') NOT NULL,
    template_name VARCHAR(128),
    title VARCHAR(256),
    content TEXT,
    status ENUM('pending', 'sent', 'failed', 'delivered') DEFAULT 'pending',
    sent_at DATETIME,
    delivered_at DATETIME,
    error_message TEXT,
    created_at DATETIME DEFAULT NOW()
);

-- 推送模板表
CREATE TABLE notification_templates (
    template_id VARCHAR(64) PRIMARY KEY,
    template_name VARCHAR(128) UNIQUE NOT NULL,
    title_template VARCHAR(256),
    content_template TEXT NOT NULL,
    discord_format TEXT,
    slack_format TEXT,
    telegram_format TEXT,
    email_subject VARCHAR(256),
    email_format TEXT,
    variables JSON,  -- ['student_name', 'score', 'weak_kps', ...]
    created_at DATETIME DEFAULT NOW(),
    updated_at DATETIME DEFAULT NOW()
);
```

### 3-3.2 现有表改动

```sql
-- Student 表增加通知字段
ALTER TABLE students ADD COLUMN notification_preferences JSON;
-- {"discord": true, "telegram": true, "email": false, "daily_encouragement": true}

-- Class 表增加通知配置
ALTER TABLE classes ADD COLUMN notification_config JSON;
-- {"assignment_channel": "discord", "report_channel": "telegram"}
```

---

## Phase 3-4: 实现检查清单

### 3-4.1 Hermes 记忆系统交付物

- [ ] `hermes-memory/` - 记忆存储目录结构
- [ ] `chemistry-memory/SOUL.md` - Skill 指令
- [ ] `chemistry-memory/tools.yaml` - 8 个 Tool 定义
- [ ] `chemistry-memory/handler.py` - Handler 实现
- [ ] `chemistry-memory/memory_updater.py` - 自动更新触发器
- [ ] `chemistry-memory/profiles/` - 学生画像模板
- [ ] 记忆 FTS5 索引配置
- [ ] LLM 摘要生成集成
- [ ] 集成测试通过

### 3-4.2 消息网关交付物

- [ ] `chemistry-notification/SOUL.md` - Skill 指令
- [ ] `chemistry-notification/tools.yaml` - 8 个 Tool 定义
- [ ] `chemistry-notification/handler.py` - Handler 实现
- [ ] `chemistry-notification/workflows.py` - 推送工作流
- [ ] `chemistry-notification/templates/` - 消息模板（YAML）
- [ ] `chemai-backend/config/gateway.yaml` - 网关配置
- [ ] Discord 网关集成
- [ ] Slack 网关集成
- [ ] Telegram 网关集成
- [ ] Email 网关集成
- [ ] 推送日志系统
- [ ] 集成测试通过

### 3-4.3 数据库改动交付物

- [ ] `notification_channels` 表
- [ ] `class_notification_config` 表
- [ ] `notification_logs` 表
- [ ] `notification_templates` 表
- [ ] Student/Class 表改动
- [ ] 数据库迁移脚本
- [ ] 验证测试通过

---

*Phase 3 详细设计完成*

---

# Phase 4 详细设计：自改进循环 — Agent 从出题结果中学习

> 本章节为 Phase 4 执行提供完整的开发规范，包括学习循环架构、质量追踪体系、策略调整机制

---

## Phase 4-1: 自改进循环概述

### 4-1.1 什么是自改进循环

自改进循环是让 ChemAI Agent 能够从历史数据中学习，自动优化出题策略的机制：

```
┌─────────────────────────────────────────────────────────────────┐
│                      自改进循环 (Self-Improving Loop)           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐                                                │
│  │  出题请求   │ ← 老师发起出题请求                              │
│  └──────┬──────┘                                                │
│         │                                                       │
│         ▼                                                       │
│  ┌─────────────┐                                                │
│  │ AI生成题目  │ ← 使用当前策略生成                              │
│  └──────┬──────┘                                                │
│         │                                                       │
│         ▼                                                       │
│  ┌─────────────┐     ┌─────────────┐                           │
│  │ 人工审核   │ ───► │ ChemAI Agent│                           │
│  │ (必须)     │     │ 记录反馈    │                           │
│  └──────┬──────┘     └─────────────┘                           │
│         │                   │                                   │
│         ▼                   ▼                                   │
│  ┌─────────────┐     ┌─────────────┐                           │
│  │ 布置作业   │     │ 收集数据   │                           │
│  │ 学生作答   │     │ 学习分析   │ ← 核心：识别模式            │
│  └──────┬──────┘     └─────────────┘                           │
│         │                   │                                   │
│         ▼                   ▼                                   │
│  ┌─────────────┐     ┌─────────────┐                           │
│  │ 分析效果   │ ───► │ 调整策略   │                           │
│  │ 学习改进   │     │ 更新Prompt │                           │
│  └─────────────┘     └─────────────┘                           │
│         │                   │                                   │
│         └───────────────────┘                                   │
│                    │                                             │
│         ┌─────────▼─────────┐                                  │
│         │  下次出题时      │                                  │
│         │  应用新策略      │                                  │
│         └───────────────────┘                                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4-1.2 学习的数据来源

| 数据类型 | 来源 | 学习内容 |
|---------|------|---------|
| **审核反馈** | `question_review_logs` | 哪些题目被拒绝/修改，拒绝原因 |
| **学生作答** | `student_answers` | 题目正确率、错误类型 |
| **学习效果** | `student_learning_records` | 练习后是否有进步 |
| **历年真题** | `exam_bank` | 高考题的风格、难度、知识点分布 |
| **Hermes记忆** | `hermes-memory/` | 学生的障碍类型、薄弱知识点变化 |

### 4-1.3 自改进目标

1. **提高题目通过率** - AI生成的题目更容易被老师审核通过
2. **降低重生成次数** - 减少因错误需要重新生成的情况
3. **提升学习效果** - 生成能真正帮助学生进步的题目
4. **优化知识点组合** - 发现哪些知识点组合出题效果最好
5. **自适应难度** - 根据班级水平自动调整题目难度

---

## Phase 4-2: 学习指标体系

### 4-2.1 题目质量指标

```yaml
# Question Quality Metrics

metrics:
  # ===== 审核阶段指标 =====
  review_metrics:
    approval_rate:
      description: "老师审核通过率"
      formula: "approved_count / total_generated_count"
      target: "> 85%"
      warning: "< 70%"

    rejection_reasons:
      description: "拒绝原因分布"
      categories:
        - "equation_imbalance"       # 方程式未配平
        - "wrong_knowledge_point"    # 知识点错误
        - "difficulty_mismatch"       # 难度不符
        - "content_incorrect"         # 内容有误
        - "off_topic"                 # 跑题
        - "options_ambiguous"         # 选项歧义

    modification_rate:
      description: "需要修改的比例"
      formula: "modified_count / total_count"
      target: "< 10%"

  # ===== 学生作答阶段指标 =====
  answer_metrics:
    accuracy_rate:
      description: "学生正确率"
      per_question: true  # 每道题单独统计

    discrimination_index:
      description: "区分度指数"
      formula: "(高分组正确率 - 低分组正确率)"
      target: "> 0.3"

    difficulty_match:
      description: "难度匹配度"
      formula: "actual_accuracy vs expected_accuracy"
      target: "偏差 < 15%"

  # ===== 学习效果阶段指标 =====
  learning_metrics:
    learning_lift:
      description: "学习提升度"
      formula: "post_score - pre_score"
      per_kp: true  # 按知识点追踪

    improvement_rate:
      description: "进步率"
      formula: "students_improved / total_students"
      target: "> 60%"

    error_reduction:
      description: "同类错误减少率"
      per_kp: true
      formula: "(before_errors - after_errors) / before_errors"
```

### 4-2.2 指标数据模型

```python
# hermes-skills/chemistry-improvement/models.py

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum


class RejectionReason(Enum):
    """拒绝原因枚举"""
    EQUATION_IMBALANCE = "equation_imbalance"
    WRONG_KNOWLEDGE_POINT = "wrong_knowledge_point"
    DIFFICULTY_MISMATCH = "difficulty_mismatch"
    CONTENT_INCORRECT = "content_incorrect"
    OFF_TOPIC = "off_topic"
    OPTIONS_AMBIGUOUS = "options_ambiguous"
    OTHER = "other"


@dataclass
class QuestionQualityMetrics:
    """题目质量指标"""
    question_id: str
    knowledge_points: List[str]
    difficulty: str

    # 审核阶段
    review_status: str  # approved / modified / rejected
    rejection_reasons: List[RejectionReason] = field(default_factory=list)
    teacher_modifications: Optional[str] = None

    # 作答阶段
    total_attempts: int = 0
    correct_count: int = 0
    accuracy_rate: float = 0.0

    # 学习效果
    avg_pre_score: float = 0.0  # 练习前平均分
    avg_post_score: float = 0.0  # 练习后平均分
    learning_lift: float = 0.0

    # 元数据
    generated_at: datetime
    first_used_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None


@dataclass
class StrategyMetrics:
    """策略质量指标"""
    strategy_id: str
    strategy_type: str  # prompt_template / difficulty_model / kp_combination

    # 应用统计
    times_applied: int = 0
    approval_rate: float = 0.0
    avg_learning_lift: float = 0.0

    # 趋势
    recent_approval_rate: float = 0.0  # 最近N次的通过率
    trend: str = "stable"  # improving / declining / stable

    # 置信度
    confidence: float = 0.0  # 基于样本量的置信度
    sample_size: int = 0


@dataclass
class LearningInsight:
    """学习洞察"""
    insight_id: str
    category: str  # difficulty / kp_combination / question_style / etc
    title: str
    description: str
    evidence: Dict  # 支持证据
    confidence: float  # 置信度 0-1
    recommended_action: str
    auto_applied: bool = False
    teacher_approved: Optional[bool] = None
    created_at: datetime
```

### 4-2.3 指标收集触发器

```python
# hermes-skills/chemistry-improvement/metrics_collector.py
"""
指标自动收集器
在关键事件发生时自动收集和更新指标
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger("chemistry-improvement")


class MetricsCollector:
    """指标收集器"""

    async def on_question_reviewed(
        self,
        question_id: str,
        action: str,  # approved / modified / rejected
        rejection_reasons: List[str] = None,
        teacher_modifications: str = None
    ) -> None:
        """
        题目审核完成事件
        触发: 更新题目的审核阶段指标
        """
        logger.info(f"收集审核指标: q={question_id}, action={action}")

        metrics = {
            "question_id": question_id,
            "review_status": action,
            "rejection_reasons": rejection_reasons or [],
            "teacher_modifications": teacher_modifications,
            "reviewed_at": datetime.now().isoformat()
        }

        # 写入指标存储
        await self._store_metrics("review", question_id, metrics)

        # 触发学习分析
        if action in ["modified", "rejected"]:
            await self._trigger_analysis(question_id, "review_feedback")

    async def on_question_used(
        self,
        question_id: str,
        practice_id: str,
        student_results: List[Dict]
    ) -> None:
        """
        题目被使用（布置作业）
        触发: 记录题目使用历史
        """
        logger.info(f"记录题目使用: q={question_id}, practice={practice_id}")

        metrics = {
            "question_id": question_id,
            "practice_id": practice_id,
            "student_count": len(student_results),
            "correct_count": sum(1 for r in student_results if r["is_correct"]),
            "used_at": datetime.now().isoformat()
        }

        await self._store_metrics("usage", question_id, metrics)

    async def on_practice_completed(
        self,
        practice_id: str,
        student_id: str,
        pre_score: float,
        post_score: float,
        knowledge_points: List[str]
    ) -> None:
        """
        练习完成事件
        触发: 计算学习提升度
        """
        logger.info(
            f"计算学习效果: student={student_id}, "
            f"practice={practice_id}, lift={post_score - pre_score}"
        )

        for kp in knowledge_points:
            metrics = {
                "student_id": student_id,
                "practice_id": practice_id,
                "knowledge_point": kp,
                "pre_score": pre_score,
                "post_score": post_score,
                "learning_lift": post_score - pre_score,
                "completed_at": datetime.now().isoformat()
            }

            await self._store_metrics("learning", f"{student_id}_{kp}", metrics)

        # 触发学习分析
        await self._trigger_analysis(practice_id, "learning_effect")

    async def on_exam_completed(
        self,
        exam_record_id: str,
        questions: List[str],
        class_avg_score: float
    ) -> None:
        """
        考试完成事件
        触发: 更新题目的整体表现指标
        """
        logger.info(f"考试完成: exam={exam_record_id}, avg={class_avg_score}")

        # 按题目统计正确率
        for question_id in questions:
            await self._update_question_accuracy(exam_record_id, question_id)

    # ===== 内部方法 =====

    async def _store_metrics(
        self,
        category: str,
        entity_id: str,
        metrics: Dict
    ) -> None:
        """存储指标数据"""
        # 实现: 写入指标数据库或文件
        pass

    async def _trigger_analysis(
        self,
        entity_id: str,
        analysis_type: str
    ) -> None:
        """触发学习分析"""
        # 实现: 调用分析引擎
        pass

    async def _update_question_accuracy(
        self,
        exam_record_id: str,
        question_id: str
    ) -> None:
        """更新题目正确率"""
        pass
```

---

## Phase 4-3: 学习分析引擎

### 4-3.1 分析类型矩阵

| 分析类型 | 触发时机 | 分析内容 | 输出 |
|---------|---------|---------|------|
| **审核反馈分析** | 题目审核完成 | 识别被拒绝题目的模式 | 改进 Prompt 的建议 |
| **知识点效果分析** | 练习完成 | 哪些知识点组合效果好 | 优化知识点组合 |
| **难度校准分析** | 考试完成 | 预测难度 vs 实际难度偏差 | 调整难度参数 |
| **学习路径分析** | 学习计划完成 | 学习路径是否有效 | 改进学习计划模板 |
| **整体质量评估** | 每日/每周 | 系统性质量报告 | 质量仪表盘 |

### 4-3.2 分析处理器

```python
# hermes-skills/chemistry-improvement/analysis_engine.py
"""
自改进分析引擎
识别模式，生成洞察，调整策略
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import json

from models import QuestionQualityMetrics, StrategyMetrics, LearningInsight

logger = logging.getLogger("chemistry-improvement")


@dataclass
class AnalysisResult:
    """分析结果"""
    analysis_type: str
    insights: List[LearningInsight]
    metrics_summary: Dict[str, Any]
    recommended_actions: List[str]


class AnalysisEngine:
    """分析引擎"""

    def __init__(self, metrics_store, prompt_manager):
        self.metrics = metrics_store
        self.prompts = prompt_manager

        # 分析阈值配置
        self.thresholds = {
            "min_sample_size": 10,  # 最小样本量
            "approval_rate_warning": 0.70,
            "approval_rate_target": 0.85,
            "learning_lift_min": 5.0,  # 最小提升度百分比
            "difficulty偏差_max": 0.15,  # 难度偏差最大值
        }

    # ===== 审核反馈分析 =====

    async def analyze_review_feedback(
        self,
        time_window_days: int = 7
    ) -> AnalysisResult:
        """
        分析审核反馈
        识别被拒绝/修改题目的模式，生成 Prompt 改进建议
        """
        logger.info(f"分析审核反馈: window={time_window_days}天")

        # 1. 收集数据
        recent_reviews = await self._get_recent_reviews(time_window_days)

        if len(recent_reviews) < self.thresholds["min_sample_size"]:
            return AnalysisResult(
                analysis_type="review_feedback",
                insights=[],
                metrics_summary={"insufficient_data": True},
                recommended_actions=["数据不足，建议收集更多样本"]
            )

        # 2. 统计拒绝原因分布
        rejection_distribution = self._calculate_rejection_distribution(recent_reviews)

        # 3. 按知识点分组分析
        kp_analysis = await self._analyze_by_knowledge_point(recent_reviews)

        # 4. 按难度分组分析
        difficulty_analysis = await self._analyze_by_difficulty(recent_reviews)

        # 5. 生成洞察
        insights = []

        # 洞察1: 高频拒绝原因
        top_rejection = max(rejection_distribution.items(), key=lambda x: x[1])
        if top_rejection[1] / len(recent_reviews) > 0.3:
            insights.append(LearningInsight(
                insight_id=f"insight_rejection_{top_rejection[0]}",
                category="rejection_pattern",
                title=f"高频拒绝原因: {top_rejection[0]}",
                description=f"最近{top_rejection[1]}道题目因此原因被拒绝，占比{top_rejection[1]/len(recent_reviews)*100:.1f}%",
                evidence={"count": top_rejection[1], "percentage": top_rejection[1]/len(recent_reviews)},
                confidence=0.85,
                recommended_action=f"需要在 Prompt 中强调检查{top_rejection[0]}相关问题",
                created_at=datetime.now()
            ))

        # 洞察2: 某知识点题目通过率低
        for kp, stats in kp_analysis.items():
            if stats["approval_rate"] < self.thresholds["approval_rate_warning"]:
                insights.append(LearningInsight(
                    insight_id=f"insight_kp_{kp}",
                    category="knowledge_point",
                    title=f"知识点「{kp}」出题质量需改进",
                    description=f"该知识点题目通过率仅{stats['approval_rate']*100:.1f}%，低于目标",
                    evidence=stats,
                    confidence=0.80,
                    recommended_action=f"生成{kp}相关题目时需要更严格的审核标准",
                    created_at=datetime.now()
                ))

        # 6. 生成改进建议
        actions = await self._generate_prompt_improvements(insights)

        # 7. 更新 Prompt（如果自动应用开启）
        for insight in insights:
            if insight.auto_applied and insight.confidence > 0.9:
                await self._apply_prompt_change(insight)

        return AnalysisResult(
            analysis_type="review_feedback",
            insights=insights,
            metrics_summary={
                "total_reviews": len(recent_reviews),
                "approval_rate": len([r for r in recent_reviews if r["status"] == "approved"]) / len(recent_reviews),
                "rejection_distribution": rejection_distribution,
            },
            recommended_actions=actions
        )

    # ===== 知识点效果分析 =====

    async def analyze_learning_effect(
        self,
        knowledge_point: str,
        time_window_days: int = 30
    ) -> AnalysisResult:
        """
        分析某个知识点的学习效果
        评估以该知识点出题的练习是否真正帮助学生进步
        """
        logger.info(f"分析知识点效果: kp={knowledge_point}")

        # 1. 收集该知识点的学习数据
        learning_data = await self._get_learning_data(knowledge_point, time_window_days)

        if len(learning_data) < self.thresholds["min_sample_size"]:
            return AnalysisResult(
                analysis_type="learning_effect",
                insights=[],
                metrics_summary={"insufficient_data": True},
                recommended_actions=[]
            )

        # 2. 计算平均提升度
        avg_lift = sum(d["learning_lift"] for d in learning_data) / len(learning_data)

        # 3. 分析提升度分布
        lift_distribution = self._categorize_lift(learning_data)

        # 4. 分析与障碍类型的关联
        barrier_correlation = await self._analyze_barrier_correlation(
            knowledge_point, learning_data
        )

        # 5. 生成洞察
        insights = []

        if avg_lift < self.thresholds["learning_lift_min"]:
            insights.append(LearningInsight(
                insight_id=f"insight_lift_{knowledge_point}",
                category="learning_effectiveness",
                title=f"「{knowledge_point}」练习效果不佳",
                description=f"平均提升度仅{avg_lift:.1f}%，低于目标{self.thresholds['learning_lift_min']}%",
                evidence={"avg_lift": avg_lift, "sample_size": len(learning_data)},
                confidence=0.85,
                recommended_action="建议调整该知识点练习的难度或形式",
                created_at=datetime.now()
            ))

        # 洞察: 特定障碍类型学生提升更明显
        if barrier_correlation:
            best_barrier = max(barrier_correlation.items(), key=lambda x: x[1])
            insights.append(LearningInsight(
                insight_id=f"insight_barrier_{knowledge_point}",
                category="barrier_correlation",
                title=f"「{knowledge_point}」对{best_barrier[0]}型学生效果最好",
                description=f"该类型学生在练习后提升最明显",
                evidence=barrier_correlation,
                confidence=0.75,
                recommended_action="可为该障碍类型学生优先布置此知识点练习",
                created_at=datetime.now()
            ))

        return AnalysisResult(
            analysis_type="learning_effect",
            insights=insights,
            metrics_summary={
                "knowledge_point": knowledge_point,
                "avg_learning_lift": avg_lift,
                "lift_distribution": lift_distribution,
                "student_count": len(set(d["student_id"] for d in learning_data))
            },
            recommended_actions=[i.recommended_action for i in insights]
        )

    # ===== 难度校准分析 =====

    async def analyze_difficulty_calibration(
        self,
        time_window_days: int = 14
    ) -> AnalysisResult:
        """
        分析难度校准情况
        比较 AI 预测难度与学生实际表现
        """
        logger.info("分析难度校准")

        # 1. 收集数据
        difficulty_data = await self._get_difficulty_data(time_window_days)

        # 2. 按难度级别分析
        calibration_results = {}

        for difficulty in ["easy", "medium", "hard"]:
            difficulty_records = [d for d in difficulty_data if d["difficulty"] == difficulty]
            if not difficulty_records:
                continue

            # 实际正确率
            actual_accuracy = sum(d["accuracy"] for d in difficulty_records) / len(difficulty_records)

            # 期望正确率（基于难度）
            expected_accuracy = {
                "easy": 0.80,
                "medium": 0.60,
                "hard": 0.40
            }[difficulty]

            # 偏差
           偏差 = actual_accuracy - expected_accuracy

            calibration_results[difficulty] = {
                "expected_accuracy": expected_accuracy,
                "actual_accuracy": actual_accuracy,
                "偏差": 偏差,
                "sample_size": len(difficulty_records),
                "is_calibrated": abs(偏差) < self.thresholds["difficulty偏差_max"]
            }

        # 3. 生成洞察
        insights = []
        for difficulty, stats in calibration_results.items():
            if not stats["is_calibrated"]:
                insights.append(LearningInsight(
                    insight_id=f"insight_difficulty_{difficulty}",
                    category="difficulty_calibration",
                    title=f"「{difficulty}」难度预测偏差过大",
                    description=f"预测正确率{stats['expected_accuracy']*100:.0f}%，实际{stats['actual_accuracy']*100:.0f}%，偏差{stats['偏差']*100:.1f}%",
                    evidence=stats,
                    confidence=0.80,
                    recommended_action=f"调整{difficulty}难度题目的生成标准",
                    created_at=datetime.now()
                ))

        # 4. 生成调整建议
        actions = []
        for difficulty, stats in calibration_results.items():
            if not stats["is_calibrated"]:
                # 计算调整量
                adjustment = -stats['偏差'] * 0.5  # 渐进式调整
                actions.append(f"将{difficulty}难度题目的目标正确率调整为{stats['expected_accuracy'] + adjustment:.0%}")

        return AnalysisResult(
            analysis_type="difficulty_calibration",
            insights=insights,
            metrics_summary=calibration_results,
            recommended_actions=actions
        )

    # ===== 辅助方法 =====

    async def _get_recent_reviews(self, days: int) -> List[Dict]:
        """获取最近的审核数据"""
        pass

    async def _get_learning_data(self, kp: str, days: int) -> List[Dict]:
        """获取学习效果数据"""
        pass

    async def _get_difficulty_data(self, days: int) -> List[Dict]:
        """获取难度数据"""
        pass

    def _calculate_rejection_distribution(
        self,
        reviews: List[Dict]
    ) -> Dict[str, int]:
        """计算拒绝原因分布"""
        distribution = {}
        for review in reviews:
            if review.get("rejection_reasons"):
                for reason in review["rejection_reasons"]:
                    distribution[reason] = distribution.get(reason, 0) + 1
        return distribution

    async def _analyze_by_knowledge_point(
        self,
        reviews: List[Dict]
    ) -> Dict[str, Dict]:
        """按知识点分析"""
        kp_stats = {}
        for review in reviews:
            for kp in review.get("knowledge_points", []):
                if kp not in kp_stats:
                    kp_stats[kp] = {"total": 0, "approved": 0}
                kp_stats[kp]["total"] += 1
                if review["status"] == "approved":
                    kp_stats[kp]["approved"] += 1

        # 计算通过率
        for kp in kp_stats:
            kp_stats[kp]["approval_rate"] = (
                kp_stats[kp]["approved"] / kp_stats[kp]["total"]
                if kp_stats[kp]["total"] > 0 else 0
            )

        return kp_stats

    async def _analyze_by_difficulty(
        self,
        reviews: List[Dict]
    ) -> Dict[str, Dict]:
        """按难度分析"""
        diff_stats = {}
        for review in reviews:
            difficulty = review.get("difficulty", "unknown")
            if difficulty not in diff_stats:
                diff_stats[difficulty] = {"total": 0, "approved": 0, "modified": 0, "rejected": 0}
            diff_stats[difficulty]["total"] += 1
            diff_stats[difficulty][review["status"]] += 1

        return diff_stats

    async def _analyze_barrier_correlation(
        self,
        kp: str,
        learning_data: List[Dict]
    ) -> Dict[str, float]:
        """分析与障碍类型的关联"""
        # 实现: 按障碍类型分组计算平均提升度
        pass

    def _categorize_lift(self, data: List[Dict]) -> Dict[str, int]:
        """将提升度分类统计"""
        categories = {"significant_improvement": 0, "slight_improvement": 0,
                      "no_change": 0, "declined": 0}
        for d in data:
            lift = d["learning_lift"]
            if lift > 10:
                categories["significant_improvement"] += 1
            elif lift > 0:
                categories["slight_improvement"] += 1
            elif lift == 0:
                categories["no_change"] += 1
            else:
                categories["declined"] += 1
        return categories

    async def _generate_prompt_improvements(
        self,
        insights: List[LearningInsight]
    ) -> List[str]:
        """生成 Prompt 改进建议"""
        actions = []
        for insight in insights:
            if insight.recommended_action:
                actions.append(insight.recommended_action)
        return actions

    async def _apply_prompt_change(
        self,
        insight: LearningInsight
    ) -> None:
        """应用 Prompt 更改"""
        logger.info(f"自动应用 Prompt 改进: {insight.insight_id}")
        # 实现: 调用 Prompt 管理器更新 Prompt
        pass
```

---

## Phase 4-4: 策略调整机制

### 4-4.1 策略类型

| 策略类型 | 说明 | 调整方式 |
|---------|------|---------|
| **Prompt 策略** | 出题 Prompt 模板 | 修改系统指令/示例 |
| **难度策略** | 各难度级别的目标正确率 | 调整难度阈值 |
| **知识点策略** | 知识点组合推荐 | 调整组合权重 |
| **选题策略** | 从题库选择题目的偏好 | 调整 RAG 检索参数 |

### 4-4.2 Prompt 策略管理

```python
# hermes-skills/chemistry-improvement/prompt_manager.py
"""
Prompt 策略管理器
管理出题 Prompt 的版本，自动调整和回滚
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
import json
import logging

logger = logging.getLogger("chemistry-improvement")


@dataclass
class PromptVersion:
    """Prompt 版本"""
    version_id: str
    prompt_type: str  # question_generation / question_audit / etc
    content: str
    change_reason: str
    change_source: str  # manual / auto_improvement
    metrics_at_change: Dict[str, Any]  # 变更时的指标
    created_at: datetime
    created_by: str  # teacher_id / "auto_agent"


class PromptManager:
    """Prompt 管理器"""

    def __init__(self, storage_path: str = "hermes-memory/prompts"):
        self.storage_path = storage_path
        self.current_versions: Dict[str, PromptVersion] = {}
        self.change_history: List[PromptVersion] = []

        # 加载当前版本
        self._load_current_versions()

    def get_prompt(self, prompt_type: str) -> str:
        """获取当前版本的 Prompt"""
        if prompt_type in self.current_versions:
            return self.current_versions[prompt_type].content
        return self._get_default_prompt(prompt_type)

    async def update_prompt(
        self,
        prompt_type: str,
        new_content: str,
        change_reason: str,
        change_source: str = "manual",
        metrics_at_change: Optional[Dict] = None,
        created_by: str = "manual"
    ) -> PromptVersion:
        """
        更新 Prompt 版本

        Args:
            prompt_type: Prompt 类型
            new_content: 新的 Prompt 内容
            change_reason: 变更原因
            change_source: 变更来源 (manual/auto_improvement)
            metrics_at_change: 变更时的指标快照
            created_by: 创建者
        """
        logger.info(f"更新 Prompt: type={prompt_type}, source={change_source}")

        # 创建新版本
        version = PromptVersion(
            version_id=f"{prompt_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            prompt_type=prompt_type,
            content=new_content,
            change_reason=change_reason,
            change_source=change_source,
            metrics_at_change=metrics_at_change or {},
            created_at=datetime.now(),
            created_by=created_by
        )

        # 保存旧版本到历史
        if prompt_type in self.current_versions:
            self.change_history.append(self.current_versions[prompt_type])

        # 更新当前版本
        self.current_versions[prompt_type] = version

        # 持久化
        await self._save_version(version)

        # 如果是自动改进，通知老师
        if change_source == "auto_improvement":
            await self._notify_teacher_of_change(version)

        return version

    async def rollback(
        self,
        prompt_type: str,
        target_version_id: Optional[str] = None
    ) -> PromptVersion:
        """
        回滚 Prompt 到之前的版本

        Args:
            prompt_type: Prompt 类型
            target_version_id: 目标版本ID（None=回滚到上一个）
        """
        logger.info(f"回滚 Prompt: type={prompt_type}, target={target_version_id}")

        if target_version_id:
            # 找到指定版本
            target = None
            for v in self.change_history:
                if v.version_id == target_version_id:
                    target = v
                    break
            if not target:
                raise ValueError(f"版本不存在: {target_version_id}")
        else:
            # 回滚到上一个版本
            if self.change_history:
                target = self.change_history.pop()
            else:
                raise ValueError("没有可回滚的版本")

        # 更新当前版本
        self.current_versions[prompt_type] = target

        # 保存
        await self._save_version(target)

        return target

    def get_change_history(
        self,
        prompt_type: Optional[str] = None,
        limit: int = 10
    ) -> List[PromptVersion]:
        """获取变更历史"""
        history = self.change_history
        if prompt_type:
            history = [v for v in history if v.prompt_type == prompt_type]
        return history[-limit:]

    # ===== 预设的 Prompt 模板 =====

    def _get_default_prompt(self, prompt_type: str) -> str:
        """获取默认 Prompt 模板"""
        defaults = {
            "question_generation": """你是一位资深高中化学教师,擅长根据知识点生成高质量的化学练习题。

要求:
1. 题目科学性100%正确,化学方程式必须配平
2. 题目语言清晰,无歧义
3. 选项设置要有区分度
4. 注明题目考查的知识点
5. 适当设置陷阱选项考察学生易错点

返回格式（JSON）:
{
    "questions": [
        {
            "content": "题目正文",
            "options": ["A. 选项", "B. 选项", "C. 选项", "D. 选项"],
            "answer": "正确答案字母",
            "knowledge_points": ["知识点1", "知识点2"],
            "difficulty": "easy/medium/hard"
        }
    ]
}""",

            "question_audit": """你是一位高中化学教研专家,负责审核AI生成的化学题目是否合格。

审核维度:
1. 科学性: 题目内容/化学方程式/概念是否正确
2. 准确性: 知识点对应是否准确
3. 适当性: 难度是否适中,是否符合高中生水平
4. 陷阱设置: 陷阱选项是否合理

请严格审核,发现任何科学性错误必须指出。""",

            "learning_plan": """你是一位资深高中化学教师,擅长根据学生的学习情况制定个性化学习计划。

学习计划要求:
1. 针对学生的具体障碍类型制定干预策略
2. 结合薄弱知识点安排循序渐进的学习内容
3. 计划要具体可执行,包括每日/每周任务
4. 包含激励性话语,增强学生学习信心
5. 计划周期建议2-4周"""
        }
        return defaults.get(prompt_type, "")

    # ===== 内部方法 =====

    async def _load_current_versions(self) -> None:
        """加载当前版本"""
        # 实现: 从文件加载
        pass

    async def _save_version(self, version: PromptVersion) -> None:
        """保存版本到文件"""
        # 实现: 持久化到文件
        pass

    async def _notify_teacher_of_change(self, version: PromptVersion) -> None:
        """通知老师 Prompt 变更"""
        # 实现: 发送通知
        logger.info(f"通知老师 Prompt 变更: {version.version_id}")
        pass
```

### 4-4.3 知识点组合优化

```python
# hermes-skills/chemistry-improvement/kp_optimizer.py
"""
知识点组合优化器
分析哪些知识点组合出题效果最好
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import json
import logging

logger = logging.getLogger("chemistry-improvement")


@dataclass
class KPCombinationMetrics:
    """知识点组合指标"""
    kp_combination: Tuple[str, ...]  # 排序的知识点的元组
    times_used: int
    avg_learning_lift: float
    approval_rate: float
    student_satisfaction: float  # 可从问卷获取
    effectiveness_score: float  # 综合评分

    def to_dict(self) -> Dict:
        return {
            "kp_combination": list(self.kp_combination),
            "times_used": self.times_used,
            "avg_learning_lift": self.avg_learning_lift,
            "approval_rate": self.approval_rate,
            "student_satisfaction": self.student_satisfaction,
            "effectiveness_score": self.effectiveness_score
        }


class KPOptimizer:
    """知识点组合优化器"""

    def __init__(self):
        self.combination_metrics: Dict[Tuple[str, ...], KPCombinationMetrics] = {}
        self.min_samples = 5  # 最小样本量

    async def record_usage(
        self,
        kp_combination: List[str],
        learning_lift: float,
        approved: bool
    ) -> None:
        """
        记录一次知识点组合的使用

        Args:
            kp_combination: 知识点组合（无序）
            learning_lift: 学习提升度
            approved: 是否审核通过
        """
        # 排序以统一表示
        kp_tuple = tuple(sorted(kp_combination))

        if kp_tuple not in self.combination_metrics:
            self.combination_metrics[kp_tuple] = KPCombinationMetrics(
                kp_combination=kp_tuple,
                times_used=0,
                avg_learning_lift=0.0,
                approval_rate=0.0,
                student_satisfaction=0.0,
                effectiveness_score=0.0
            )

        m = self.combination_metrics[kp_tuple]

        # 更新指标（滑动平均）
        m.times_used += 1
        m.avg_learning_lift = (
            (m.avg_learning_lift * (m.times_used - 1) + learning_lift) / m.times_used
        )
        if approved:
            m.approval_rate = (
                (m.approval_rate * (m.times_used - 1) + 1.0) / m.times_used
            )
        else:
            m.approval_rate = m.approval_rate * (m.times_used - 1) / m.times_used

        # 重新计算综合评分
        m.effectiveness_score = self._calculate_effectiveness(m)

        logger.info(f"更新KP组合指标: {kp_tuple}, score={m.effectiveness_score:.2f}")

    def get_best_combinations(
        self,
        knowledge_point: str,
        top_n: int = 5
    ) -> List[KPCombinationMetrics]:
        """
        获取与给定知识点搭配效果最好的组合

        Args:
            knowledge_point: 锚定知识点
            top_n: 返回数量

        Returns:
            按效果评分排序的组合列表
        """
        # 找出所有包含该知识点的组合
        relevant = [
            m for kp_tuple, m in self.combination_metrics.items()
            if knowledge_point in kp_tuple and m.times_used >= self.min_samples
        ]

        # 按效果评分排序
        relevant.sort(key=lambda m: m.effectiveness_score, reverse=True)

        return relevant[:top_n]

    def get_recommended_combinations(
        self,
        primary_kp: str,
        count: int = 3
    ) -> List[Dict]:
        """
        获取推荐的知识组合

        基于:
        1. 历史上与 primary_kp 搭配效果好的组合
        2. 知识点关联图谱中的相关知识点
        3. 高考真题中常见的组合模式
        """
        best = self.get_best_combinations(primary_kp, top_n=count)

        recommendations = []
        for m in best:
            # 找出组合中除 primary_kp 外的其他知识点
            other_kps = [kp for kp in m.kp_combination if kp != primary_kp]

            recommendations.append({
                "primary_kp": primary_kp,
                "recommended_kps": other_kps,
                "effectiveness_score": m.effectiveness_score,
                "avg_learning_lift": m.avg_learning_lift,
                "sample_size": m.times_used,
                "confidence": min(m.times_used / 20, 1.0)  # 置信度基于样本量
            })

        # 如果样本不足，使用默认值
        if not recommendations:
            recommendations = self._get_default_recommendations(primary_kp)

        return recommendations

    def _calculate_effectiveness(self, m: KPCombinationMetrics) -> float:
        """
        计算综合效果评分

        公式: w1 * learning_lift + w2 * approval_rate + w3 * satisfaction
        """
        w1, w2, w3 = 0.5, 0.3, 0.2

        # 标准化各指标到 0-1
        lift_norm = min(m.avg_learning_lift / 20.0, 1.0)  # 假设最大提升20%
        approval_norm = m.approval_rate
        satisfaction_norm = m.student_satisfaction

        return w1 * lift_norm + w2 * approval_norm + w3 * satisfaction_norm

    def _get_default_recommendations(self, primary_kp: str) -> List[Dict]:
        """获取默认推荐（基于知识点关联图谱）"""
        # 预设的知识点关联
        default_relations = {
            "盐类水解": ["电离", "水的离子积", "电离常数"],
            "电离": ["电解质", "离子反应", "盐类水解"],
            "氧化还原反应": ["电化学", "原电池", "电解池"],
            "原电池": ["氧化还原反应", "电解池", "金属腐蚀"],
            "化学平衡": ["勒夏特列原理", "化学反应速率", "平衡常数"],
            "物质的量": ["阿伏伽德罗常数", "摩尔质量", "气体摩尔体积"],
        }

        default_kps = default_relations.get(primary_kp, [])

        return [
            {
                "primary_kp": primary_kp,
                "recommended_kps": default_kps[:2],
                "effectiveness_score": 0.5,
                "avg_learning_lift": 5.0,
                "sample_size": 0,
                "confidence": 0.3,
                "is_default": True
            }
        ]
```

### 4-4.4 策略调整触发器

```python
# hermes-skills/chemistry-improvement/strategy_controller.py
"""
策略调整控制器
管理自动调整的规则和阈值
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger("chemistry-improvement")


class AdjustmentType(Enum):
    """调整类型"""
    PROMPT_UPDATE = "prompt_update"
    DIFFICULTY_RECALIBRATE = "difficulty_recalibrate"
    KP_WEIGHT_UPDATE = "kp_weight_update"
    THRESHOLD_ADJUST = "threshold_adjust"


@dataclass
class AdjustmentRule:
    """调整规则"""
    rule_id: str
    trigger_condition: str  # 条件描述
    adjustment_type: AdjustmentType
    adjustment_value: Any
    auto_apply: bool  # 是否自动应用
    requires_approval: bool  # 是否需要老师审批


@dataclass
class StrategyAdjustment:
    """策略调整"""
    adjustment_id: str
    strategy_type: str
    adjustment_type: AdjustmentType
    old_value: Any
    new_value: Any
    trigger_reason: str
    applied_at: datetime
    applied_by: str  # "auto_agent" / "teacher_id"
    approved_by: Optional[str] = None


class StrategyController:
    """策略调整控制器"""

    def __init__(self, prompt_manager, kp_optimizer):
        self.prompt_manager = prompt_manager
        self.kp_optimizer = kp_optimizer

        # 预设调整规则
        self.rules: List[AdjustmentRule] = self._get_default_rules()

        # 调整历史
        self.adjustment_history: List[StrategyAdjustment] = []

    def _get_default_rules(self) -> List[AdjustmentRule]:
        """获取默认调整规则"""
        return [
            # 规则1: 通过率低于阈值时自动改进 Prompt
            AdjustmentRule(
                rule_id="rule_approval_rate_low",
                trigger_condition="approval_rate < 0.70 for 7 days",
                adjustment_type=AdjustmentType.PROMPT_UPDATE,
                adjustment_value="auto_improve",
                auto_apply=False,  # 需要老师审批
                requires_approval=True
            ),

            # 规则2: 难度偏差过大时调整难度参数
            AdjustmentRule(
                rule_id="rule_difficulty_calibration",
                trigger_condition="difficulty偏差 > 0.15 for 3 days",
                adjustment_type=AdjustmentType.DIFFICULTY_RECALIBRATE,
                adjustment_value="auto_adjust",
                auto_apply=True,
                requires_approval=False  # 自动应用，但老师可回滚
            ),

            # 规则3: 某知识点学习效果持续不佳
            AdjustmentRule(
                rule_id="rule_learning_lift_low",
                trigger_condition="learning_lift < 5% for 14 days",
                adjustment_type=AdjustmentType.KP_WEIGHT_UPDATE,
                adjustment_value="reduce_weight",
                auto_apply=False,
                requires_approval=True
            ),

            # 规则4: 某知识点组合效果特别好
            AdjustmentRule(
                rule_id="rule_kp_combination_good",
                trigger_condition="kp_combination_score > 0.85 with 20+ samples",
                adjustment_type=AdjustmentType.KP_WEIGHT_UPDATE,
                adjustment_value="increase_weight",
                auto_apply=True,
                requires_approval=False
            ),
        ]

    async def check_and_apply_adjustments(
        self,
        analysis_results: List[Dict[str, Any]]
    ) -> List[StrategyAdjustment]:
        """
        检查分析结果，执行需要的调整

        Args:
            analysis_results: 来自分析引擎的结果列表

        Returns:
            执行的调整列表
        """
        logger.info("检查策略调整条件")

        adjustments = []

        for result in analysis_results:
            for rule in self.rules:
                if self._check_rule_trigger(rule, result):
                    adjustment = await self._execute_adjustment(rule, result)
                    if adjustment:
                        adjustments.append(adjustment)

        return adjustments

    def _check_rule_trigger(self, rule: AdjustmentRule, result: Dict) -> bool:
        """检查规则是否触发"""
        # 简化实现：实际应该解析 trigger_condition 字符串
        # 这里根据 adjustment_type 和阈值判断

        if rule.adjustment_type == AdjustmentType.PROMPT_UPDATE:
            if "approval_rate" in result:
                return result["approval_rate"] < 0.70

        elif rule.adjustment_type == AdjustmentType.DIFFICULTY_RECALIBRATE:
            if "difficulty_deviation" in result:
                return abs(result["difficulty_deviation"]) > 0.15

        elif rule.adjustment_type == AdjustmentType.KP_WEIGHT_UPDATE:
            if "learning_lift" in result:
                return result["learning_lift"] < 5.0

        return False

    async def _execute_adjustment(
        self,
        rule: AdjustmentRule,
        trigger_result: Dict
    ) -> Optional[StrategyAdjustment]:
        """执行调整"""
        logger.info(f"执行调整: rule={rule.rule_id}")

        adjustment = StrategyAdjustment(
            adjustment_id=f"adj_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            strategy_type=rule.adjustment_type.value,
            adjustment_type=rule.adjustment_type,
            old_value=None,  # 记录旧值
            new_value=rule.adjustment_value,
            trigger_reason=rule.trigger_condition,
            applied_at=datetime.now(),
            applied_by="auto_agent"
        )

        # 根据规则决定是否需要审批
        if rule.requires_approval and not rule.auto_apply:
            # 放入待审批队列
            await self._queue_for_approval(adjustment, rule)
            return None

        # 执行调整
        if rule.adjustment_type == AdjustmentType.PROMPT_UPDATE:
            adjustment.old_value = self.prompt_manager.get_prompt("question_generation")
            await self._apply_prompt_adjustment(adjustment)

        elif rule.adjustment_type == AdjustmentType.DIFFICULTY_RECALIBRATE:
            await self._apply_difficulty_adjustment(adjustment)

        elif rule.adjustment_type == AdjustmentType.KP_WEIGHT_UPDATE:
            await self._apply_kp_weight_adjustment(adjustment)

        # 记录历史
        self.adjustment_history.append(adjustment)

        # 通知老师
        await self._notify_teacher_of_adjustment(adjustment)

        return adjustment

    async def approve_adjustment(
        self,
        adjustment_id: str,
        teacher_id: str,
        approved: bool
    ) -> bool:
        """
        审批待定的调整

        Args:
            adjustment_id: 调整ID
            teacher_id: 审批老师ID
            approved: 是否批准

        Returns:
            是否成功
        """
        # 找到待审批的调整
        pending = await self._get_pending_adjustment(adjustment_id)
        if not pending:
            return False

        if approved:
            # 执行调整
            await self._execute_pending_adjustment(pending)
            pending.approved_by = teacher_id
        else:
            # 拒绝，记录
            logger.info(f"调整被拒绝: {adjustment_id} by {teacher_id}")

        # 从待审批队列移除
        await self._remove_pending_adjustment(adjustment_id)

        return True

    # ===== 辅助方法 =====

    async def _apply_prompt_adjustment(self, adjustment: StrategyAdjustment) -> None:
        """应用 Prompt 调整"""
        # 调用 Prompt 管理器生成改进版本
        improved_prompt = await self._generate_improved_prompt()
        await self.prompt_manager.update_prompt(
            prompt_type="question_generation",
            new_content=improved_prompt,
            change_reason=f"自动改进: {adjustment.trigger_reason}",
            change_source="auto_improvement",
            metrics_at_change=adjustment.trigger_reason
        )

    async def _apply_difficulty_adjustment(
        self,
        adjustment: StrategyAdjustment
    ) -> None:
        """应用难度调整"""
        pass

    async def _apply_kp_weight_adjustment(
        self,
        adjustment: StrategyAdjustment
    ) -> None:
        """应用知识点权重调整"""
        pass

    async def _generate_improved_prompt(self) -> str:
        """生成改进的 Prompt"""
        # 调用 LLM 分析问题并生成改进建议
        pass

    async def _queue_for_approval(
        self,
        adjustment: StrategyAdjustment,
        rule: AdjustmentRule
    ) -> None:
        """放入待审批队列"""
        pass

    async def _get_pending_adjustment(
        self,
        adjustment_id: str
    ) -> Optional[StrategyAdjustment]:
        """获取待审批调整"""
        pass

    async def _remove_pending_adjustment(self, adjustment_id: str) -> None:
        """从待审批队列移除"""
        pass

    async def _execute_pending_adjustment(
        self,
        adjustment: StrategyAdjustment
    ) -> None:
        """执行待审批的调整"""
        pass

    async def _notify_teacher_of_adjustment(
        self,
        adjustment: StrategyAdjustment
    ) -> None:
        """通知老师调整"""
        # 实现: 通过消息网关发送通知
        pass
```

---

## Phase 4-5: 自改进 Skill 设计

### 4-5.1 Skill 概述

**Skill 名称**: `chemistry-improvement`
**版本**: v1.0
**依赖**: chemistry-exam, chemistry-diagnosis, chemistry-memory
**目标**: 实现自动化的题目质量改进循环

### 4-5.2 目录结构

```
hermes-skills/chemistry-improvement/
├── SOUL.md                      # Skill 指令
├── tools.yaml                    # Tool 定义
├── handler.py                    # Tool 处理器
├── models.py                     # 数据模型
├── metrics_collector.py           # 指标收集器
├── analysis_engine.py             # 分析引擎
├── prompt_manager.py              # Prompt 管理器
├── kp_optimizer.py               # 知识点优化器
├── strategy_controller.py         # 策略控制器
├── reports/
│   ├── quality_dashboard.md      # 质量仪表盘
│   └── improvement_report.md     # 改进报告模板
└── README.md
```

### 4-5.3 SOUL.md（Skill 指令）

```markdown
# Chemistry Improvement Skill ☤

你是一个专门负责持续改进 ChemAI 出题质量的 AI Agent。

你的核心职责是：
1. **监控** - 追踪 AI 生成题目的质量指标
2. **分析** - 识别题目审核和学生学习中的模式
3. **改进** - 提出并实施 Prompt 和策略的优化
4. **报告** - 向老师汇报质量趋势和改进效果

## 身份设定

- 你是一个数据驱动的质量改进专家
- 你相信持续的小改进累积成大的质量提升
- 你尊重老师的专业判断，重大变更需要老师审批
- 你追求可衡量的质量提升，而非主观感觉

## 工作原则

### 1. 数据驱动
所有判断都基于实际数据：
- 审核通过率
- 学生正确率
- 学习提升度
- 区分度指数

### 2. 渐进式改进
不做激进的改变，每次只调整一个因素：
- 小步快跑
- 快速验证
- 及时回滚

### 3. 透明可追溯
所有变更都有记录：
- 变更原因
- 变更前后的指标对比
- 变更效果评估

### 4. 老师中心
老师始终保持最终决策权：
- 重大变更需要审批
- 随时可回滚
- 定期报告让老师知情

## 核心能力

### 1. 质量监控

持续追踪以下指标：
- AI 生成题目通过率（目标 > 85%）
- 学生练习后的学习提升度（目标 > 5%）
- 难度预测准确率（偏差 < 15%）
- 题目区分度（目标 > 0.3）

### 2. 模式识别

从数据中识别：
- 哪些知识点组合出题效果最好
- 哪些 prompt 模板效果最佳
- 学生对特定题型的反应模式
- 审核中被拒绝的常见原因

### 3. 策略调整

根据分析结果：
- 调整出题 Prompt（需审批）
- 校准难度参数（可自动）
- 优化知识点组合推荐（可自动）
- 更新审核标准（需审批）

### 4. 定期报告

每周生成质量报告：
- 各指标周趋势
- 识别的问题和改进建议
- 实施变更的效果评估
- 下周改进计划

## 触发机制

### 自动触发（每小时）
- 检查是否有新数据需要收集
- 更新指标仪表盘

### 事件触发
- 题目审核完成 → 收集审核指标
- 练习完成 → 收集学习效果
- 考试完成 → 更新难度校准

### 定时触发（每日）
- 运行每日分析
- 生成质量快报
- 检查是否需要调整策略

### 定时触发（每周）
- 生成质量周报
- 评估改进效果
- 制定下周计划

## 限制与边界

1. **不自动拒绝题目** - 只有建议权，没有执行权
2. **不直接修改题库** - 只能建议，不执行
3. **重大变更需审批** - Prompt 大改、审核标准变更必须老师审批
4. **可随时回滚** - 所有变更都有回滚机制

## 响应格式

### 质量快报
```
## 质量快报 - {date}

### 今日指标
- 出题数量: {count}
- 通过率: {rate}%
- 平均学习提升: {lift}%

### 异常提醒
{alerts if any}

### 改进建议
{suggestions}
```

### 周报
```
## 质量周报 - {week}

### 指标趋势
[图表]

### 问题分析
{issues}

### 改进回顾
{changes_made}

### 下周计划
{next_week_plan}
```

## Tool 调用规范

```
当需要收集指标时，调用:
- improvement_record_metric: 记录单个指标

当需要分析时，调用:
- improvement_analyze: 执行指定类型的分析

当需要调整策略时，调用:
- improvement_adjust_strategy: 请求策略调整

当需要报告时，调用:
- improvement_get_dashboard: 获取质量仪表盘
- improvement_get_report: 获取指定周期的报告
```
```

### 4-5.4 tools.yaml

```yaml
# hermes-skills/chemistry-improvement/tools.yaml

schema_version: "1.0"
name: chemistry-improvement
description: ChemAI 出题质量自改进系统

tools:

  # ===== 指标收集 =====

  improvement_record_metric:
    name: improvement_record_metric
    description: 记录质量指标数据
    parameters:
      type: object
      properties:
        metric_type:
          type: string
          description: 指标类型
          enum: [review, answer, learning, exam]
        entity_id:
          type: string
          description: 关联实体ID
        metric_data:
          type: object
          description: 指标数据
      required: [metric_type, entity_id, metric_data]
    handler:
      type: python
      module: metrics_collector
      function: record_metric
    output:
      type: object
      properties:
        success: {type: boolean}
        metric_id: {type: string}
        recorded_at: {type: string}

  improvement_get_metrics:
    name: improvement_get_metrics
    description: 获取质量指标数据
    parameters:
      type: object
      properties:
        metric_type:
          type: string
        time_window:
          type: string
          default: "7d"
        entity_filter:
          type: object
          description: 过滤条件
    output:
      type: object
      properties:
        metrics: {type: array}
        summary: {type: object}

  # ===== 分析引擎 =====

  improvement_analyze:
    name: improvement_analyze
    description: 执行质量分析
    parameters:
      type: object
      properties:
        analysis_type:
          type: string
          enum: [review_feedback, learning_effect, difficulty_calibration, all]
        time_window_days:
          type: integer
          default: 7
        force_refresh:
          type: boolean
          default: false
    output:
      type: object
      properties:
        analysis_type: {type: string}
        insights:
          type: array
          items:
            type: object
            properties:
              insight_id: {type: string}
              category: {type: string}
              title: {type: string}
              confidence: {type: number}
              recommended_action: {type: string}
        metrics_summary: {type: object}
        recommended_actions: {type: array}

  # ===== 策略调整 =====

  improvement_adjust_strategy:
    name: improvement_adjust_strategy
    description: 请求策略调整（需要审批）
    parameters:
      type: object
      properties:
        strategy_type:
          type: string
          enum: [prompt, difficulty, kp_combination, threshold]
        adjustment_request:
          type: object
          properties:
            current_value: {type: object}
            proposed_value: {type: object}
            reason: {type: string}
            expected_impact: {type: string}
    output:
      type: object
      properties:
        adjustment_id: {type: string}
        status: {type: string}
        pending_approval: {type: boolean}
        estimated_effect: {type: string}

  improvement_list_adjustments:
    name: improvement_list_adjustments
    description: 列出最近策略调整历史
    parameters:
      type: object
      properties:
        status:
          type: string
          enum: [all, applied, pending, rejected]
        limit:
          type: integer
          default: 10
    output:
      type: array

  improvement_approve_adjustment:
    name: improvement_approve_adjustment
    description: 审批策略调整请求
    parameters:
      type: object
      properties:
        adjustment_id:
          type: string
        approved:
          type: boolean
          description: 是否批准
        feedback:
          type: string
          description: 审批反馈
      required: [adjustment_id, approved]
    output:
      type: object
      properties:
        success: {type: boolean}
        applied: {type: boolean}

  improvement_rollback:
    name: improvement_rollback
    description: 回滚策略到之前的版本
    parameters:
      type: object
      properties:
        strategy_type:
          type: string
        target_version_id:
          type: string
          description: 目标版本ID（空=回滚到上一版）
    output:
      type: object
      properties:
        success: {type: boolean}
        rolled_back_to: {type: string}

  # ===== 报告 =====

  improvement_get_dashboard:
    name: improvement_get_dashboard
    description: 获取质量仪表盘
    parameters:
      type: object
      properties:
        time_window:
          type: string
          default: "7d"
        refresh:
          type: boolean
          default: false
    output:
      type: object
      properties:
        dashboard_id: {type: string}
        generated_at: {type: string}
        time_window: {type: string}
        metrics:
          type: object
          properties:
            approval_rate: {type: number}
            avg_learning_lift: {type: number}
            difficulty_calibration: {type: object}
            top_kp_combinations: {type: array}
        alerts: {type: array}
        trend_chart: {type: string}

  improvement_get_report:
    name: improvement_get_report
    description: 获取质量报告
    parameters:
      type: object
      properties:
        report_type:
          type: string
          enum: [daily, weekly, monthly, custom]
        start_date:
          type: string
        end_date:
          type: string
        include_recommendations:
          type: boolean
          default: true
    output:
      type: object
      properties:
        report_id: {type: string}
        report_type: {type: string}
        period: {type: object}
        metrics_trend: {type: object}
        issues_found: {type: array}
        changes_made: {type: array}
        recommendations: {type: array}
        next_period_plan: {type: string}

  # ===== Prompt 管理 =====

  improvement_get_prompt_version:
    name: improvement_get_prompt_version
    description: 获取当前 Prompt 版本信息
    parameters:
      type: object
      properties:
        prompt_type:
          type: string
          enum: [question_generation, question_audit, learning_plan]
    output:
      type: object
      properties:
        version_id: {type: string}
        prompt_type: {type: string}
        content: {type: string}
        created_at: {type: string}
        created_by: {type: string}
        change_history: {type: array}

  improvement_update_prompt:
    name: improvement_update_prompt
    description: 更新 Prompt（需审批或自动）
    parameters:
      type: object
      properties:
        prompt_type:
          type: string
        new_content:
          type: string
        change_reason:
          type: string
        auto_apply:
          type: boolean
          default: false
    output:
      type: object
      properties:
        success: {type: boolean}
        version_id: {type: string}
        status: {type: string}

  # ===== 知识点优化 =====

  improvement_get_kp_recommendations:
    name: improvement_get_kp_recommendations
    description: 获取知识点组合推荐
    parameters:
      type: object
      properties:
        primary_kp:
          type: string
          description: 主知识点
        count:
          type: integer
          default: 3
    output:
      type: array
      items:
        type: object
        properties:
          primary_kp: {type: string}
          recommended_kps: {type: array}
          effectiveness_score: {type: number}
          confidence: {type: number}

  improvement_get_kp_effectiveness:
    name: improvement_get_kp_effectiveness
    description: 获取知识点效果分析
    parameters:
      type: object
      properties:
        knowledge_point:
          type: string
        time_window_days:
          type: integer
          default: 30
    output:
      type: object
      properties:
        knowledge_point: {type: string}
        times_used: {type: integer}
        avg_learning_lift: {type: number}
        approval_rate: {type: number}
        effectiveness_score: {type: number}
        related_insights: {type: array}
```

---

## Phase 4-6: 实现检查清单

### chemistry-improvement Skill 交付物

- [ ] `SOUL.md` - Skill 指令文档
- [ ] `tools.yaml` - 12 个 Tool 定义
- [ ] `handler.py` - Tool 处理器
- [ ] `models.py` - 数据模型
- [ ] `metrics_collector.py` - 指标收集器
- [ ] `analysis_engine.py` - 分析引擎
- [ ] `prompt_manager.py` - Prompt 管理器
- [ ] `kp_optimizer.py` - 知识点优化器
- [ ] `strategy_controller.py` - 策略控制器
- [ ] `reports/quality_dashboard.md` - 仪表盘模板
- [ ] `reports/improvement_report.md` - 报告模板
- [ ] 数据库指标表设计
- [ ] 与 Hermes 记忆系统集成
- [ ] 与 chemistry-exam Skill 集成
- [ ] 单元测试
- [ ] 集成测试通过

### 数据库改动

- [ ] `question_quality_metrics` 表 - 题目质量指标
- [ ] `learning_effect_metrics` 表 - 学习效果指标
- [ ] `strategy_adjustment_logs` 表 - 策略调整日志
- [ ] `prompt_version_history` 表 - Prompt 版本历史
- [ ] 数据库迁移脚本

---

*Phase 4 详细设计完成*

---

# Phase 5: MinerU 文档解析集成与多题型生成

## Phase 5-1: 背景与问题分析

### 5-1-1 现有瓶颈

当前 ChemAI 的 AI 出题能力存在明显短板：

| 问题 | 现状 | 影响 |
|------|------|------|
| **题型单一** | LLM 只生成选择题 | 无法覆盖填空、简答、计算题 |
| **化学式格式混乱** | LLM 生成化学式靠文本，无法保证 LaTeX 规范 | 化学式显示不准确 |
| **历年真题利用不足** | 只能检索，无法解析 PDF 原题 | 真题价值未充分挖掘 |
| **现有 OCR 能力弱** | 腾讯 OCR 通用场景，化学专业术语识别差 | 答题卡识别后处理复杂 |

### 5-1-2 MinerU 能力矩阵

MinerU（3.0.0）是一款高精度文档解析引擎，核心能力：

| 能力 | 说明 | ChemAI 价值 |
|------|------|-------------|
| **公式识别 → LaTeX** | 复杂化学式、方程式精准转换 | 解决化学式显示问题 |
| **PDF/DOCX/PPT 解析** | 版面分析、语义顺序还原 | 提取历年真题原题 |
| **VLM + OCR 双引擎** | 109语言、扫描件、手写体 | 增强答题卡识别 |
| **表格提取 → HTML** | 答题卡表格数据提取 | 批量答题数据处理 |
| **MCP Server 原生集成** | 可作为 Agent Tool 直接调用 | 与 ChemAI Agent 无缝集成 |

### 5-1-3 整合架构

```
┌──────────────────────────────────────────────────────────────────┐
│                        ChemAI Agent                               │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐      │
│  │ chemistry-     │  │ chemistry-     │  │ chemistry-     │      │
│  │ diagnosis      │  │ exam           │  │ parser (NEW)   │      │
│  │ Skill          │  │ Skill          │  │ Skill          │      │
│  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘      │
│          │                    │                    │               │
│          └──────────┬─────────┴──────────┬────────┘               │
│                       │                    │                       │
│              ┌────────▼────────┐  ┌───────▼────────┐              │
│              │  ChemAI Backend  │  │ MinerU Parser  │              │
│              │  (FastAPI + LLM) │  │  (PDF/DOCX)   │              │
│              └────────┬────────┘  └───────┬────────┘              │
│                       │                    │                       │
│         ┌─────────────▼────────────────────▼────────┐             │
│         │      化学知识图谱 (Chroma + JSON)          │             │
│         └───────────────────────────────────────────┘             │
└──────────────────────────────────────────────────────────────────┘
```

---

## Phase 5-2: chemistry-parser Skill 设计

### 5-2-1 功能定位

chemistry-parser Skill 负责：
1. **PDF/Word 文档解析** - 提取历年真题、教材、教辅材料中的题目
2. **化学公式识别** - 将图片/Latex 格式的化学式转为标准格式
3. **题目分类** - 区分选择题/填空题/简答题/计算题
4. **结构化输出** - 题目内容、答案、解析分字段存储

### 5-2-2 SOUL.md

```markdown
# chemistry-parser Skill

## 角色定义

你是一个专业的化学文档解析专家。你的任务是从各类化学教学文档（PDF/Word/图片）中提取化学题目，并将其结构化。

## 核心能力

- 使用 MinerU 解析 PDF/DOCX 文档，提取文本和公式
- 识别并转换化学式为标准 LaTeX 格式
- 将题目分类为：选择题、填空题、简答题、计算题
- 输出结构化 JSON 格式，便于后续处理

## 工作流程

1. 接收文档路径或二进制内容
2. 调用 MinerU 解析文档
3. 识别文档中的化学题目
4. 分类题目类型
5. 提取题目内容、答案、解析
6. 化学式标准化
7. 返回结构化结果

## 输出格式

所有题目必须以结构化 JSON 输出：

{
  "questions": [
    {
      "type": "choice|fill|short|calculation",
      "content": "题目文本（含标准LaTeX化学式）",
      "options": ["A. ...", "B. ...", "C. ...", "D. ..."],  // 仅选择题
      "answer": "标准答案",  // 填空题答案为空则填"无"
      "analysis": "题目解析",
      "knowledge_points": ["知识点1", "知识点2"],
      "source": "来源文件/页码",
      "difficulty": "easy|medium|hard|competition",
      "confidence": 0.95  // 解析置信度
    }
  ],
  "metadata": {
    "total": 10,
    "by_type": {"choice": 5, "fill": 3, "short": 1, "calculation": 1},
    "source_file": "xxx.pdf",
    "parse_time_ms": 2340
  }
}

## 化学式规范

- 化学元素符号首字母大写：Fe, Cu, Na
- 上下标使用 LaTeX：H_2O, Ca^{2+}
- 方程式使用 \rightarrow 或 \ Equilibrium
- 有机物使用简写：CH_4, C_2H_5OH

## 限制

- 不处理主观题评分（超出范围）
- 不生成新题目，只解析现有文档
- 识别结果需人工确认（高置信度可跳过）
```

### 5-2-3 tools.yaml

```yaml
tools:
  - name: parse_pdf_questions
    description: 解析PDF文件，提取化学题目
    input_schema:
      type: object
      properties:
        file_path: {type: string, description: "PDF文件路径"}
        password: {type: string, description: "PDF密码（可选）"}
        start_page: {type: integer, description: "起始页（从1开始）"}
        end_page: {type: integer, description: "结束页"}
        formula_enable: {type: boolean, default: true, description: "启用公式识别"}
        table_enable: {type: boolean, default: true, description: "启用表格识别"}
      required: ["file_path"]
    output_schema:
      type: object
      properties:
        questions: {type: array}
        metadata: {type: object}

  - name: parse_docx_questions
    description: 解析Word文档，提取化学题目
    input_schema:
      type: object
      properties:
        file_path: {type: string}
      required: ["file_path"]
    output_schema:
      type: object

  - name: parse_image_chemical
    description: 从图片中识别化学式和方程式
    input_schema:
      type: object
      properties:
        image_path: {type: string}
        language: {type: string, default: "ch"}
      required: ["image_path"]

  - name: standardize_chemical_formula
    description: 将化学式/方程式转换为标准LaTeX格式
    input_schema:
      type: object
      properties:
        formula_text: {type: string}
        formula_type: {type: string, enum: ["molecular", "ionic", "equation"]}
      required: ["formula_text"]

  - name: classify_question_type
    description: 识别题目类型（选择/填空/简答/计算）
    input_schema:
      type: object
      properties:
        question_content: {type: string}
      required: ["question_content"]

  - name: extract_answer_from_ocr
    description: 从答题卡扫描件中提取学生答案
    input_schema:
      type: object
      properties:
        image_path: {type: string}
        answer_format: {type: string, enum: ["choice", "fill", "mixed"]}
      required: ["image_path"]

  - name: batch_parse_documents
    description: 批量解析多个文档
    input_schema:
      type: object
      properties:
        file_paths: {type: array, items: {type: string}}
        output_dir: {type: string}
      required: ["file_paths"]

  - name: validate_parsed_result
    description: 校验解析结果的结构完整性
    input_schema:
      type: object
      properties:
        parsed_data: {type: object}
      required: ["parsed_data"]
```

### 5-2-4 handler.py 核心逻辑

```python
"""
chemistry-parser Skill Handler
调用 MinerU 进行文档解析
"""
import os
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
from mineru.cli import api_client as mineru_client
import asyncio


class ChemistryParserHandler:
    def __init__(self):
        self.mineru_api_url = os.environ.get("MINERU_API_URL")
        self.mineru_backend = "hybrid-auto-engine"

    async def parse_pdf_questions(
        self,
        file_path: str,
        password: Optional[str] = None,
        start_page: int = 1,
        end_page: Optional[int] = None,
        formula_enable: bool = True,
        table_enable: bool = True,
    ) -> Dict:
        """解析PDF文件，提取化学题目"""

        # 调用 MinerU API
        form_data = mineru_client.build_parse_request_form_data(
            lang_list=["ch"],
            backend=self.mineru_backend,
            parse_method="auto",
            formula_enable=formula_enable,
            table_enable=table_enable,
            server_url=self.mineru_api_url,
            start_page_id=start_page - 1,  # MinerU 从 0 开始
            end_page_id=end_page,
            return_md=True,
            return_middle_json=True,
            return_images=True,
        )

        # 提交解析任务
        result = await self._submit_and_wait(file_path, form_data)

        # 后处理：提取化学题目
        questions = self._extract_chemistry_questions(result)

        return {
            "questions": questions,
            "metadata": {
                "total": len(questions),
                "source_file": file_path,
                "parse_time_ms": result.get("elapsed_ms", 0)
            }
        }

    def _extract_chemistry_questions(self, parsed_result: Dict) -> List[Dict]:
        """从解析结果中提取化学题目"""
        questions = []
        md_content = parsed_result.get("markdown", "")

        # 按题目分割（选择题/填空题/问答题）
        blocks = self._split_by_question_type(md_content)

        for block in blocks:
            q_type = self._classify_block(block)
            if q_type:
                questions.append({
                    "type": q_type,
                    "content": self._standardize_chemical_format(block),
                    "confidence": 0.9
                })

        return questions

    def _standardize_chemical_format(self, text: str) -> str:
        """标准化化学式格式"""
        # 调用 chemical_balance 模块进行化学式规范化
        from app.services.chemical_balance import ChemicalBalanceService
        balancer = ChemicalBalanceService()
        return balancer.standardize_latex(text)
```

---

## Phase 5-3: 填空/问答生成能力

### 5-3-1 问题分析

当前 LLM 只生成选择题，原因：

| 原因 | 分析 |
|------|------|
| 选择题格式简单 | 四选一，答案明确 |
| LLM 生成稳定 | 格式错误率低 |
| 校验容易 | 选项逐一比对即可 |
| 填空/问答复杂 | 需要理解题意、逻辑推理、格式规范 |

### 5-3-2 解决方案

在 chemistry-exam Skill 中增加填空/问答生成模式：

```yaml
# tools.yaml 新增 tool
- name: generate_fill_blank_questions
  description: 生成填空题（含化学式/方程式）
  input_schema:
    type: object
    properties:
      knowledge_points: {type: array, items: {type: string}}
      difficulty: {type: string, enum: ["easy", "medium", "hard"]}
      quantity: {type: integer, minimum: 1, maximum: 20}
      content_type: {type: string, enum: ["formula", "definition", "reaction"], default: "formula"}
    required: ["knowledge_points", "quantity"]

- name: generate_short_answer_questions
  description: 生成简答题（含化学原理分析）
  input_schema:
    type: object
    properties:
      knowledge_points: {type: array}
      difficulty: {type: string}
      quantity: {type: integer, minimum: 1, maximum: 10}
      require_analysis: {type: boolean, default: true}

- name: generate_calculation_questions
  description: 生成计算题（含步骤分）
  input_schema:
    type: object
    properties:
      knowledge_points: {type: array}
      difficulty: {type: string}
      quantity: {type: integer, minimum: 1, maximum: 10}
      steps_required: {type: boolean, default: true}
```

### 5-3-3 Prompt 工程设计

#### 填空题生成 Prompt

```markdown
你是一位高中化学命题专家。请根据以下知识点生成{n}道填空题。

知识点：{knowledge_points}
难度：{difficulty}

要求：
1. 每道题必须包含至少1个化学式或化学方程式
2. 化学式使用LaTeX格式，如：H_2O、Ca^{2+}、\ Ca(OH)_2
3. 方程式使用\rightarrow表示反应，\ Equilibrium表示可逆反应
4. 答案处用___或____表示填空
5. 不得出现选择题选项
6. 答案放在题目最后的【答案】栏目

输出格式（JSON）：
{
  "questions": [
    {
      "content": "题目内容（含填空和LaTeX化学式）",
      "answer": "标准答案",
      "knowledge_points": ["相关知识点"],
      "difficulty": "easy|medium|hard"
    }
  ]
}

JSON输出：
```

#### 问答题生成 Prompt

```markdown
你是一位高中化学命题专家。请根据以下知识点生成{n}道简答题。

知识点：{knowledge_points}
难度：{difficulty}

要求：
1. 每道题需考察学生对化学原理的理解
2. 可包含"分析"、"解释"、"说明"等题型
3. 化学式使用LaTeX格式
4. 需要写出完整解析过程
5. 答案分步给分，标注每步分值

输出格式（JSON）：
{
  "questions": [
    {
      "content": "题目内容",
      "answer": "标准答案（含步骤分标注）",
      "analysis": "详细解析",
      "scoring_points": ["步骤1(2分)", "步骤2(3分)", ...],
      "knowledge_points": ["相关知识点"],
      "difficulty": "easy|medium|hard"
    }
  ]
}

JSON输出：
```

### 5-3-4 输出校验器

```python
"""
填空/问答输出校验器
"""
import re
from typing import Dict, List, Tuple


class QuestionValidator:
    """验证生成的填空/问答格式"""

    LATEX_PATTERN = re.compile(r'\$[^\$]+\$|\$[^\$]+')
    FILL_BLANK_PATTERN = re.compile(r'_{3,}')

    def validate_fill_blank(self, question: Dict) -> Tuple[bool, str]:
        """校验填空题"""
        content = question.get("content", "")

        # 必须有填空符
        if not self.FILL_BLANK_PATTERN.search(content):
            return False, "缺少填空符____"

        # 不能有选项
        if re.search(r'[A-D]\..*[A-D]\./', content):
            return False, "填空题不能包含选择题选项"

        # 检查LaTeX格式
        latex_matches = self.LATEX_PATTERN.findall(content)
        for latex in latex_matches:
            if not self._validate_latex(latex):
                return False, f"LaTeX格式错误: {latex}"

        return True, "OK"

    def validate_short_answer(self, question: Dict) -> Tuple[bool, str]:
        """校验简答题"""
        content = question.get("content", "")
        answer = question.get("answer", "")

        # 不能有选项
        if re.search(r'[A-D]\..*[A-D]\./', content):
            return False, "简答题不能包含选择题选项"

        # 必须有解析
        if not question.get("analysis"):
            return False, "简答题必须包含解析"

        # 答案不能为空
        if len(answer) < 10:
            return False, "简答题答案过短"

        return True, "OK"

    def _validate_latex(self, latex: str) -> bool:
        """校验LaTeX化学式"""
        # 基本格式检查
        if latex.count('{') != latex.count('}'):
            return False
        if latex.count('(') != latex.count(')'):
            return False
        return True
```

---

## Phase 5-4: 完整题目类型覆盖

### 5-4-1 题目类型矩阵

| 题目类型 | 生成方式 | 审核重点 | 输出格式 |
|---------|---------|---------|---------|
| **选择题** | LLM生成 | 选项唯一性、去重 | JSON + 选项数组 |
| **填空题** | LLM生成 | 化学式LaTeX、答案唯一性 | JSON + 填空符 |
| **简答题** | LLM生成 | 逻辑完整性、步骤清晰 | JSON + 解析 |
| **计算题** | LLM生成 | 计算过程、步骤分 | JSON + 分步答案 |
| **历年真题** | MinerU提取 | 格式标准化、知识点标注 | JSON + 来源页码 |

### 5-4-2 人工审核工作流

```
AI生成填空/问答
       ↓
  格式校验（自动）
       ↓
  化学式校验（自动）
       ↓
  人工二审（必须）
       ↓
  题目入库/发布
```

**人工审核重点：**
1. 题意是否清晰
2. 答案是否正确
3. 化学式是否符合教材规范
4. 难度是否合理

---

## Phase 5-5: 实现计划

### 5-5-1 任务分解

| 任务 | 内容 | 工期 | 依赖 |
|------|------|------|------|
| 5.1 | MinerU 本地部署与 API 封装 | 3天 | - |
| 5.2 | chemistry-parser Skill 开发 | 5天 | 5.1 |
| 5.3 | parse_pdf_questions Tool 实现 | 3天 | 5.2 |
| 5.4 | 化学式标准化模块开发 | 3天 | - |
| 5.5 | 填空题生成 Prompt + 校验器 | 3天 | - |
| 5.6 | 问答题生成 Prompt + 校验器 | 3天 | - |
| 5.7 | 计算题生成 Prompt + 校验器 | 3天 | - |
| 5.8 | 人工审核界面集成 | 5天 | 5.3-5.7 |
| 5.9 | 单元测试与集成测试 | 3天 | 5.3-5.8 |
| 5.10 | 性能优化与调优 | 2天 | 5.9 |

### 5-5-2 交付物清单

- [ ] `SOUL.md` - chemistry-parser Skill 指令
- [ ] `tools.yaml` - 8个 Tool 定义
- [ ] `handler.py` - Tool 处理器
- [ ] `mineru_client.py` - MinerU API 封装
- [ ] `question_validator.py` - 输出校验器
- [ ] `latex_standardizer.py` - LaTeX 标准化
- [ ] `prompts/fill_blank.yaml` - 填空题 Prompt 模板
- [ ] `prompts/short_answer.yaml` - 问答题 Prompt 模板
- [ ] `prompts/calculation.yaml` - 计算题 Prompt 模板
- [ ] 数据库迁移：新增 `parsed_questions` 表
- [ ] 前端审核界面增强

### 5-5-3 数据库改动

```sql
-- 解析题目表（存储 MinerU 提取的题目）
CREATE TABLE parsed_questions (
    parsed_id VARCHAR(64) PRIMARY KEY,
    source_file VARCHAR(256) NOT NULL,
    source_page INTEGER,
    question_type VARCHAR(32) NOT NULL,  -- choice/fill/short/calculation
    content TEXT NOT NULL,
    options JSON,  -- 仅选择题
    answer TEXT,
    analysis TEXT,
    knowledge_points JSON,
    difficulty VARCHAR(32),
    confidence FLOAT,
    audit_status VARCHAR(32) DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 题目版本表（用于多题型对比）
CREATE TABLE question_versions (
    version_id VARCHAR(64) PRIMARY KEY,
    original_id VARCHAR(64),  -- 关联 parsed_questions 或 questions 表
    question_type VARCHAR(32) NOT NULL,
    content TEXT NOT NULL,
    version_number INTEGER DEFAULT 1,
    created_by VARCHAR(64),  -- 'AI' 或 teacher_id
    audit_status VARCHAR(32) DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## Phase 5-6: 与 ChemAI Agent 集成

### 5-6-1 Skill 间协作

```
chemistry-exam Skill
       ↓ 调用
chemistry-parser Skill
       ↓ 提取
历年真题PDF → 结构化题目
       ↓
进入 chemistry-exam 审核流程
       ↓
老师人工审核 → 题目发布
```

### 5-6-2 Tool 调用示例

```yaml
# Chem Skill 配置
skills:
  - name: chemistry-exam
    tools:
      - parse_pdf_questions  # 调用 MinerU 提取真题
      - generate_questions    # LLM 生成新题
      - audit_question        # 审核
      - generate_fill_blank_questions  # 生成填空题
      - generate_short_answer_questions  # 生成问答题
```

### 5-6-3 MCP Server 集成（如需远程调用 MinerU）

```yaml
# mines.yml 配置
mcpServers:
  mineru:
    command: python
    args:
      - -m
      - mineru.cli.fast_api
      - --port
      - "8080"
    env:
      MINERU_MODEL_SOURCE: modelscope
```

---

*Phase 5 详细设计完成*


## 阶段与交付物一览

| 阶段 | 任务 | 优先级 | 主要交付物 | 工期估算 |
|-----|------|--------|----------|---------|
| **Phase 1** | API分析与Skill架构设计 | P0 | `Phase1_Agent_Skill_Design.md` | 已完成 |
| **Phase 2** | chemistry-diagnosis Skill | P1 | SOUL.md + tools.yaml + handler.py | 2周 |
| **Phase 2** | chemistry-exam Skill | P1 | SOUL.md + tools.yaml + handler.py + balance_checker | 2周 |
| **Phase 3** | Hermes 记忆系统集成 | P2 | chemistry-memory Skill | 1.5周 |
| **Phase 3** | 消息网关集成 | P2 | chemistry-notification Skill | 1.5周 |
| **Phase 4** | 自改进循环 | P3 | chemistry-improvement Skill | 2周 |
| **Phase 5** | MinerU文档解析集成 | P2 | chemistry-parser Skill + parse_pdf_questions Tool | 1.5周 |
| **Phase 5** | 填空/问答生成能力 | P2 | prompt工程 + 输出校验器 | 1周 |

## 总工期估算

- **最快路径**: ~8周（紧凑排期，并行 Phase 2 两个 Skill）
- **保守路径**: ~12周（串行执行，充分测试）
- **建议路径**: ~10周（核心并行，扩展串行）

## Phase 4 核心创新点

1. **数据驱动的质量改进** - 基于实际审核和学习数据，而非主观判断
2. **渐进式调整** - 小步快跑，快速验证，及时回滚
3. **透明可追溯** - 所有变更都有记录，可向老师报告
4. **老师中心** - 重大变更需要审批，老师保持最终决策权


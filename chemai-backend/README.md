# 智辅化学 (ChemAI) - 高中化学AI辅助教学工具

基于PRD v1.0完整版开发的MVP后端服务，支持教师端+学生端完整教学闭环。

## 项目概述

智辅化学是一款面向高中化学教师和学生的AI辅助教学工具，通过以下核心功能提升教学效率：

- **F1: OCR答题卡识别** - 拍照/扫描答题卡，自动识别学生答案，生成班级错题统计表
- **F2: AI出题与三维安全审核** - 基于知识点生成题目，化学方程式系数配平零错误保障
- **F3: 两层错题报告** - 老师详情版（含错误率/典型错误/干预建议）+ 学生筛选版（含鼓励语）
- **F4: 学生障碍类型诊断** - 诊断概念理解型/审题障碍型/表述障碍型，生成个性化干预策略
- **F5: 自适应出题引擎** - 根据学生障碍类型和薄弱知识点推送个性化练习
- **F6: 历年真题智能关联** - AI出题自动关联历年同类真题
- **F7: 班级学情可视化面板** - 三维度学情分析（知识点/学生/时间）

## 技术栈

| 层级 | 技术选型 | 成本 |
|------|---------|------|
| LLM | 通义千问 qwen-turbo | <¥200/月 |
| 向量数据库 | Chroma | ¥0 |
| OCR | 腾讯OCR | <¥100/月 |
| 后端框架 | FastAPI + SQLAlchemy | 开源 |
| 数据库 | SQLite/MySQL | ¥0 |
| **月度成本** | - | **<¥500/月** |

## 快速开始

### 1. 安装依赖

```bash
cd chemai-backend
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑.env填写API密钥
```

### 3. 初始化数据库

```bash
python -c "from app.models.database import init_db; init_db()"
```

### 4. 启动服务

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

> 推荐直接用一键脚本：`start.bat` 开发模式（端口 8001 + 热重载，自动等就绪后开浏览器）或 `start.bat stable` 稳定模式（端口 8000，无热重载）。

### 5. 访问API文档

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 功能模块

### F1: OCR答题卡识别

```bash
# 识别单张答题卡
curl -X POST "http://localhost:8000/api/ocr/recognize" \
  -F "file=@answer_sheet.jpg"

# 批量识别
curl -X POST "http://localhost:8000/api/ocr/recognize/batch" \
  -F "files=@sheet1.jpg" -F "files=@sheet2.jpg"
```

### F2: AI出题与审核

```bash
# AI生成题目
curl -X POST "http://localhost:8000/api/question/generate" \
  -H "Content-Type: application/json" \
  -d '{"knowledge_points": ["盐类水解", "电离"], "difficulty": "medium", "quantity": 5}'

# 题目安全审核
curl -X POST "http://localhost:8000/api/question/audit" \
  -H "Content-Type: application/json" \
  -d '{"question_content": "题目内容..."}'

# 老师自主导入题目（手动录入）
curl -X POST "http://localhost:8000/api/question/import" \
  -H "Content-Type: application/json" \
  -d '{"questions": [...]}'

# 老师自主导入题目（OCR扫描试卷）
curl -X POST "http://localhost:8000/api/question/import/ocr" \
  -F "file=@paper.jpg"
```

### F3: 错题报告

```bash
# 老师详情版报告
curl "http://localhost:8000/api/report/teacher/exam_20260408"

# 学生筛选版报告
curl "http://localhost:8000/api/report/student/exam_20260408/student_001"

# 一键发送报告给学生
curl -X POST "http://localhost:8000/api/report/send-to-students/exam_20260408"

# 导出报告
curl "http://localhost:8000/api/report/export/exam_20260408?format=json"
```

### F4: 障碍诊断与学习计划

```bash
# 班级学生障碍诊断
curl "http://localhost:8000/api/diagnosis/barrier/class_001/exam_20260408"

# 生成个性化学习计划（LLM）
curl -X POST "http://localhost:8000/api/diagnosis/learning-plan/generate" \
  -H "Content-Type: application/json" \
  -d '{"student_id": "student_001", "barrier_type": "concept", "weak_knowledge_points": ["盐类水解", "电离"]}'

# 应用学习计划到学生
curl -X POST "http://localhost:8000/api/diagnosis/learning-plan/apply/student_001" \
  -H "Content-Type: application/json" \
  -d '{"plan": {...}}'

# 发送学习计划给家长
curl -X POST "http://localhost:8000/api/diagnosis/learning-plan/send-to-parent/student_001"
```

### F5: 自适应练习

```bash
# 布置练习
curl -X POST "http://localhost:8000/api/practice/assign" \
  -H "Content-Type: application/json" \
  -d '{"class_id": "class_001", "knowledge_points": ["盐类水解"], "question_count": 10}'

# 学生获取练习任务
curl "http://localhost:8000/api/practice/student/student_001/tasks"

# 提交练习答案
curl -X POST "http://localhost:8000/api/practice/submit" \
  -H "Content-Type: application/json" \
  -d '{"practice_id": "practice_001", "student_id": "student_001", "answers": [...]}'
```

### F7: 学情面板

```bash
# 班级学情面板
curl "http://localhost:8000/api/panel/class/class_001"

# 知识点详情
curl "http://localhost:8000/api/panel/class/class_001/knowledge/盐类水解"

# 学生学习详情
curl "http://localhost:8000/api/panel/class/class_001/student/student_001"

# 班级学情趋势
curl "http://localhost:8000/api/panel/class/class_001/trend"
```

## 题库（历年真题）

题库存放于 `data/exam_questions/` 目录，已提取2008-2025年真题：

| 来源 | 年份范围 | 题目数量 | 状态 |
|------|---------|---------|------|
| 全国卷 | 2008-2020 | 143题 | **可用** |
| 湖南卷 | 2021-2025 | 107题 | **可用** |
| **合计** | 18年 | **250题** | - |

**覆盖高频知识点：** 盐类水解、电离平衡、原电池、电解池、氧化还原反应、化学平衡、反应速率、元素周期律、有机化学、物质的量等

## 项目结构

```
chemai-backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI应用入口
│   ├── api/                    # API路由
│   │   ├── auth.py            # 认证（登录/注册/登出）
│   │   ├── user.py            # 用户管理（学生/教师CRUD）
│   │   ├── class_api.py       # 班级管理
│   │   ├── ocr.py             # F1: OCR识别
│   │   ├── exam.py            # 考试管理
│   │   ├── question.py        # F2: AI出题/审核/导入
│   │   ├── diagnosis.py       # F4: 障碍诊断/学习计划
│   │   ├── report.py          # F3: 报告生成
│   │   ├── practice.py        # F5: 自适应练习
│   │   └── panel.py           # F7: 学情面板
│   ├── core/
│   │   └── config.py         # 配置管理
│   ├── models/
│   │   └── database.py       # 数据库模型（7个核心实体）
│   ├── services/
│   │   ├── chemical_balance.py  # F2: 化学方程式审核引擎
│   │   ├── llm_service.py       # 通义千问API封装
│   │   ├── ocr_service.py       # OCR服务封装
│   │   └── exam_bank.py        # 历年真题库
│   └── utils/
├── data/
│   ├── exam_questions/       # 历年真题JSON文件
│   ├── chromadb/              # 向量数据库
│   └── knowledge_graph/       # 知识点数据
├── frontend/                  # 前端代码（教师端+学生端）
├── tests/
├── requirements.txt
├── .env.example
└── README.md
```

## 数据库模型

实现7个核心实体：

- `Teacher` - 教师表
- `Student` - 学生表
- `Class` - 班级表
- `ExamRecord` - 考试/练习记录表
- `Question` - 题目表（含AI生成+手动选题+OCR导入）
- `BarrierConfig` - 障碍诊断配置表
- `Account` - 账户表（登录认证）

## API清单

### 认证 API

| API | 方法 | 说明 |
|-----|------|------|
| `/api/auth/login` | POST | 用户登录 |
| `/api/auth/register` | POST | 用户注册 |
| `/api/auth/logout` | POST | 登出 |

### 用户管理 API

| API | 方法 | 说明 |
|-----|------|------|
| `/api/users/students` | GET | 获取学生列表 |
| `/api/users/teachers` | GET | 获取教师列表 |
| `/api/users/student` | POST | 创建学生 |
| `/api/users/student/{id}` | PUT | 更新学生 |
| `/api/users/student/{id}` | DELETE | 删除学生 |
| `/api/users/student/approve/{id}` | POST | 审批学生 |
| `/api/users/teacher/{id}` | PUT | 更新教师 |
| `/api/users/teacher/approve/{id}` | POST | 审批教师 |

### 班级管理 API

| API | 方法 | 说明 |
|-----|------|------|
| `/api/classes` | GET | 获取班级列表 |
| `/api/classes` | POST | 创建班级 |
| `/api/classes/{id}` | PUT | 更新班级 |
| `/api/classes/{id}` | DELETE | 删除班级 |
| `/api/classes/{id}/students` | GET | 获取班级学生 |

### 核心功能 API

| API | 方法 | 说明 |
|-----|------|------|
| `/api/ocr/recognize` | POST | F1: 答题卡OCR识别 |
| `/api/ocr/recognize/batch` | POST | F1: 批量OCR识别 |
| `/api/ocr/stats` | POST | F1: 生成错题统计 |
| `/api/question/generate` | POST | F2: AI生成题目 |
| `/api/question/audit` | POST | F2: 题目安全审核 |
| `/api/question/historical` | GET | F6: 历年真题查询 |
| `/api/question/import` | POST | F2: 老师手动导入题目 |
| `/api/question/import/batch` | POST | F2: 批量导入（Base64） |
| `/api/question/import/ocr` | POST | F2: OCR扫描导入 |
| `/api/diagnosis/barrier/{class_id}/{exam_id}` | GET | F4: 班级障碍诊断 |
| `/api/diagnosis/barrier/{student_id}` | GET | F4: 学生障碍详情 |
| `/api/diagnosis/learning-plan/generate` | POST | F4: 生成学习计划 |
| `/api/diagnosis/learning-plan/apply/{student_id}` | POST | F4: 应用学习计划 |
| `/api/diagnosis/learning-plan/send-to-parent/{student_id}` | POST | F4: 发送计划给家长 |
| `/api/diagnosis/config/{teacher_id}` | GET/PUT | F4: 诊断规则配置 |
| `/api/report/teacher/{exam_id}` | GET | F3: 老师详情版报告 |
| `/api/report/student/{exam_id}/{student_id}` | GET | F3: 学生筛选版报告 |
| `/api/report/send-to-students/{exam_id}` | POST | F3: 一键发送报告 |
| `/api/report/export/{exam_id}` | GET | F3: 导出报告 |
| `/api/practice/assign` | POST | F5: 布置自适应练习 |
| `/api/practice/student/{id}/tasks` | GET | F5: 学生练习任务 |
| `/api/practice/student/{id}/practice/{pid}` | GET | F5: 练习内容 |
| `/api/practice/submit` | POST | F5: 提交练习 |
| `/api/practice/effect/{student_id}` | GET | F5: 练习效果 |
| `/api/panel/class/{class_id}` | GET | F7: 班级学情面板 |
| `/api/panel/class/{class_id}/knowledge/{kp}` | GET | F7: 知识点详情 |
| `/api/panel/class/{class_id}/student/{sid}` | GET | F7: 学生详情 |
| `/api/panel/class/{class_id}/trend` | GET | F7: 学情趋势 |
| `/api/panel/export/{class_id}` | GET | F7: 导出面板 |

## 化学方程式审核引擎

F2安全审核的核心模块，实现四维审核：

1. **系数配平审核** - 使用元素原子计数法验证配平
2. **反应条件审核** - 检查点燃/加热/催化剂等标注
3. **产物稳定性审核** - 检查产物是否合理
4. **分子结构审核** - 检查化学式/结构式是否正确

```python
from app.services.chemical_balance import audit_chemical_equation

result = audit_chemical_equation("2H2 + O2 → 2H2O")
print(result["overall_status"])  # "passed" or "blocked"
```

## LLM 服务

支持通义千问和ChatGLM两种大模型：

```python
from app.services.llm_service import llm_service

# AI生成题目
result = llm_service.generate_questions(
    knowledge_points=["盐类水解", "电离"],
    difficulty="medium",
    quantity=5
)

# 题目安全审核
result = llm_service.audit_question_with_llm(question_content)

# 障碍类型诊断
result = llm_service.diagnose_barrier_type(
    student_error_history=[...],
    question_content="...",
    student_answer="...",
    correct_answer="..."
)

# 历年真题关联
result = llm_service.find_similar_historical_questions(
    question_content="...",
    knowledge_point="盐类水解"
)

# 生成个性化学习计划
result = llm_service.generate_learning_plan(
    student_name="张三",
    barrier_type="concept",
    weak_knowledge_points=["盐类水解", "电离"]
)
```

## 开发团队

MVP阶段建议配置:

- 后端开发: 1人
- 前端开发: 1人
- AI/算法工程师: 0.5人
- 产品经理: 0.5人

## 文档

- [PRD v1.0完整版](../../Desktop/高中化学AI辅助教学工具_PRD_v1.0_完整版.md)
- [需求规格说明书](../../Desktop/高中化学AI辅助教学工具_产品需求规格说明书_v1.0.md)
- [访谈洞察报告](../../Desktop/化学教师AI辅助教学完整访谈洞察报告.md)
- [开发计划](../../.claude/plans/glistening-cooking-peach.md)

## License

Proprietary - MVP Internal Use Only

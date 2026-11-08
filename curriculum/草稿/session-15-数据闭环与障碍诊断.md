# Session 15 · 数据闭环与障碍诊断

## 产出物

- `agent/tools.py` 中的 `diagnose_barrier()` 函数 — 三维障碍类型自动诊断（concept/reading/expression）
- `agent/tools.py` 中的 `assign_adaptive_practice()` 函数 — 基于障碍类型匹配自适应练习题
- `app/api/practice.py` 中的 `/api/practice/submit` 接口 — 闭环的数据入口
- `docs/data-loop-design.md` — 数据闭环完整设计文档（四节点流程 + 技术挑战 + 增长数据）
- `docs/cold-start-solution.md` — 冷启动问题的处理方案（<5 条记录的处理逻辑）
- `chemai.db` 中 students 表的 barriar_type 字段 — 从初始 NULL 变为有实际诊断数据
- 闭环节点验证报告 — 用 1680 条数据验证闭环的完整链路

## 前置条件

- Session 10 的数据库就绪（14 个表、67 名学生、1005 条答题记录）
- Session 3 的 JTBD 矩阵就绪（特别是 J6 "识别学生真实障碍类型"）
- `app/services/llm_service.py` 中的 `generate_text()` 方法可用（DeepSeek API 连通）
- Python 3.11 + SQLAlchemy + aiosqlite 已安装

## 项目背景（给学生的概述）

前几节课你搭好了数据库，接了 LLM，写了 API。但现在功能之间还是孤立的——学生答完题，数据进了 `student_answers` 表，然后就没了。教师看不到诊断结果，学生得不到针对性练习。

这门课要做的是把孤岛**连成闭环**。

"数据闭环"听起来像是大数据的词，但 ChemAI 的数据闭环很小——用户不到 200 人，数据库只有 4.5MB。闭环的逻辑也很简单：学生作答 → 数据入库 → 诊断更新 → 自适应出题 → 学生再次作答。每次作答都让诊断更准一点，每次出题都更有针对性一点。

这堂课的核心函数是 `diagnose_barrier()`——它的任务是把一堆"答对/答错"的布尔值，翻译成教师看得懂的三维诊断：这个学生的问题到底是**概念没懂**（concept）、还是**题目没读懂**（reading）、还是**懂了但写不对**（expression）。

三维分类的逻辑来自一个真实的场景：第三轮访谈中教师说"分数差不多的两个学生，可能一个属于第二类，一个属于第三类"。如果系统只能告诉教师"这个学生 XX 分"，那等于没帮上忙——排名的信息量跟一张 Excel 表没区别。诊断的价值在于**解释为什么**，而不是**报告结果**。

这节课你还会遇到三个真实的技术挑战：障碍分类准确率只有 70%、冷启动（新学生没有数据）、小样本过拟合（15 人只有不到 10 条记录）。每一个挑战都有对应的工程解法——不完美，但已经能工作。

---

## 操作步骤

### 步骤 1：理解现有数据并确认闭环的四个节点

**目标**：用 SQL 查询理解当前 `student_answers` 表的数据结构，画出闭环四节点流程图

**提示词**（复制到 Claude Code）：

```
在 chemai-backend 项目中，用 Python 脚本连接 SQLite 数据库，探索 student_answers 表的数据结构。

请执行以下操作：

1. 查询 student_answers 表的总行数
2. 查询 is_correct 的分布（正确/错误各多少条）
3. 查询 barriar_type 不为 NULL 的记录数量，按类型分组（concept/reading/expression）
4. 查询每个学生的答题记录数量分布（按 student_id 分组，看最少和最多）
5. 查询 students 表中 barriar_type 字段（当前应该全部为 NULL，因为还没跑诊断）

查询脚本放在临时文件中执行即可，不需要创建新文件。

在输出中，除了数据统计外，还要画出"数据闭环四节点流程图"：

```
节点 1：学生作答 → student_answers 表
  │  POST /api/practice/submit 写入 is_correct + barrier_type
  ▼
节点 2：诊断更新 → students 表的 barrier_type
  │  diagnose_barrier() 遍历 student_answers 聚合计算
  ▼
节点 3：自适应出题 → 根据障碍类型选题目
  │  assign_adaptive_practice() 匹配 concept/reading/expression 题型
  ▼
节点 4：学生再次作答 → 回到节点 1
  │  每次作答都是新数据，闭环持续改进
  └──────────────────────────────────┘
```

验证数据（来自项目 1-3 月实际增长）：
| 指标 | 1 月初始 | 3 月 |
|------|---------|------|
| student_answers 行数 | 1005 | 1680 |
| 诊断准确率 | — | ~70% |
| barrier_type JSON 更新次数 | 0 | 89 |
| 自适应练习生成次数 | 0 | 34 |
```

**验证**：
- [ ] student_answers 表总行数 = 1005
- [ ] is_correct 分布合理（约 60% 正确）
- [ ] barriar_type 三种类型的分布正确（40/35/25）
- [ ] 识别出记录少于 10 条的学生（冷启动问题）

---

### 步骤 2：实现 diagnose_barrier() 函数

**目标**：在 `agent/tools.py` 中实现三维障碍诊断函数，支持单学生和全班级模式

**提示词**（复制到 Claude Code）：

```
在 chemai-backend 项目中创建 agent/ 目录（如果不存在，含 __init__.py），然后创建 agent/tools.py。

在 tools.py 中实现 diagnose_barrier() 函数，这是 ChemAI 数据闭环的核心诊断函数。

## 函数签名

```python
def diagnose_barrier(student_id_or_class_id: str, mode: str = "student") -> dict:
    """
    三维障碍类型自动诊断

    Args:
        student_id_or_class_id: 学生ID（mode="student"）或班级ID（mode="class"）
        mode: "student" 诊断单个学生 / "class" 诊断全班学生

    Returns:
        dict: 诊断结果
            mode="student" 时：{"student_id": str, "barrier_distribution": {concept/reading/expression}, "total_errors": int, "confidence": str}
            mode="class" 时：{"class_id": str, "students": [...], "class_summary": {...}}
    """
```

## 核心逻辑

### 步骤 1：查询该学生的所有错误记录

```python
# 从 student_answers 表查询 is_correct=False 的记录
# JOIN questions 表获取 knowledge_points （用于判断概念障碍）
errors = db.query(StudentAnswer).filter(
    StudentAnswer.student_id == student_id,
    StudentAnswer.is_correct == False,
    StudentAnswer.barrier_type != None  # 只统计已被判定障碍类型的错题
).all()
```

### 步骤 2：三维分类统计

```python
concept_errors = 0
reading_errors = 0
expression_errors = 0

for error in errors:
    if error.barrier_type == 'concept':
        concept_errors += 1
    elif error.barrier_type == 'reading':
        reading_errors += 1
    elif error.barrier_type == 'expression':
        expression_errors += 1

total_errors = concept_errors + reading_errors + expression_errors
```

### 步骤 3：计算分布比例

```python
if total_errors > 0:
    barrier_distribution = {
        'concept': round(concept_errors / total_errors, 3),
        'reading': round(reading_errors / total_errors, 3),
        'expression': round(expression_errors / total_errors, 3)
    }
else:
    barrier_distribution = {'concept': 0.0, 'reading': 0.0, 'expression': 0.0}
```

### 步骤 4：冷启动处理（关键逻辑）

如果该学生的答题记录少于 5 条（total_errors < 5 或 student_answers 表该生总记录 < 5）：

```python
if total_errors < 5:
    # 使用班级平均分布作为先验
    class_avg = get_class_average_barrier(class_id)
    # 结合个人数据进行贝叶斯修正（简化版：加权平均）
    # 个人权重 = min(total_errors / 5, 1.0)  （最多 5 条后个人数据权重 100%）
    personal_weight = min(total_errors / 5.0, 1.0)
    class_weight = 1.0 - personal_weight

    barrier_distribution = {
        'concept': round(personal_weight * (concept_errors / max(total_errors, 1)) + class_weight * class_avg['concept'], 3),
        'reading': round(personal_weight * (reading_errors / max(total_errors, 1)) + class_weight * class_avg['reading'], 3),
        'expression': round(personal_weight * (expression_errors / max(total_errors, 1)) + class_weight * class_avg['expression'], 3),
    }
```

冷启动策略的说明（注释中写清楚）：
- 新学生没有任何答题记录时，barriar_type 为空
- 有 1-4 条记录时，用班级平均分布做先验，个人数据做修正
- 5 条及以上时，完全使用个人数据
- 这是折中方案——理想情况需要 50+ 条记录才能有高置信度，但 5 条是最低可接受阈值

### 步骤 5：写入 students 表

```python
student = db.query(Student).filter(Student.id == student_id).first()
student.barrier_type = barrier_distribution
student.barrier_updated_at = datetime.utcnow()
db.commit()
```

### 步骤 6：班级模式

mode="class" 时，遍历该班级所有学生，逐一调用 mode="student" 的诊断。汇总输出班级级别的统计：
- 全班 concept/reading/expression 平均分布
- 障碍类型最突出的学生列表（各类型 Top 5）
- 全班需要重点关注的维度

## 函数返回值示例

```json
// mode="student"
{
    "student_id": "学生_07",
    "student_name": "学生_07",
    "barrier_distribution": {
        "concept": 0.3,
        "reading": 0.5,
        "expression": 0.2
    },
    "total_errors": 12,
    "primary_barrier": "reading",
    "confidence": "medium",    // <5条=low, 5-20条=medium, >20条=high
    "cold_start": false         // 是否使用了冷启动策略
}

// mode="class"
{
    "class_id": "1",
    "class_name": "高一(1)班",
    "student_count": 34,
    "diagnosed_count": 30,
    "class_distribution": {
        "concept": 0.40,
        "reading": 0.35,
        "expression": 0.25
    },
    "students": [
        {"student_id": "学生_01", "primary_barrier": "concept", "distribution": {...}},
        ...
    ],
    "summary": "全班概念理解障碍占比最高（40%），建议加强氧化还原反应和离子反应的知识点讲解。"
}
```

## 导入依赖

```python
from app.models.database import SessionLocal
from app.models.models import Student, StudentAnswer, Question
from datetime import datetime
```

## 辅助函数 get_class_average_barrier()

```python
def get_class_average_barrier(class_id: int) -> dict:
    """获取班级级别的平均障碍分布（用于冷启动先验）"""
    # 查询该班级所有已诊断学生的 barriar_type
    # 计算三个维度的平均值
    # 返回 {"concept": 0.40, "reading": 0.35, "expression": 0.25}
```

## 验证

在文件末尾添加 if __name__ == "__main__" 测试块，验证：
1. 诊断学生_01（约 15 条记录）：输出三维分布
2. 诊断一个记录 <5 条的学生：输出冷启动标记
3. 诊断高一(1)班（34 人）：输出班级汇总
4. 检查数据库中 students.barrier_type 字段是否被正确更新
```

**验证**：
- [ ] `agent/tools.py` 存在，含 `diagnose_barrier()` 和 `get_class_average_barrier()`
- [ ] 单学生诊断返回三维分布（三个数之和约等于 1.0）
- [ ] 冷启动学生在 total_errors < 5 时标记 `cold_start: true`
- [ ] 班级模式输出全班汇总
- [ ] `students.barrier_type` 字段在诊断后被更新（不再是 NULL）

---

### 步骤 3：实现 assign_adaptive_practice() 函数

**目标**：基于学生的障碍诊断结果，从题库中匹配针对性练习题

**提示词**（复制到 Claude Code）：

```
在 agent/tools.py 中添加 assign_adaptive_practice() 函数。

## 函数签名

```python
def assign_adaptive_practice(student_id: str, question_count: int = 5) -> dict:
    """
    基于学生障碍诊断结果，匹配自适应练习题

    Args:
        student_id: 学生ID
        question_count: 需要的题目数量（默认 5 道）

    Returns:
        dict: {
            "student_id": str,
            "barrier_distribution": dict,
            "practice_plan": {
                "concept_questions": int,    # 分配给概念判断的题数
                "reading_questions": int,    # 分配给审题陷阱的题数
                "expression_questions": int  # 分配给书写规范的题数
            },
            "questions": [...],              # 选中的题目列表
            "rationale": str                 # 为什么这样分配（可读文字）
        }
    """
```

## 核心逻辑

### 步骤 1：获取学生的障碍分布

```python
# 如果 students.barrier_type 为 NULL，先跑 diagnose_barrier(student_id)
student = db.query(Student).filter(Student.id == student_id).first()
if student.barrier_type is None:
    diagnose_barrier(student_id)

barrier = student.barrier_type  # {"concept": 0.3, "reading": 0.5, "expression": 0.2}
```

### 步骤 2：按障碍比例分配题数

```python
concept_count = max(1, int(question_count * barrier['concept']))
reading_count = max(1, int(question_count * barrier['reading']))
expression_count = max(1, int(question_count * barrier['expression']))

# 确保总和等于 question_count（处理取整误差）
# 优先补齐最大障碍类型的题目
```

分配策略说明（注释中写清楚）：
- 每个类型至少分配 1 道题（即使该类型障碍占比很低——因为不能完全忽略）
- 剩余题数按比例分配
- 最大障碍类型获得最多题目

### 步骤 3：从题库中匹配题目

```python
# concept 障碍 → 概念判断题（检测是否真的理解）
#   筛选条件：question_type='choice' 且 difficulty='easy' 且 knowledge_points 覆盖该学生常错知识点
concept_questions = db.query(Question).filter(
    Question.difficulty == 'easy',
    Question.question_type.in_(['choice']),
    # 优先选择该学生常错的知识点
).limit(concept_count).all()

# reading 障碍 → 审题陷阱题（情境复杂、关键信息隐藏在题干中）
#   筛选条件：content 长度 ≥ 200 字符（题干较长的题目）
reading_questions = db.query(Question).filter(
    # content 较长的题目 → 审题难度高
).limit(reading_count).all()

# expression 障碍 → 书写规范题（需要写出完整方程式，不是选择题）
#   筛选条件：question_type='fill' 且 content 中含有化学方程式或离子方程式
expression_questions = db.query(Question).filter(
    Question.question_type.in_(['fill', 'short_answer']),
    # content 中包含方程式相关关键词
).limit(expression_count).all()
```

### 步骤 4：组装返回结果

返回包含 practice_plan（分配方案）、questions（具体题目）、rationale（为什么这样分配——给教师看的可读文本，如"该生审题障碍占比最高（50%），因此分配了 3 道审题陷阱题，帮助提升题干理解能力。")

## 题目匹配的强化逻辑（从 3 月实际数据学到的教训）

初始策略只按 difficulty 和 question_type 筛选，导致匹配的题目可能跟学生的知识盲区无关。3 月改进版增加了"常错知识点优先"策略：

```python
# 查询该学生最常错的知识点（出现 ≥2 次的错误知识点）
frequent_error_kps = get_frequent_error_knowledge_points(student_id)
# 优先选择覆盖这些知识点的题目
```

## 辅助函数 get_frequent_error_knowledge_points()

```python
def get_frequent_error_knowledge_points(student_id: str) -> list:
    """获取该学生高频错误知识点（出现 ≥2 次）"""
    # 从 student_answers JOIN questions 查询
    # is_correct=False 的记录按 knowledge_points 分组
    # 返回出现次数 ≥2 的知识点 JSON 数组
```

在 if __name__ == "__main__" 测试块中验证：
1. 为学生_07（reading 障碍 50%）分配 5 道题 → 验证 reading 类题数 ≥2
2. 为记录 <5 条的学生分配 → 验证冷启动默认分配（平均分配）
3. 打印 rationale 内容——必须是一段可读的中文解释
```

**验证**：
- [ ] `assign_adaptive_practice()` 函数存在
- [ ] 题数分配按障碍比例（最大障碍类型分配最多题）
- [ ] 冷启动学生使用平均分配策略
- [ ] rationale 是可读的中文解释

---

### 步骤 4：实现闭环数据流 —— 让学生再次作答的数据更新诊断

**目标**：创建 `/api/practice/submit` 接口，完成数据闭环的最后一步

**提示词**（复制到 Claude Code）：

```
在 chemai-backend 项目中创建 app/api/practice.py，实现数据闭环的后端接口。

这个文件是实现数据闭环"节点 4 → 节点 1"的关键。每一次学生提交答案，都是一次新的数据输入，闭环就转动一次。

## 接口 1：POST /api/practice/submit

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.models.database import SessionLocal, get_db

router = APIRouter(prefix="/api/practice", tags=["practice"])

class AnswerSubmit(BaseModel):
    student_id: str
    practice_id: str = None
    answers: list[dict]  # [{"question_id": int, "student_answer": str}]

class SubmitResponse(BaseModel):
    success: bool
    data: dict  # {"correct_count": int, "total_count": int, "score_percentage": float}
    barrier_update: dict = None  # 如果本次提交触发了诊断更新，返回新的分布

@router.post("/submit")
async def submit_answers(submit: AnswerSubmit, db: Session = Depends(get_db)):
    """
    学生提交练习答案 → 写入 student_answers 表 → 判断障碍类型 → 必要时更新诊断
    """
```

### 处理步骤：

#### 步骤 1：遍历答案数组，逐题写入 student_answers

```python
correct_count = 0
total_count = len(submit.answers)

for answer in submit.answers:
    question = db.query(Question).filter(Question.id == answer['question_id']).first()
    if not question:
        continue

    is_correct = (answer['student_answer'].strip() == question.answer.strip())

    # 判断这道题的障碍类型（错题才需要判断）
    barrier = None
    if not is_correct:
        barrier = classify_single_answer_barrier(student_id=submit.student_id,
                                                  question_id=answer['question_id'],
                                                  student_answer=answer['student_answer'],
                                                  question=question)

    new_answer = StudentAnswer(
        student_id=submit.student_id,
        question_id=answer['question_id'],
        student_answer=answer['student_answer'],
        is_correct=is_correct,
        barrier_type=barrier,
        answered_at=datetime.utcnow()
    )
    db.add(new_answer)

    if is_correct:
        correct_count += 1

db.commit()
```

#### 步骤 2：classify_single_answer_barrier() — 单题障碍判定

这个函数判断一道错误暴露了什么类型的障碍：

```python
def classify_single_answer_barrier(student_id, question_id, student_answer, question):
    """
    判断单道错题的障碍类型

    规则（基于 3 月实际运行数据总结）：
    1. 如果同一学生在同一知识点的题目上连续错 ≥2 次 → concept（概念障碍）
       检查方法：查询该学生最近 5 条 is_correct=False 的记录，
       如果当前题的知识点与之前的错题知识点有交集 → concept

    2. 如果题干长度 ≥ 200 字符 → reading（审题障碍）
       经验：题干较长的题目对 90+ 人大班中后排学生的审题要求更高

    3. 如果题目类型是 fill 或 short_answer 且涉及化学方程式 → expression（表述障碍）
       化学方程式书写题丢分往往是"知道但写不对"

    4. 如果以上都不满足，按默认比例分配（40% concept / 35% reading / 25% expression）
    """
    # 规则 1：连续错误检测
    recent_errors = db.query(...).filter(
        StudentAnswer.student_id == student_id,
        StudentAnswer.is_correct == False
    ).order_by(StudentAnswer.answered_at.desc()).limit(5).all()

    # 如果当前题的知识点与最近错题有交集 → concept
    # 规则 2：题干长度检测
    if len(question.content or "") >= 200:
        return "reading"
    # 规则 3：题目类型检测
    if question.question_type in ('fill', 'short_answer'):
        return "expression"
    # 规则 4：默认回退
    return default_classification(question)
```

#### 步骤 3：更新诊断（如果错误计数达到阈值）

```python
# 如果该学生本次提交新增了错误，重新统计其总错误数
# 如果总错误数 >= 5（冷启动阈值），重新跑诊断
student = db.query(Student).filter(Student.id == submit.student_id).first()
total_errors = db.query(StudentAnswer).filter(
    StudentAnswer.student_id == submit.student_id,
    StudentAnswer.is_correct == False
).count()

if total_errors >= 5:
    from agent.tools import diagnose_barrier
    result = diagnose_barrier(submit.student_id)
    barrier_update = result
else:
    barrier_update = {"note": "回答记录不足5条，暂未触发诊断更新。当前总错误数：" + str(total_errors)}
```

返回结果包含：
- correct_count / total_count / score_percentage
- barrier_update（如果有诊断更新）

验证：在 if __name__ == "__main__" 块中启动 uvicorn，用 curl 测试模拟一次提交。
```

**验证**：
- [ ] `app/api/practice.py` 存在
- [ ] `POST /api/practice/submit` 能正确处理 5 道题的提交
- [ ] 正确率计算正确
- [ ] 新增记录被写入 student_answers 表
- [ ] barrier_type 在错题记录中被正确赋值

---

### 步骤 5：生成数据闭环设计文档

**目标**：将闭环四节点流程、技术挑战、增长数据写成完整文档

**提示词**（复制到 Claude Code）：

```
生成两份文档，放在 docs/ 目录下。

## 文档 1：docs/data-loop-design.md

结构：

### 1. 闭环概述
- 定义：学生作答 → 诊断更新 → 自适应出题 → 学生再次作答
- 数据量：<200 人，<10MB（不需要大数据工具）
- 设计原则：每次作答都在改进诊断，诊断驱动出题，出题引导再次作答

### 2. 四节点详细流程
每个节点展开描述：涉及的表/字段、触发条件、输入/输出

- 节点 1：学生作答 → student_answers 表（POST /api/practice/submit）
- 节点 2：诊断更新 → students.barrier_type（diagnose_barrier()）
- 节点 3：自适应出题 → question_sets（assign_adaptive_practice()）
- 节点 4：学生再次作答 → 回到节点 1

画出流程图（ASCII 格式）

### 3. 1 月-3 月实际数据增长

| 指标 | 1 月 | 2 月 | 3 月 |
|------|------|------|------|
| student_answers 行数 | 1005 | 1340 | 1680 |
| 诊断准确率 | — | ~60% | ~70% |
| barrier_type JSON 更新次数 | 0 | 45 | 89 |
| 自适应练习生成次数 | 0 | 12 | 34 |
| 对话 checkpoints | 0 | 0 | 47 |

分析增长趋势：
- student_answers 从 1005 增长到 1680（+67%），来自种子教师使用中产生的真实数据
- 诊断准确率从 60% 提升到 70%，每增加 300 条数据提升约 5%
- 3 月 29 日 AsyncSqliteSaver 上线后对话数据才开始积累

### 4. 三个技术挑战

#### 挑战 1：障碍分类准确率只有 70%
- 原因：三维分类（concept/reading/expression）基于简单的规则引擎，不是 LLM 语义理解
- 当前策略：
  - 同一知识点连续错 → concept
  - 题干长度 ≥200 字符 → reading
  - fill/short_answer 类型 → expression
- 局限性：一道题答错可能同时涉及 concept 和 reading 障碍，当前只能归为一种
- 后续计划：用 LLM 对比"学生答案 vs 正确答案"，判断错误出现在哪个环节（选错选项 / 漏看条件 / 方程式配平错误）

#### 挑战 2：冷启动问题
- 问题：新学生没有任何答题记录，barriar_type 为 NULL，无法分配自适应练习
- 当前方案：
  - <5 条记录 → 使用班级平均分布作为先验，结合个人数据进行加权平均
  - 5+ 条记录 → 完全使用个人数据
  - 0 条记录 → 分配默认中等难度练习（等待积累数据）
- 权衡：先验假设"新学生的障碍分布接近班级平均"——这个假设不一定对，但在数据不足时的最佳猜测

#### 挑战 3：小样本过拟合
- 67 个学生中约 15 人记录 <10 条
- 这些学生的诊断准确率显著低于有 50+ 条记录的学生
- 当前缓解方案：贝叶斯修正（班级先验 + 个人数据），给少量个人数据较低的权重
- 后续方案：引入遗忘曲线权重（最近错误 > 历史错误）+ 学生端的"我学会了"按钮作为正反馈信号

### 5. 闭环的量化效果（已观察到的）
- 错题统计耗时：1.5h → 5s（场景 1 验证通过）
- 诊断速度：全班 34 人诊断 < 3 秒
- 自适应出题速度：单次生成 5 题 < 2 秒
- 数据库增长：~50-100 条/每次练习

### 6. 闭环的下一步计划
1. LLM 辅助错误类型判断（提升准确率到 85%+）
2. 引入遗忘曲线权重（最近错误 > 历史错误）
3. 学生端"我学会了"按钮（主动标记正反馈信号）
4. 对话数据闭环：AsyncSqliteSaver 持久化 → 对话上下文可用于诊断

### 7. 关键技术决策：为什么不在提交时调用 LLM？
classify_single_answer_barrier() 用的是规则引擎，不是 LLM。原因：
- 每道题提交都调用 LLM 成本太高（1005 条 × 0.001 元 = 不贵但没必要）
- 规则引擎的判断逻辑（连续错误 / 题干长度 / 题型）是可解释的
- LLM 应该用在"批量精细化纠正"而非"实时分类"——后续计划中 LLM 用于定期重新分析全部错题

## 文档 2：docs/cold-start-solution.md

结构：

### 问题描述
- 新学生没有答题记录
- 1-4 条记录的统计结果不可信
- 实际数据中 67 人里有约 15 人记录 <10 条

### 当前方案（三层策略）

```
第 0 层：0 条记录 → 分配默认中等难度练习（easy/medium/hard 各 1/3）
第 1 层：1-4 条记录 → 班级先验 + 个人数据加权（个人权重 = N/5）
第 2 层：5+ 条记录 → 完全使用个人数据
```

### 数学公式

```
barrier_distribution = personal_weight * personal_distribution + (1 - personal_weight) * class_average_distribution

其中 personal_weight = min(N / 5, 1.0)
  N = 该学生的总错误条数
```

### 班级先验的计算

```python
def get_class_average_barrier(class_id):
    查询该班级所有 barriar_type 不为 NULL 的学生
    计算三个维度的算术平均值
    返回分布式 {"concept": 0.40, "reading": 0.35, "expression": 0.25}
```

### 局限性
- 假设新学生接近班级平均水平（可能不成立）
- 贝叶斯先验应该用整个年级而非单一班级（但当前只有一个年级）

### 后续改进
- 用年级平均替代班级平均（样本量更大）
- 引入学科先验知识（如高一学生 concept 障碍通常偏高，因为化学刚开始学）
```

**验证**：
- [ ] `docs/data-loop-design.md` 存在
- [ ] `docs/cold-start-solution.md` 存在
- [ ] 增长数据表完整（1 月-3 月）
- [ ] 三个技术挑战都有展开分析
- [ ] 冷启动方案的数学公式准确

---

### 步骤 6：端到端验证数据闭环

**目标**：模拟一次完整的"学生练习-提交-诊断更新-自适应出题"流程

**提示词**（复制到 Claude Code）：

```
编写一个验证脚本，放在临时位置执行（不创建新文件），验证数据闭环的完整链路。

验证流程（模拟一次完整的学生练习）：

### 1. 初始状态检查
- 查询学生_07 当前 barriar_type（应该为 NULL，因为还没跑诊断）
- 查询学生_07 当前的 student_answers 记录数量

### 2. 模拟提交 5 道题
- 用 POST /api/practice/submit 提交 5 道题的答案数组
- 其中 3 道错误、2 道正确（模拟真实场景）
- 检查 student_answers 表是否新增 5 条记录
- 检查新增记录中的 barriar_type 是否正确分类

### 3. 运行诊断
- 调用 diagnose_barrier("学生_07")
- 检查返回的三维分布
- 检查 students.barrier_type 是否被更新（不再为 NULL）

### 4. 生成自适应练习
- 调用 assign_adaptive_practice("学生_07", question_count=5)
- 检查返回的题数分配是否与障碍分布一致
- 检查每道题的类型是否匹配

### 5. 再次提交（闭环第二圈）
- 模拟学生完成自适应练习后再次提交 5 道题
- 检查 student_answers 新增记录（现在应该共有 1015 条）
- 再次运行 diagnose_barrier("学生_07")
- 检查障碍分布是否有变化（如果新提交的题目中有不同障碍类型，分布应该变化）

### 6. 冷启动验证
- 选一个记录 <5 条的学生
- 验证 diagnose_barrier() 返回 cold_start: true
- 验证分布使用了班级先验

### 7. 班级模式验证
- 调用 diagnose_barrier("1", mode="class")
- 检查返回 34 个学生的诊断结果
- 检查班级汇总分布

输出格式：每个步骤 PASS/FAIL + 关键数据
```

**验证**：
- [ ] 完整 7 步验证全部 PASS
- [ ] 闭环第一圈：提交 → 诊断 → 出题
- [ ] 闭环第二圈：再次提交 → 分布变化
- [ ] 冷启动标记正确
- [ ] 班级模式输出 34 个学生

---

### 步骤 7：生成闭环验证报告

**目标**：将验证结果和关键数据汇总为可交付的验证报告

**提示词**（复制到 Claude Code）：

```
基于上一步的端到端验证输出，生成一份闭环验证报告，保存到 docs/data-loop-verification.md。

报告结构：

## 数据闭环验证报告

### 验证日期
（当前日期）

### 验证范围
- 闭环四节点全部覆盖
- 单学生诊断 + 全班级诊断
- 冷启动策略
- 自适应出题匹配

### 验证环境
- 数据库：SQLite chemai.db（WAL 模式）
- 数据量：初始 1005 条 + 模拟新增 10 条 = 1015 条
- 学生数：67 人

### 验证结果

| 测试项 | 状态 | 关键数据 |
|--------|------|---------|
| 学生提交答案入库 | PASS | 新增 5 条记录，barrier_type 正确分类 |
| 单学生障碍诊断 | PASS | 三维分布 {concept: 0.35, reading: 0.45, expression: 0.20} |
| students.barrier_type 更新 | PASS | 从 NULL → {"concept": 0.35, ...} |
| 自适应出题匹配 | PASS | 5 题中 2 题 reading 类（占比最高），匹配正确 |
| 闭环第二轮 | PASS | 再次提交后分布轻微调整（concept: 0.35→0.33） |
| 冷启动处理 | PASS | 学生_55（3 条记录）标记 cold_start: true |
| 班级模式诊断 | PASS | 34 人诊断完成，班级平均 concept: 0.40, reading: 0.35, expression: 0.25 |

### 数据增长统计

| 操作 | 变化 |
|------|------|
| 初始 student_answers | 1005 条 |
| 闭环第一圈后 | 1010 条 |
| 闭环第二圈后 | 1015 条 |
| 诊断更新次数 | 2 次 |
| barrier_type 更新数 | 1 个学生（从 NULL 到有值） |

### 已知问题
- 诊断准确率约 70%，仍有 30% 的归因可能不准确
- 冷启动学生的诊断置信度为 low
- 小样本学生（<10 条记录）的诊断波动较大

### 结论
数据闭环功能正常，四节点完整链路通过验证。下一步需要种子教师实际试用，验证诊断准确率的用户感知。
```

**验证**：
- [ ] `docs/data-loop-verification.md` 存在
- [ ] 所有验证项都有 PASS/FAIL 状态
- [ ] 数据增长统计有具体数字

---

## 发生了什么（教师参考）

### 1. 数据闭环的核心设计思想

数据闭环不是什么"大数据系统"——它只是保证每次学生答题都在让诊断更准确。这个设计思想的起点来自一个朴素的观察：

在第三轮访谈中，教师说"分数差不多的两个学生，可能一个属于第二类，一个属于第三类"。如果系统只能报告"这个学生答对了几道题、答错了几道题"，那它提供的信息量跟 Excel 统计没区别。

闭环的设计让每一次错误都变成诊断的数据点。1005 条初始数据的诊断准确率只有 60-70%，但每增加一批新数据，准确率就提升一点点。从 1 月到 3 月，student_answers 从 1005 增长到 1680（+67%），准确率从 60% 提升到 70%。

**闭环的真正价值不在数据量增长，而在于诊断的自我改进**——不需要人工标注，不需要模型重新训练，诊断随使用自然提升。

### 2. 三维障碍分类的完整数据流

以下是 diagnose_barrier() 的完整数据流，每一步都在操作具体的表和字段：

```
1. student_answers 表
   └── 查询 is_correct=False AND barrier_type IS NOT NULL 的记录
       └── 统计 concept/reading/expression 各有多少条

2. 冷启动判断
   └── if total_errors < 5:
       ├── personal_weight = total_errors / 5
       ├── class_weight = 1 - personal_weight
       └── barrier_distribution = personal_weight * personal + class_weight * class_avg

3. students 表更新
   ├── students.barrier_type = {"concept": 0.3, "reading": 0.5, "expression": 0.2}
   └── students.barrier_updated_at = datetime.utcnow()

4. assign_adaptive_practice() 选题
   ├── 障碍分布 → 题数分配（concept:2, reading:3, expression:1 → 总共 6 题超出 → 向下取整到 5）
   └── questions 表筛选匹配题目

5. 新的 student_answers 插入
   └── 学生再次作答 → 新数据 → 触发诊断更新 → 循环
```

### 3. 数据增长的完整表格（教师讲解用）

| 指标 | 1 月（初始） | 2 月（内测中） | 3 月（稳定运行） | 增长解读 |
|------|-----------|--------------|----------------|---------|
| student_answers 行数 | 1005 | 1340 | 1680 | 每月新增约 300+ 条，来自种子教师的日常使用 |
| 诊断准确率 | — | ~60% | ~70% | 初始 60%（规则太简单），数据积累后提升到 70% |
| barrier_type JSON 更新次数 | 0 | 45 | 89 | 2 月份诊断功能上线后才开始更新；每次老师查看诊断都触发一次更新 |
| 自适应练习生成次数 | 0 | 12 | 34 | 3 月 growth，教师开始为学生布置自适应练习 |
| 对话 checkpoints | 0 | 0 | 47 | 1-2 月用 MemorySaver（不持久化），3 月 29 日切 AsyncSqliteSaver 后才有 |

**关键转折点：3 月 29 日**

3 月 29 日之前，对话数据不持久化——MemorySaver 只在内存中，服务重启就丢失。3 月 29 日换到 AsyncSqliteSaver 后，对话数据才开始积累。这也是为什么 checkpoints 在 1-2 月都是 0——不是没对话，是对话没存下来。

这个教训表明：**闭环的完整性取决于每个节点都真正在积累数据**。如果某个节点数据丢失（如 MemorySaver），闭环在那个节点就断了。

### 4. 三个技术挑战的深度解析

**挑战 1：障碍分类准确率只有 70%**

这是当前最大的技术限制。三维分类基于规则引擎，判断逻辑是：
- 同一知识点连续错 → concept
- 题干长 → reading
- 书写题 → expression

规则引擎的好处是可解释——教师看到诊断结果，可以追问"为什么判断为 reading？"回答是"因为该学生在题干 ≥200 字符的题目上错误率 60%，在短题干题目上只有 20%。"

但规则引擎的缺陷也很明显：一道题答错可能同时涉及概念和审题。比如一道题干很长、又考了氧化还原反应的题目——学生答错是因为没理解氧化还原？还是没读懂题干？规则引擎只能归到一种类型（当前按优先级：concept > reading > expression）。

**后续方案（LLM 辅助分类）**：
- 定期（如每周）用 DeepSeek 批量分析所有新错题
- LLM 比较"学生答案 vs 正确答案"，判断错误出现在哪个环节
- 将 LLM 的分类结果作为 Gold Label 反馈给规则引擎，修正规则

**为什么不用 LLM 做实时分类？** 因为成本和延迟。每道题提交都调一次 LLM API（1005+ 次调用）既不经济也不必要。规则引擎的 70% 准确率在早期够用——知道"这个学生主要问题是审题"已经能指导教学干预了。

**挑战 2：冷启动问题**

67 名学生中约 15 人答题记录少于 10 条。对于这些学生，基于 3-4 条错误记录的诊断极不稳定——可能今天显示 80% concept，明天新增一条 reading 记录就变成 40% concept。

ChemAI 的当前方案是**贝叶斯修正**：用班级平均分布作为先验，对 1-4 条记录的学生做加权平均。

```python
# 4 条记录学生的计算示例
personal_weight = 4/5 = 0.8    # 个人数据权重 80%
class_weight = 1 - 0.8 = 0.2   # 班级先验权重 20%

# 假设个人数据：3 条 concept, 1 条 reading
personal = {"concept": 0.75, "reading": 0.25, "expression": 0.0}

# 班级先验：{"concept": 0.40, "reading": 0.35, "expression": 0.25}

result = {
    "concept": 0.8 * 0.75 + 0.2 * 0.40 = 0.60 + 0.08 = 0.68
    "reading": 0.8 * 0.25 + 0.2 * 0.35 = 0.20 + 0.07 = 0.27
    "expression": 0.8 * 0.00 + 0.2 * 0.25 = 0.00 + 0.05 = 0.05
}
```

个人数据显示 75% concept，但班级先验拉回了一部分——因为 4 条数据太少了，可能不反映真实分布。这种拉回在统计学上叫 shrinkage（收缩估计）：当数据量不足时，估计值向先验收缩，避免对小样本的过拟合。

**但这个方案的假设可能不成立**：班级平均能代表新学生的先验吗？目前无法验证——需要更多数据。

**挑战 3：小样本过拟合**

15 个学生记录 <10 条。用 5-9 条数据做诊断，本质上是在抛硬币——5 次抛硬币的结果不能告诉你硬币是不是公平的。

当前缓解方案：
1. 贝叶斯修正（班级先验拉回）
2. 对 <5 条记录的学标记为 low confidence
3. 在 assign_adaptive_practice() 中，冷启动学生使用平均分配（三种类型各 1/3），而非严格按比例

**后续方案**：
- 遗忘曲线权重：最近 30 天的错误在诊断中占更高权重（越近越能反映当前状态）
- 学生端"我学会了"按钮：如果学生做了错题本练习后点击了"我学会了"，这会作为正反馈信号，降低该知识点的 concept 权重

### 5. 障碍类型 JSON 的教师端展示设计

`barrier_type` JSON 在 `students` 表中是这样存的：`{"concept": 0.3, "reading": 0.5, "expression": 0.2}`

但这三个数字对教师来说不够直观。教师端的展示逻辑（`frontend/pages/diagnosis.html`）将 JSON 转为三个信息层：

**第一层（快速判断）**：主要障碍类型。如果 reading 最高 → "该生主要障碍：审题"。教师看到这个就知道：不需要重讲知识点，需要训练审题。

**第二层（详细分布）**：三个维度的进度条/饼图。为什么是进度条而不是百分比文本？因为教师说了"我扫一眼就要能判断"——视觉化的分布比数字更容易快速理解。

**第三层（行动建议）**：基于障碍类型的教学建议。
- concept 为主 → "建议针对氧化还原反应和离子反应做专项讲解"
- reading 为主 → "建议安排审题训练——先让学生在试卷上圈出关键条件再作答"
- expression 为主 → "建议强调化学方程式书写规范，特别注意配平步骤"

这三层信息全部由 `diagnose_barrier()` 生成，前端只负责渲染。

### 6. 经常出现的问题

**Q：diagnose_barrier() 跑完为什么准确率只有 70%？能到 90% 吗？**
A：70% 是规则引擎的上限。规则引擎只能根据"连续错""题干长""书写题"做粗分类，它不理解题目的具体内容。要知道学生到底是"不知道配平规则"还是"知道但算错了"，需要 LLM 对比学生答案 vs 正确答案。后续计划用 DeepSeek 做批量分析（不是实时），目标 85%+。

**Q：冷启动用班级平均做先验——如果整个班级都没数据呢？**
A：目前不存在这个问题，因为初始数据有 1005 条、全班 67 人都有记录。但如果扩展到新学校，确实是问题。到时候三层回退：班级平均 → 年级平均 → 学科普遍先验（如高一学生 concept 障碍通常偏高，因为化学刚开始学）。

**Q：闭环的"自适应"体现在哪？**
A：区别于"统一布置"（所有学生做同样的题），`assign_adaptive_practice()` 根据每个学生的障碍类型分配不同比例的题型。reading 障碍的学生收到更多长题干题目，expression 障碍的学生收到更多书写题，concept 障碍的学生收到该知识点的基础概念题。练习不是难度的自适应，是**障碍类型的自适应**。

### 7. 真实开发记录还原

以下是 2026 年 2-3 月数据闭环功能开发的真实操作记录：

```
2 月 20 日
- 实现 diagnose_barrier() 函数初版（agent/tools.py:191）
- 规则引擎：三种障碍类型的简单分类
- 第一次用 1005 条数据跑诊断：准确率约 60%
- 教师反馈："大致对，但这个学生我知道他是概念问题，系统说是 reading" → 规则需要调整

2 月 25 日
- 调整规则优先级：concept > reading > expression
- 新增 continuous_errors 字段到 student_answers
- 准确率提升到约 65%

3 月 5 日
- 实现 assign_adaptive_practice() 初版
- 按障碍比例分配题型（而非按难度）
- 教师反馈："reading 的题确实看题用了更多时间，这个方向对的"

3 月 15 日
- 新增冷启动处理逻辑（<5 条记录的贝叶斯修正）
- 新增 get_class_average_barrier() 辅助函数

3 月 29 日
- MemorySaver → AsyncSqliteSaver 切换
- 对话数据开始持久化（对话闭环建立）
- checkpoints 从 0 开始增长

4 月 1-5 日
- 后测：1680 条数据跑诊断，准确率约 70%
- 教师反馈："比之前准了，但仍有个别学生不准——比如基础好但粗心的学生被标记为 concept"
- 下一步：LLM 辅助精细分类
```

---

## 课后产出检查

学生应该同时具备：

- [ ] `agent/tools.py` 含 `diagnose_barrier()` 函数（支持单学生和班级模式）
- [ ] `agent/tools.py` 含 `assign_adaptive_practice()` 函数（按障碍类型匹配题目）
- [ ] `agent/tools.py` 含 `classify_single_answer_barrier()` 和 `get_class_average_barrier()` 辅助函数
- [ ] `app/api/practice.py` 含 `POST /api/practice/submit` 接口（闭环数据入口）
- [ ] `docs/data-loop-design.md` 含完整闭环设计（四节点流程 + 增长数据 + 三技术挑战）
- [ ] `docs/cold-start-solution.md` 含冷启动处理方案（三层策略 + 数学公式）
- [ ] `docs/data-loop-verification.md` 含闭环验证报告（全部 PASS）
- [ ] `students` 表中至少 1 个学生的 `barrier_type` 从 NULL 变为有实际数据
- [ ] 端到端验证通过（提交 → 诊断 → 出题 → 再提交 → 分布变化）

**下节课需要**：数据闭环就绪，`diagnose_barrier()` 函数可用。Session 16 将进行测试调优与 Bug 修复实战（从 15 个真实 bug 中修复 5 个代表性 bug + 性能基准测试）。

---

## 补充内容 — 教师深度参考

### classify_single_answer_barrier() 的规则引擎详表

| 检测顺序 | 规则 | 判定为 | 理由 | 优先级 |
|---------|------|--------|------|--------|
| 1 | 同一学生在同一知识点的题目上连续错 ≥2 次 | concept | 如果同一知识点的不同题目都错，说明知识点没掌握，不是偶然失误 | 最高 |
| 2 | 题干长度 ≥200 字符 | reading | 长题干对 90+ 人大班学生的审题要求更高（来源：教师反馈"有些学生你把题给他读一遍他就会了"） | 中 |
| 3 | 题目类型为 fill 或 short_answer | expression | 书写题丢分往往是"知道但写不对"（来源：教师反馈"他懂了，但方程式写不对"） | 中 |
| 4 | 以上都不满足 | 按默认比例随机分配 (40/35/25) | 作为回退策略，分布接近班级平均 | 最低 |

### 冷启动三层策略的数学推导

```
第 0 层：N=0（无记录）→ 不调用 diagnose_barrier()，分配默认练习（easy/medium/hard 各 1/3）
第 1 层：N=1~4（少量记录）→ barrier_distribution = (N/5) * personal + (1-N/5) * class_avg
第 2 层：N≥5（足够记录）→ barrier_distribution = personal_distribution
```

为什么阈值选 5？
- 5 是统计上最小可接受样本量（低于 5 条的分布无法做任何推断）
- 实际数据中，绝大多数学生（52/67 = 78%）有 ≥10 条记录，5 条阈值不伤害大多数学生的诊断质量
- 5 条规则的来源：教师反馈"你看他错了一次两次不能下结论，错到四五次就看得出苗头了"

### 贝叶斯修正的直觉理解

冷启动的贝叶斯修正本质上就是在说："你对这个学生的了解很少，所以不要对他做过强的推断。用全班平均做个参考，随着你了解越多，你自己的判断越来越重要。"

这不是一个完美的统计方法（理想的贝叶斯估计需要先验分布和后验分布，这里简化为了加权平均），但它在工程上是现实的折中——够用、可解释、不需要额外的统计库。

### 对话数据闭环的教训

3 月 29 日之前，对话数据是不闭环的。MemorySaver 只在内存中存对话状态，服务重启就全丢。教师反馈说"上次问过的内容又要重新问一遍"——虽然答题数据的闭环是完整的，但对话数据的闭环是断裂的。

3 月 29 日切换到 AsyncSqliteSaver 后，对话持久化到 `chemai_checkpoints.db`。这让 Agent 能记住之前的对话上下文——教师上次问过的氧化还原反应考点分析，下次打开时还在。

这个教训的普适性：**数据闭环不仅适用于答题数据，也适用于对话数据。任何"用户输入 → 系统处理 → 用户再次输入"的流程，都应该考虑闭环。**

### 1 月-3 月数据增长的趋势分析

```
student_answers 增长：
  1 月 1005（初始导入的学校月考数据）
  2 月 1340（+335，每月约 300 条，来自种子教师的日常使用）
  3 月 1680（+340，增长稳定）

诊断准确率提升：
  2 月 60%（第一次跑，规则太简单）
  2 月 65%（调整规则优先级后）
  3 月 70%（累积 1680 条数据 + 规则调优）

barrier_type 更新次数：
  1 月 0（功能未上线）
  2 月 45（每次教师查看诊断触发一次，每周约 11 次）
  3 月 89（增长，月均约 22 次）

自适应练习：
  2 月 12 次（教师刚开始试用，对学生端持观望态度）
  3 月 34 次（增长明显——教师开始信任自适应分配的结果）
```

这些数据的价值在于：它们不是预测，是**种子教师真实使用产生的**。每增加一条 student_answers 记录，诊断就准一点——不用跑 A/B 测试，不用做统计显著，数据在真实使用中自然积累。

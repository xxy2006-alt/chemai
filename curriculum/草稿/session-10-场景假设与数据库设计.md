# Session 10 · 场景假设与数据库设计

## 产出物

- `chemai-backend/app/models/` 目录，含 `database.py` 和 `models.py`
- SQLite 数据库，14 个表完整建立
- `app/models/database.py` — 数据库连接和会话管理（WAL 模式）
- `app/models/models.py` — 所有 14 个表的 SQLAlchemy ORM 模型
- `app/utils/init_db.py` — 数据库初始化脚本（67 名学生 + 1005 条答题记录）
- `docs/database-schema.md` — 完整数据库 schema 文档（14 个表，每个字段有注释）
- `docs/scenario-spec-v1.md` — 6 个核心场景的完整拆解文档
- `chemai.db` — 初始化后的 SQLite 数据库文件（约 4.5MB）

## 前置条件

- Session 3 的 JTBD 矩阵和 Session 6 的 PRD 文档就绪
- `chemai-backend/` 项目目录完整可用
- Python 3.11 已安装，venv 已激活
- `pip list` 确认 sqlalchemy 和 aiosqlite 已安装（Session 1 装了）

## 项目背景（给学生的概述）

Session 3 你通过三轮角色扮演访谈理解了用户，Session 6-7 你完成了 PRD 编写和原型设计。这节课要做的是把理解**翻译成数据结构**。

数据库设计不是"先画 ER 图再建表"——在 ChemAI 项目中，表结构是 JTBD 矩阵一层层推导出来的。比如 `students` 表有个 `barrier_type` 字段，类型是 JSON，存的是 `{"concept": 0.3, "reading": 0.5, "expression": 0.2}`。这个字段不是拍脑袋出来的——它来自第三轮访谈中教师的一句原话："分数差不多的两个学生，可能一个属于第二类，一个属于第三类。"

同样，`student_answers` 表不只是存"学生答对还是答错"，还存了 `barrier_type`（这道题暴露了什么障碍）和 `consecutive_errors`（这个知识点上连续错了几次）。因为 JTBD-J6 要求"识别学生真实障碍类型"，如果只存分数，诊断就无从下手。

这节课还有一个关键任务：场景假设。在写第一行数据库代码之前，你需要先定义好"用户在什么情况下、做什么事、期待什么结果"——这就是场景假设。ChemAI 定义了 6 个核心场景，全部来自用户访谈中描述的真实行为。

---

## 操作步骤

### 步骤 1：分析 JTBD 矩阵，推导数据库需求

**目标**：从 JTBD 矩阵中提取所有需要存储的数据实体，输出数据需求清单

**提示词**（复制到 Claude Code）：

```
读取 docs/jtbd-matrix.md，分析其中的 12 项 JTBD（7 功能 + 2 社交 + 3 情感），从中推导出需要存储的数据实体。

对于每项功能 JTBD（J1-J7），回答三个问题：
- 这个 Job 需要存储什么数据？
- 这些数据之间有什么关系？
- 哪些字段对实现这个 Job 是必须的？

输出一份数据需求清单，格式如下：

## 数据需求清单

### 实体 1：教师（teachers）
- 来源 JTBD：J1, J2, J3, J4（多个 Job 都需要教师身份）
- 需要字段：姓名、学校、任教班级、周课时、...
- 数据关系：一个教师 → 多个班级 → 多个学生

### 实体 2：学生（students）
- 来源 JTBD：J1, J4, J6, J7, J10
- 需要字段：姓名、班级、barrier_type（三维障碍分布 JSON）...
- 需要理由：barrier_type 来自 JTBD-J6 "识别学生真实障碍类型"，用户原话"分数差不多的两个学生，可能一个属于第二类一个属于第三类"——因此不能只存分数，必须存三维分类

...（继续列出所有需要的实体）

### 实体 3-10（自行推导）

要求：
- 每个实体都要明确它服务于哪个 JTBD
- 对 barriar_type JSON 字段的设计给出专门的理由说明
- 输出到 docs/data-requirement.md
```

**验证**：
- [ ] `docs/data-requirement.md` 存在
- [ ] 至少识别出 10 个以上数据实体
- [ ] 每个实体都追溯到了具体的 JTBD
- [ ] barrier_type JSON 字段有专门的设计理由

---

### 步骤 2：创建 SQLAlchemy ORM 模型（14 个表）

**目标**：在 `app/models/models.py` 中创建所有 14 个表的 SQLAlchemy 模型

**提示词**（复制到 Claude Code）：

```
在 chemai-backend 项目里创建数据库模型文件。先创建目录 app/models/ （含 __init__.py），然后创建 app/models/models.py。

models.py 中需要定义以下 14 个 SQLAlchemy ORM 模型。注意：这是 ChemAI 的真实数据库结构，每个表的字段都是经过 JTBD 推导的，不能随意增减。

表结构如下（字段名用英文，注释用中文）：

## 1. accounts 表 — 登录认证
- id: Integer, primary_key
- username: String, unique, index
- password_hash: String
- role: String（teacher / student / parent）
- created_at: DateTime, default=utcnow

## 2. teachers 表 — 教师信息
- id: Integer, primary_key
- account_id: Integer, ForeignKey('accounts.id')
- name: String
- school: String（学校名称，统一用"湖南某重点高中"）
- phone: String, nullable
- subject: String, default='chemistry'
- created_at: DateTime

## 3. students 表 — 学生信息（含障碍诊断）
- id: Integer, primary_key
- account_id: Integer, ForeignKey('accounts.id'), nullable
- name: String
- class_id: Integer, ForeignKey('classes.id')
- barrier_type: JSON, nullable（关键字段！存储三维障碍分布，如 {"concept": 0.3, "reading": 0.5, "expression": 0.2}）
- barrier_updated_at: DateTime, nullable
- created_at: DateTime

## 4. classes 表 — 班级
- id: Integer, primary_key
- name: String
- grade: String（如"高一"）
- school_id: Integer, ForeignKey('schools.id'), nullable

## 5. teacher_class_subject 表 — 教师-班级-科目关联
- id: Integer, primary_key
- teacher_id: Integer, ForeignKey('teachers.id')
- class_id: Integer, ForeignKey('classes.id')
- subject: String, default='chemistry'

## 6. exam_records 表 — 考试记录
- id: Integer, primary_key
- class_id: Integer, ForeignKey('classes.id')
- exam_name: String（如"2026年1月月考"）
- exam_date: DateTime
- total_score: Integer
- created_by: Integer, ForeignKey('teachers.id')

## 7. questions 表 — 题目
- id: Integer, primary_key
- content: Text（题目正文）
- answer: String（正确答案）
- analysis: Text, nullable（解析）
- knowledge_points: JSON（知识点标签，如 ["氧化还原反应", "电子转移"]）
- difficulty: String（easy/medium/hard）
- source: String, nullable（题目来源，如"2025湖南高考真题"）
- question_type: String（choice/fill/short_answer/calculation）
- created_at: DateTime

## 8. student_answers 表 — 学生答题记录
- id: Integer, primary_key
- student_id: Integer, ForeignKey('students.id')
- question_id: Integer, ForeignKey('questions.id')
- exam_record_id: Integer, ForeignKey('exam_records.id'), nullable
- student_answer: String（学生填的答案）
- is_correct: Boolean
- barrier_type: String, nullable（这道题暴露的障碍类型：concept/reading/expression，由诊断算法自动判定）
- consecutive_errors: Integer, default=0（该知识点连续错误次数）
- answered_at: DateTime

## 9. student_submissions 表 — 答题卡扫描提交
- id: Integer, primary_key
- student_id: Integer, ForeignKey('students.id')
- upload_session_id: Integer, ForeignKey('upload_sessions.id')
- submitted_at: DateTime

## 10. upload_sessions 表 — OCR 上传会话
- id: Integer, primary_key
- uploaded_by: Integer, ForeignKey('teachers.id')
- file_name: String
- file_data: LargeBinary（PDF 文件内容）
- status: String（pending/processing/done/error）
- created_at: DateTime

## 11. question_sets 表 — AI 生成的题库集合
- id: Integer, primary_key
- name: String
- created_by: Integer, ForeignKey('teachers.id')
- question_ids: JSON（如 [1, 4, 7, 12]）
- created_at: DateTime

## 12. schools 表 — 学校信息
- id: Integer, primary_key
- name: String
- city: String
- created_at: DateTime

## 13. parents 表 — 家长
- id: Integer, primary_key
- account_id: Integer, ForeignKey('accounts.id')
- name: String
- phone: String, nullable

## 14. parent_notifications 表 — 家长通知
- id: Integer, primary_key
- parent_id: Integer, ForeignKey('parents.id')
- student_id: Integer, ForeignKey('students.id')
- message: Text
- is_read: Boolean, default=False
- created_at: DateTime

实现要求：
1. 使用 SQLAlchemy 的 declarative_base() 创建 Base
2. 每个模型继承 Base
3. __tablename__ 使用上述小写表名
4. 字段类型正确使用：Integer, String, Text, Boolean, DateTime, JSON, LargeBinary
5. 所有 ForeignKey 正确引用
6. 注释准确（中文注释说明字段用途）
7. 文件头部导入 SQLAlchemy 必要模块
```

**验证**：
- [ ] `app/models/models.py` 存在，含 14 个 ORM 模型
- [ ] 每个表都有 `__tablename__`
- [ ] ForeignKey 关系正确
- [ ] `students.barrier_type` 字段类型为 JSON
- [ ] 所有字段都有中文注释

---

### 步骤 3：创建数据库连接管理

**目标**：在 `app/models/database.py` 中创建数据库引擎和会话管理，启用 WAL 模式

**提示词**（复制到 Claude Code）：

```
创建 app/models/database.py，实现 SQLite 数据库连接管理。

要求：

1. 从 app.core.config 导入配置
2. 使用 sqlalchemy 的 create_engine() 创建 SQLite 引擎：
   - 数据库文件路径：项目根目录下的 chemai.db
   - 连接参数：check_same_thread=False（FastAPI 多线程需要）
   - echo=False（不打印 SQL 日志）

3. 使用 sessionmaker 创建 SessionLocal（autocommit=False, autoflush=False）

4. 实现 get_db() 依赖注入函数：
   - yield SessionLocal()
   - finally 中 close()

5. 实现 init_db() 函数：
   - 从 app.models.models 导入 Base
   - 调用 Base.metadata.create_all(bind=engine) 创建所有表
   - 创建完成后执行 PRAGMA journal_mode=WAL（启用 WAL 模式，提升并发写入性能）
   - 打印 "数据库初始化完成，14个表已创建，WAL模式已启用"

6. 在 if __name__ == "__main__" 块中调用 init_db()

7. 确保 app/models/__init__.py 存在（可以留空）

WAL 模式的选择理由（写在代码注释中）：
SQLite 默认是 DELETE 模式（写操作串行）。WAL（Write-Ahead Logging）模式下读写不互斥，
多个学生同时提交答案时不会因为写锁导致请求排队。对于 ChemAI 的用户规模（<200人），
WAL 模式足够，不需要 PostgreSQL。
```

**验证**：
- [ ] `app/models/database.py` 存在
- [ ] `python app/models/database.py` 执行无报错
- [ ] 项目根目录生成 `chemai.db` 文件
- [ ] 控制台打印"数据库初始化完成，14个表已创建，WAL模式已启用"

---

### 步骤 4：编写数据初始化脚本（init_db.py）

**目标**：创建 `app/utils/init_db.py`，插入 67 名学生和 1005 条答题记录

**提示词**（复制到 Claude Code）：

```
创建 app/utils/ 目录（如果不存在），然后创建 app/utils/init_db.py。

这个脚本用于初始化数据库演示数据——插入 67 名学生和 1005 条模拟答题记录。数据量和结构来自真实的项目初期状态。

init_db.py 需要做的事情：

## 第一部分：基础数据插入

1. 插入 1 所学校（schools 表）：
   - name: "湖南某重点高中"
   - city: "湖南"

2. 插入 1 个教师账号 + 教师记录（accounts 表 + teachers 表）：
   - username: "teacher1"
   - password_hash: 用 hashlib.sha256("123456".encode()).hexdigest()
   - role: "teacher"
   - name: "张老师"（使用化名，不暴露真实姓名）

3. 插入 2 个班级（classes 表）：
   - 高一(1)班、高一(2)班

4. 插入教师-班级关联（teacher_class_subject 表）

## 第二部分：批量插入 67 名学生

5. 插入 67 名学生（students 表）：
   - 格式：姓名用"学生_01"到"学生_67"
   - 前 34 人分配 class_id=1，后 33 人分配 class_id=2
   - account_id 设为 NULL（学生不登录系统，通过教师端管理）
   - barrier_type 初始为 NULL（等答题记录积累后再跑诊断）

## 第三部分：批量插入 1005 条答题记录

6. 模拟 1005 条答题记录（student_answers 表）：
   - 平均每个学生约 15 条记录
   - is_correct：约 60% 正确（随机但不完全随机——真实场景下正确率不会太低）
   - barrier_type 使用以下策略赋值（关键逻辑）：
     - 如果 is_correct=True → barrier_type=None
     - 如果 is_correct=False → 按比例分配 barrier_type：
       - 40% concept（同一知识点反复错——通过给同一 student 在相邻 question_id 上都标记 concept 来模拟）
       - 35% reading（题干较长的题目标记为 reading）
       - 25% expression（涉及方程式书写的题目标记为 expression）
   - consecutive_errors：同一 student 的同一知识点连续错误次数（1-5 之间）
   - answered_at：分布在 2025 年 9 月到 2026 年 1 月之间

7. 模拟 20 道题目到 questions 表：
   - 内容覆盖化学六大板块：氧化还原、离子反应、元素周期律、化学平衡、有机化学、电化学
   - knowledge_points 用 JSON 数组存储
   - difficulty 分布在 easy/medium/hard
   - question_type 以 choice 为主（因为选择题是月考和高考的主要题型）

## 技术要求

- 使用 SessionLocal() 管理数据库会话
- 使用 bulk_insert_mappings 或 add_all 提升插入性能
- 每插入一批数据后 commit() 一次
- 脚本结束时打印统计信息：插入了多少条数据
- 使用随机种子 random.seed(42) 保证数据可复现

## 分层插入顺序

```
schools (1 行)
  → accounts (1 行)
    → teachers (1 行)
      → classes (2 行)
        → teacher_class_subject (2 行)
          → students (67 行)
            → questions (20 行)
              → student_answers (1005 行)
```

运行方式：在项目根目录下运行 python app/utils/init_db.py
```

**验证**：
- [ ] `app/utils/init_db.py` 存在
- [ ] `python app/utils/init_db.py` 执行无报错
- [ ] 控制台显示最终统计：schools: 1, teachers: 1, classes: 2, students: 67, questions: 20, student_answers: 1005
- [ ] 数据可复现（`random.seed(42)` 保证）

---

### 步骤 5：生成数据库 schema 文档

**目标**：生成一份完整可读的数据库设计文档

**提示词**（复制到 Claude Code）：

```
读取 app/models/models.py，生成一份数据库 schema 文档，输出到 docs/database-schema.md。

文档结构：

## 数据库概述
- 引擎：SQLite（单文件 chemai.db）
- 模式：WAL（Write-Ahead Logging）
- 表数量：14
- 选用 SQLite 的四大硬约束：
  1. Windows 单机部署，没有运维人员
  2. 用户量 <200 人，数据量 <10MB
  3. chemai.db 一个文件就能备份/迁移
  4. FastAPI 的 SQLAlchemy + SQLite 零配置启动

## 表结构详情

### 表 1：accounts
- 用途：
- 关键字段：
- 索引：
- SQL DDL：

### 表 2：teachers
- 用途：
- 关键字段：
- 外键：
- SQL DDL：

...（14 个表逐一描述）

### 表 3：students（重点说明）
- 用途：学生信息 + 障碍诊断结果存储
- barriar_type 字段设计理由（详细展开）：
  引用用户原话："分数差不多的两个学生，可能一个属于第二类，一个属于第三类"
  如果 students 表只存分数排名，无法区分"错在同一原因"和"错在不同原因"的学生。
  barriar_type JSON 字段存的是三维分布比例，比如 {"concept": 0.3, "reading": 0.5, "expression": 0.2}，
  教师看到就能知道这个学生 50% 的错误来自审题问题——不是不会，是没好好看题。
- SQL DDL：

（继续描述表 4-14）

## ER 关系图（用 ASCII 文字画）

## 关键设计决策

### 决策 1：为什么用 JSON 存 barriar_type 而不是三个独立字段？
（详细说明：JSON 的好处是可以扩展维度，不需要 ALTER TABLE；坏处是 SQLite 不能对 JSON 字段做索引查询。但对于 <200 人的数据量，全表扫描 JSON 解析的耗时在毫秒级，可接受。）

### 决策 2：为什么 student_answers 也存 barriar_type？
（因为诊断需要知道"每道题暴露了什么障碍"，而不是只知道"答对还是答错"。这个字段是后来加上去的——最初设计只存了 is_correct，发现无法做三维分类后才加的。）

### 决策 3：为什么用 LargeBinary 存 PDF 而不是存文件路径？
（文件路径在 Windows 和 Linux 之间不兼容，大型二进制在 SQLite 中直接存储更方便单文件备份。但 4.5MB 的数据库包含了 PDF 后会显著增大，后续可能需要拆分为文件存储。）

### 决策 4：为什么 accounts 和 teachers/students/parents 分表？
（单一职责：accounts 管认证，teachers/students/parents 管业务。这样改密码不影响业务表，加新的用户类型（如管理员）不需要改 accounts 表结构。）
```

**验证**：
- [ ] `docs/database-schema.md` 存在
- [ ] 14 个表都有完整描述
- [ ] barrier_type 设计理由有详细展开
- [ ] 4 大设计决策都有说明
- [ ] 包含 ER 关系图

---

### 步骤 6：写入 6 个核心场景的完整拆解文档

**目标**：基于 JTBD 矩阵和数据库 schema，生成 6 个核心场景的完整拆解

**提示词**（复制到 Claude Code）：

```
读取 docs/jtbd-matrix.md 和 docs/prd-v1.0.md，以及 app/models/models.py。

生成 6 个核心场景的完整拆解文档，输出到 docs/scenario-spec-v1.md。

每个场景的格式必须包含以下 5 个部分：

## 场景 N：场景名称

### 用户原话
（从访谈记录中引用的真实原话，标注来自第几轮访谈）

### 场景假设
- When（什么时候触发）
- Who（谁在操作）
- What（具体做什么——详细到步骤级别）
- Pain（痛点——为什么现在的做法让人痛苦）
- Expect（期望——用户希望得到什么结果）

### 对应实现
- 涉及的数据库表/字段
- 涉及的 API 接口
- 涉及的服务/工具函数

### 验证数据
- 用什么数据验证场景是否正确实现
- 预期结果是什么

---

## 6 个场景的具体内容（每个场景都需要展开到这一步）：

### 场景 1：月考后错题统计
- 用户原话："每次月考完我要花一个半小时在那数哪道题多少人错"
- 场景假设：考试结束 2 小时内，教师在办公室用 Excel 逐题统计错题人数和知识点分布
- 对应实现：app/api/exam.py:get_exam_results() + student_answers.is_correct + questions.knowledge_points
- 验证数据：用 1005 条 student_answers 数据查询班级级别错题分布，验证是否能输出按知识点聚合的报告

### 场景 2：AI 出题 + 安全审核
- 用户原话："用了 AI 出题还是要我自己全做一遍验题，那不如我自己出。"
- 场景假设：准备月考/单元测试卷时，教师用 AI 生成 10-15 道题，需要逐题验证系数/条件/产物
- 对应实现：agent/tools.py:chemical_balance + app/services/chemical_balance.py + auditDims 四维审核
- 验证数据：用 20 道模拟题目测试 chemical_balance，检查四维审核是否每一维都覆盖

### 场景 3：学生障碍类型诊断
- 用户原话："分数差不多的两个学生，可能一个属于第二类，一个属于第三类。"
- 场景假设：考试后教师不再只看分数排名，而是看每个学生的三维障碍分布
- 对应实现：agent/tools.py:diagnose_barrier() + students.barrier_type JSON 字段
- 验证数据：用 1005 条答题记录跑诊断，验证输出是否为三维分布比例

### 场景 4：学生自主练习
- 用户原话："班里十几二十个学生明显跟不上，不是他们不聪明。"
- 场景假设：课后/周末，学生在手机上看到教师布置的练习，逐题作答、查看结果、复习错题
- 对应实现：frontend/m/practice.html + GET /api/practice/student/{id}/tasks + POST /api/practice/submit
- 验证数据：模拟一个学生完成一次练习（5-10 题），验证 student_answers 表新增记录正确

### 场景 5：变种真题生成
- 用户原话（教导主任）："能不能把历年真题改成不同版本让学生练？"
- 场景假设：教导主任推动，教师选一道真题为蓝本 → AI 生成 3-5 个变种 → 教师审核确认等价性
- 对应实现：agent/tools.py:generate_questions(variant_source=qid)
- 技术约束：四条红线——方程式系数、反应条件、产物、知识点不能变
- 验证数据：选一道真题生成 3 个变种，逐条比对四条红线是否被违反

### 场景 6：教师通过 AI 对话获取教研信息
- 用户原话："请讲解氧化还原反应"→ 期望得到考点分布、学生常见误区、教学策略
- 场景假设：备课阶段，教师通过 AI 对话获取结构化教研信息，不想被当成学生来教
- 对应实现：agent/tools.py:chemistry_tutor(persona="teacher") + agent/langgraph_agent.py:_current_persona
- 验证数据：模拟教师提问，验证 Persona 流转是否走到教研分支（而非学生辅导分支）

---

要求：
- 每个场景的"场景假设"部分要详细到步骤级别——不只是"教师要出题"，而是"教师打开出题页面 → 选择出题类型 → 输入考点 → AI 生成 3 道题 → 教师逐道审核 → 保存到题库"
- 不准暴露学校真实名称
- 用户原话必须标注来自第几轮访谈
- 总文档 5000 字以上
```

**验证**：
- [ ] `docs/scenario-spec-v1.md` 存在
- [ ] 6 个场景全部展开，每个 5 部分完整
- [ ] 用户原话都标注了访谈轮次
- [ ] 每个场景都有验证数据描述

---

### 步骤 7：验证数据库完整性和数据初始化脚本

**目标**：确认 14 个表全部创建成功，1005 条数据正确插入

**提示词**（复制到 Claude Code）：

```
执行以下验证步骤：

1. 确认 chemai.db 文件存在且大小 > 1MB
2. 用 Python 脚本验证所有表：
   - 从 app.models.database 导入 SessionLocal
   - 从 sqlalchemy 导入 inspect
   - 获取所有表名列表，验证是否恰好 14 个
   - 输出所有表名和每个表中的行数

验证脚本伪代码：
```
from app.models.database import SessionLocal, engine
from sqlalchemy import inspect, text

inspector = inspect(engine)
tables = inspector.get_table_names()
print(f"表数量：{len(tables)}")
print(f"表列表：{tables}")

with SessionLocal() as db:
    for table in tables:
        count = db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
        print(f"  {table}: {count} 行")
```

预期输出：
表数量：14
表列表：['accounts', 'classes', 'exam_records', ...]
  accounts: 1 行
  teachers: 1 行
  students: 67 行
  classes: 2 行
  questions: 20 行
  student_answers: 1005 行

3. 验证 barriar_type 字段：
   - 查询 student_answers 表中 barriar_type 不为 NULL 的记录数量
   - 统计三种类型（concept/reading/expression）的分布
   - 查询 students 表中有 barriar_type 数据的记录（当前应为 0，因为还没跑诊断）

4. 验证 WAL 模式：
   - 执行 PRAGMA journal_mode 返回 'wal'
```

**验证**：
- [ ] 14 个表全部存在
- [ ] students 表 67 行
- [ ] student_answers 表 1005 行
- [ ] barriar_type 分布合理（约 40/35/25）
- [ ] WAL 模式已启用
- [ ] 数据库大小约 4.5MB 左右

---

## 发生了什么（教师参考）

### 1. SQLite 的选择：不是"够用"，是"最优"

很多学生会问：为什么用 SQLite 而不是 MySQL 或 PostgreSQL？

ChemAI 选 SQLite 不是因为它简单——是因为在给定的约束条件下，它是**最优解**。四个硬约束缺一不可：

| 约束 | 解释 | 为什么 SQLite 是最优的 |
|------|------|----------------------|
| Windows 单机部署 | 学校没有服务器，教师只用自己办公电脑 | PostgreSQL 需要安装、配置、启动守护进程；SQLite 只需要一个文件 |
| 用户量 <200 人 | 2 个班 × 90 人 = 180 人，加上教师和家长也不到 200 | PostgreSQL 的连接池和并发优化在此规模下没有价值 |
| 数据量 <10MB | 1005 条答题记录，每条约 500 字节，总计约 500KB | SQLite 单文件性能在此数据量下完全不受影响 |
| 单文件备份/迁移 | 教师可能换电脑，需要能直接拷贝 | `chemai.db` 一个文件拷走即完成备份，不需要 mysqldump |

**WAL 模式的选择**：SQLite 默认是 DELETE 模式（写操作互斥锁）。启用 WAL（Write-Ahead Logging）后，读写不互斥——多个学生同时提交答案时不会排队。对于 90+ 人的班级同时在线练习，WAL 模式足够了。

### 2. barrier_type JSON 字段的设计逻辑

这是整个数据库设计中最关键的一个字段。它的设计直接来自访谈发现，经历了两次迭代。

**迭代 0（未实现的想法）**：最初想用三个独立的 Float 字段 `concept_score / reading_score / expression_score`。这样设计的好处是 SQLite 可以对这些字段做索引查询，坏处是：如果未来加了第四维度（比如"计算能力"），需要 ALTER TABLE。对于单机部署场景，ALTER TABLE 的风险比全表扫描大得多。

**迭代 1（当前方案）**：用 JSON 字段 `barriar_type`，存储 `{"concept": 0.3, "reading": 0.5, "expression": 0.2}`。好处是无限可扩展维度，坏处是 SQLite 的 JSON 查询不走索引。但 <200 人的数据量，全表扫描耗时在毫秒级——这个"坏处"实际上不存在。

**为什么 field-level 命名不是"score"而是"type"？** 因为 `barriar_type` 的语义是"这个学生的主要障碍类型是什么"，不是"这个学生在某个维度得了多少分"。教师在访谈中说的是"可能一个属于第二类，一个属于第三类"——她需要的是一个分类标签，不是连续分数。

**关键原话的语境**（来自第三轮访谈）：

采访者："如果 AI 帮你分析每个学生为什么错，你觉得它应该怎么分类？"

教师："分数差不多的两个学生，有些是知识点没懂——你跟他讲一遍他就会了。有些是题目没读懂——题干太长他不知道在问什么，你帮他把题读一遍他就会了。还有一种——他懂了、读懂了，但是写不对，化学方程式配不平。这三种你要怎么帮是不一样的。"

这段话是 `barriar_type` 的三维分类（concept / reading / expression）的直接来源。

### 3. student_answers 表也存 barrier_type：为什么？

这个问题在项目中引起过争论。`students` 表已经有 `barriar_type` 了，为什么 `student_answers` 表还要存？

答案是：**粒度不同**。

- `students.barrier_type` 是聚合后的分布比（基于该学生所有错题的统计结果）
- `student_answers.barrier_type` 是单道题的障碍判定（这道错题暴露了什么问题）

就像全班平均分不能替代每个人的分数，聚合后的障碍分布也不能替代每道题的障碍判定。`diagnose_barrier()` 函数需要遍历 `student_answers` 表中每条错误记录——它需要知道"这道题被判定为什么类型的障碍"，才能聚合出分布。

**实际教训**：这个字段是项目中第二次迭代加上去的。最初 `student_answers` 只存了 `is_correct`，后来发现诊断时还需要知道每道错题的错误模式（是概念题错了还是阅读题错了），才加了 `barriar_type` 和 `consecutive_errors` 两个字段。

### 4. 6 个场景的完整拆解（教师讲解用）

以下是 6 个核心场景的完整拆解，每个都有用户原话、场景假设、对应实现、验证数据：

**场景 1：月考后错题统计**

- 用户原话："每次月考完我要花一个半小时在那数哪道题多少人错"（第一轮）
- 场景假设：每次月考/期中/期末考试结束后 2 小时内，化学教师独自在办公室，打开 Excel，对着答题卡一张张统计——哪道题错了多少人、哪个知识点高频出错。这个过程纯属重复劳动，占用了本该用来备课的时间。"没有人知道我做得多辛苦"——没有认可感。
- 对应实现：`app/api/exam.py:get_exam_results(exam_id)` 从 `student_answers` 表查询 `is_correct=False` 的记录，GROUP BY `question_id` 统计错误数，JOIN `questions.knowledge_points` 按知识点聚合。统计逻辑在 `app/api/exam.py:226-265`，返回 `question_results` 含每道题的正确/错误人数。
- 验证数据：用 1005 条 student_answers 初始化数据，查询某一班级的错题分布，验证：
  - 每道题的错误人数是否正确
  - 知识点聚合是否正确
  - 报告能否在 5 秒内生成（而非 1.5 小时）

**场景 2：AI 出题 + 安全审核**

- 用户原话："用了 AI 出题还是要我自己全做一遍验题，那不如我自己出。"（第二轮）
- 场景假设：准备月考/单元测试卷时（每 2-3 周一次），教师用 AI 生成 10-15 道题目。但之前用 ChatGPT 出题曾出现化学方程式配平错误，导致教师对 AI 完全不信任。教师需要逐题验证——不仅验证答案是否正确，还要验证方程式系数、反应条件、产物是否正确。当前耗时 30 分钟/次。
- 对应实现：`agent/tools.py:chemical_balance` + `app/services/chemical_balance.py`，基于价态规则和反应条件数据库做四维审核（系数/条件/产物/结构）。审核结果不是"通过/不通过"——是结构化报告 `auditDims`，包含 warning 级别和 block 级别。warning 级别的项目教师可以忽略（"这个条件是加热还是高温？考题有时候不写"），block 级别的项目教师必须确认。
- 验证数据：用 20 道模拟题目测试 chemical_balance。故意在其中 3 道中注入系数错误、条件缺失、产物错误——验证 chemical_balance 是否全部检出。

**场景 3：学生障碍类型诊断**

- 用户原话："分数差不多的两个学生，可能一个属于第二类，一个属于第三类。"（第三轮）
- 场景假设：每次考试/练习后，教师不再只看分数排名，而是调取诊断报告查看每个学生的三维障碍分布。教师期望：知道这个学生是概念没懂（需要重新讲解）、还是题目没读懂（需要审题训练）、还是懂了但写不对（需要规范性练习）。
- 对应实现：`agent/tools.py:diagnose_barrier(student_id_or_class_id)` 遍历 `student_answers` 表中该学生的所有错误记录，统计 `barriar_type` 为 concept/reading/expression 的数量，计算分布比例，写入 `students.barrier_type` JSON 字段。教师前端页面 `frontend/pages/diagnosis.html` 展示分布图。
- 验证数据：第一次用 1005 条数据跑诊断，准确率约 60-70%。教师反馈"大致对但还需要样本积累"。验证项：
  - 输出是否为三维分布比例（三个数之和约等于 1.0）
  - 至少能区分出"主要障碍类型"（占比最高的维度）

**场景 4：学生自主练习**

- 用户原话："班里十几二十个学生明显跟不上，不是他们不聪明。"（第一轮）
- 场景假设：课后或周末自修时间，学生在手机上打开练习页面。看到教师布置的练习任务——可能是根据障碍诊断结果分配的针对性练习。逐题作答（选择题点选项、填空题键盘输入）、提交后看到结果和正确率。练习中的错题自动进入错题本。
- 对应实现：
  - `frontend/m/practice.html` — 学生端练习页面，5 个交互状态
  - `GET /api/practice/student/{id}/tasks` — 获取练习任务列表
  - `POST /api/practice/submit` — 提交答案，写入 `student_answers` 表
  - `frontend/m/wrong.html` — 错题本页面
- 交互流程的 5 个状态：
  1. 任务列表（`loadTasks()`）— 待完成卡片 + 已完成列表
  2. 开始练习（`startPractice(pid)`）— 加载题目列表
  3. 逐题作答（`selectOpt(i)`）— 选项卡片点击选中
  4. 提交（`submitAnswers()`）— API 发送答案数组
  5. 结果展示 — 正确率 + 返回按钮
- 验证数据：模拟 1 个学生完成 5 道题的练习，验证 `student_answers` 表新增 5 条记录，`is_correct` 字段根据答案正确性正确设置。

**场景 5：变种真题生成**

- 用户原话（教导主任，通过教师转述）："能不能把历年真题改成不同版本让学生练？"（六级来源——行政推动，后经验证成为真实需求）
- 场景假设：教导主任推动，教师在出卷时需要基于历年真题生成同考点、同难度、同题型的变种题。选一道真题作为蓝本 → AI 生成 3-5 个变种 → `chemical_balance` 自动审核 → 教师人工确认等价性 → 保存到题库。目的是同一考试不同考场使用不同试卷，防止作弊。
- 对应实现：`agent/tools.py:generate_questions(variant_source=qid)`，提取真题的考点/难度/题型，LLM 生成同构变体，变体生成后进入审核流程。四条红线约束——化学方程式系数不能变、反应条件不能变、产物不能变、考查知识点不能变。
- 教师必须在环内——变种题生成后不能自动保存到题库，必须人工确认等价性。这是从场景 2 的教训中来的：教师对 AI 修改她的题目有天然的抗拒心理。如果 AI 自动保存变种而没有人工审核，教师会直接拒绝使用整个功能。

**场景 6：教师通过 AI 对话获取教研信息**

- 用户原话（模拟，来自 Persona 分离需求）："请讲解氧化还原反应"→ 教师期望得到考点分布、学生常见误区、教学策略，不是被当成学生来教基础概念。
- 场景假设：备课阶段，教师在 AI 聊天对话框中输入"讲解氧化还原反应"。系统需要识别这是一个教师（不是学生），调用教研模式回答——给出考点分布、命题趋势、教学策略、常见误区分析——而不是反问"你先说说你的理解"。
- 对应实现：`agent/tools.py:chemistry_tutor(persona="teacher")` + `agent/langgraph_agent.py:_current_persona`。完整 Persona 流转：
  1. Gateway `agent/gateway.py:276` 匹配关键词"讲解" → `chemistry_tutor`
  2. 路由到 `tutor_expert`
  3. `tutor_expert` 子专家检查 `_current_persona`
  4. 如果 `_current_persona == "teacher"` → 走教研 prompt 分支
  5. 否则走学生辅导 prompt 分支
- 这个流转在 2026 年 3 月 29 日之前只到第 4 步就卡住了——`persona` 传的是默认值 `"tutor"`，导致教师总是被当成学生。

### 5. 场景假设的验证闭环

每个场景假设在代码实现后必须经过三次验证：
1. **开发者自测**：代码跑通，API 返回正确数据
2. **种子用户反馈**：教师实际试用，确认"这就是我要的"
3. **边界压力测试**：异常输入（空数据、极端数据、错误注入）下不崩溃

场景 1（错题统计）是第一个通过三轮验证的场景。种子教师试用了自动生成的错题分布报告后说："这个可以省我一个多小时。"——这是项目第一个被用户确认的功能。

### 6. 经常出现的问题

**Q：学生觉得数据库设计很简单，"不就是建 14 个表吗？"**
A：建 14 个表不难，难的是每个字段都有理由。检查每个字段：这个字段服务于哪个 JTBD？如果没有对应的 JTBD，说明它是多余的。如果有 JTBD 但字段不完整，说明它无法完成工作。比如 `student_answers.barriar_type`——如果只存 `is_correct`，JTBD-J6（识别障碍类型）就无法实现。

**Q：场景假设文档写得太笼统，每个场景只有 3-5 行**
A：场景假设的检查标准："给一个不熟悉项目的开发者看这份文档，他能不能理解这个场景的用户交互流程？"如果场景只写了"教师要出题"而没有"教师打开页面→选择出题类型→输入考点→AI 生成 3 道→逐道审核→保存"，说明场景假设还不够细。

**Q：学生选择 PostgreSQL 而不是 SQLite，理由是"我们公司都用 PostgreSQL"**
A：回看四个硬约束。工具选择没有"好坏"，只有在给定约束下的"合适"。在一个 Windows 单机、没有运维、200 人不到的环境下，PostgreSQL 不是更好——是过度设计。额外复杂度带来的不是收益，是维护负担。

### 7. 真实开发记录还原

以下是 2026 年 1 月到 2 月数据库和场景设计阶段的真实操作记录：

```
Week 2（1 月 14-15 日）
- 完成三轮访谈，提炼 JTBD 矩阵
- 输出 6 个核心场景的初版假设
- 确定数据库选型：SQLite（四大硬约束确认）

Week 3（1 月 20 日）
- 创建 app/models/models.py：14 个 ORM 模型
- 创建 app/models/database.py：WAL 模式引擎
- 创建 app/utils/init_db.py：67 人 + 1005 条数据
- 首次 python app/utils/init_db.py 运行：14 表创建成功

Week 4（1 月 27 日）
- 种子教师试用错题统计功能（场景 1），确认"这个可以省我一个多小时"
- 根据反馈微调 knowledge_points JSON 字段的知识点标签体系
```

---

## 课后产出检查

学生应该同时具备：

- [ ] `app/models/models.py` 含 14 个完整的 SQLAlchemy ORM 模型
- [ ] `app/models/database.py` 含数据库引擎、会话管理、WAL 模式启用
- [ ] `app/utils/init_db.py` 可执行，输出：67 学生 + 1005 答题记录
- [ ] `chemai.db` 文件存在，大小约 4.5MB
- [ ] `docs/database-schema.md` 含 14 个表的完整描述和设计决策
- [ ] `docs/scenario-spec-v1.md` 含 6 个核心场景的完整拆解
- [ ] PRAGMA journal_mode 返回 'wal'
- [ ] 所有学校名称统一写"湖南某重点高中"

**下节课需要**：数据库就绪（chemai.db 包含初始化数据），场景假设文档就绪。Session 11 将搭建 OCR 管线（Baidu + MinerU + MiMo 三层架构），让计算机读懂化学 PDF。

---

## 补充内容 — 教师深度参考

### 14 个表的设计决策树

以下是每个表为什么被创建、服务于什么 JTBD 的完整追踪：

```
accounts（登录认证）
  ├── teachers → 服务于 J1-J12（所有 JTBD 都需要教师身份）
  ├── students → 服务于 J6, J7, J10（障碍诊断 + 自适应练习 + 个性化关注）
  └── parents → 服务于 J4（错题报告 - 家长版）

classes + teacher_class_subject
  └── 服务于 J1, J4（班级级错题统计 + 班级级报告）

exam_records → 服务于 J1, J3（考试记录 + 分析报告）

questions
  ├── 服务于 J1（错题统计需要知道题目所属知识点）
  ├── 服务于 J2, J3（出题审核 + 三维分析）
  └── 服务于 J7（自适应练习需要从题库选题）

student_answers → 服务于 J1, J6, J7（错题统计 + 障碍诊断 + 自适应练习）

student_submissions + upload_sessions → 服务于 J1（答题卡扫描导入）

question_sets → 服务于 J2, J7（AI 出题的题库集合管理）

schools → 服务于学校信息存储（基础数据）

parent_notifications → 服务于 J4（错题报告 - 家长通知）
```

### barrier_type JSON 字段的演化过程

```
无此字段（最初设计）
  → student_answers 只存 is_correct
    → 发现：只知道答对答错，不知道"为什么错"
      → 添加 student_answers.barrier_type（单题判定）
        → 发现：需要聚合视图才能展示给学生和教师
          → 添加 students.barrier_type（聚合分布）
            → 当前方案：两层 barriar_type 共存
```

### SQLite 的 WAL 模式技术细节

SQLite 默认的 DELETE 模式在写操作时需要对整个数据库文件加锁，所有读操作必须等待。WAL 模式将写操作写入一个单独的 WAL 文件，读操作仍然可以访问主数据库文件，实现了读写不互斥。

启用的 SQL 语句：`PRAGMA journal_mode=WAL;`

对于 ChemAI 场景（90+ 人同时在线练习），WAL 模式可以让多个学生同时提交答案而不会出现写锁排队。但要注意：WAL 文件可能会增长（因为写入比 checkpoint 快），SQLite 会在 WAL 文件达到 1000 页时自动 checkpoint。

### 为什么原生 HTML 而非 Vue/React

这个决策不是数据库设计的一部分，但在 Session 4 的上下文中有学生的疑问会自然地连到这里。原因在前端架构设计文档中有详述，这里简要说明三点：

1. 教书匠不是前端工程师，改一个页面不需要先学 Vue Router
2. 页面间没有共享状态（每个页面独立的表单和数据）
3. 每个页面 <500 行，小学生都能维护——全前端代码 1300 行，用 React 至少 3000 行起步

这个决策的验证数据：教师端的核心页面 `exam-v2.html` 使用 Vue 3 内联（917 行），不需要 `npm install`，不需要 `webpack build`，直接在浏览器打开就能用。

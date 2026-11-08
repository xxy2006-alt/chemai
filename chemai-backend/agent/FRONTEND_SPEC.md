# ChemAI 前端完整规格文档

> 用于生成原型。当前前端已模块化但积重难返，建议基于此文档重新设计。

---

## 一、用户角色

| 角色 | 用户名 | 密码 | 可见功能 |
|------|--------|------|---------|
| 管理员 | `admin` | `admin123` | 全部 |
| 学科组长 | `hai` | `hai123456` | 教学功能 + 审批 |
| 教师 | `liu` / `chen` | `123456` | OCR/出题/诊断/考试/学情 |
| 学生 | `202610101` 等67人 | `123456` | 练习/错题/复习/AI辅导 |

---

## 二、页面清单与跳转流程

```
登录页 (/login.html)
  │
  ├─ 教师/管理员 → 首页 (Agent 聊天)
  │     │
  │     ├─ AI 对话 (默认首页)
  │     │   └─ 支持：提问/配平/出题/实验模拟/真题搜索/错题诊断
  │     │
  │     ├─ 答题卡识别 (/ocr)
  │     │   └─ 流程：选班级 → 上传答题卡 → OCR识别 → 预览确认 → 入库
  │     │
  │     ├─ 考试管理 (/exam)
  │     │   └─ 创建考试 → 选题（AI生成/手动/真题库）→ 发布 → 查看结果
  │     │
  │     ├─ 题目管理 (/question)
  │     │   └─ AI出题 / 手动导入 / 历年真题搜索 / 题目审核
  │     │
  │     ├─ 障碍诊断 (/diagnosis)
  │     │   └─ 班级诊断 → 学生个体诊断 → 生成学习计划 → 发送给家长
  │     │
  │     ├─ 学情报告 (/report)
  │     │   └─ 老师版：班级维度 / 学生维度 / 知识点维度
  │     │
  │     ├─ 学情面板 (/panel)
  │     │   └─ 知识点热力图 / 学生进退步 / 班级趋势
  │     │
  │     ├─ 学生管理 (/students)
  │     │   └─ 学生列表 / 审批 / 转班
  │     │
  │     └─ 系统设置 (管理员)
  │         └─ 学校设置 / 年级 / 班级 / 教师审批
  │
  ├─ 学生 → 学生首页 (练习中心)
  │     ├─ AI 辅导 (聊天)  ← 默认
  │     ├─ 我的练习 (pending/completed)
  │     ├─ 错题本 (错题复习/变式练习)
  │     ├─ 复习中心 (艾宾浩斯间隔复习)
  │     ├─ 学习计划 (AI生成)
  │     └─ 我的报告
  │
  └─ 家长 → 家长首页
        ├─ 孩子本周学习周报
        ├─ 学习情况报告
        └─ 通知消息
```

---

## 三、核心功能详细规格

### 3.1 AI 对话 (Agent Chat) — 首页

**位置：** 所有角色登录后的默认首页

**功能：**
- SSE 流式对话（逐字显示）
- 快捷提问芯片（配平方程式 / 出题练习 / 模拟实验 / 讲解概念 / 查真题 / 错题诊断）
- 工具调用可视化（执行方程式审核时显示 ToolCard）
- 状态栏（思考中... / 执行中... / 回复中...）
- 侧边栏：对话历史 + 功能入口

**API：** `POST /api/agent/chat/stream` (SSE)

**输入：**
```json
{ "persona": "teacher", "message": "...", "provider": "deepseek", "history": [...] }
```

**输出 (SSE 事件流)：**
```
data: {"type":"phase","phase":"thinking"}
data: {"type":"tool_call","name":"balance_equation","args":{...}}
data: {"type":"tool_result","name":"balance_equation","success":true,"result":{...}}
data: {"type":"phase","phase":"reply"}
data: {"type":"text","content":"这个方程式..."}
data: {"type":"done"}
```

**Persona 映射：**
| 角色 | Persona | 可用 Skill |
|------|---------|-----------|
| 教师 | `teacher` | diagnose_barrier, generate_questions, search_exam_bank, balance_equation, import_exam_paper |
| 学生 | `tutor` | chemistry_tutor, balance_equation, search_exam_bank, simulate_experiment |
| 家长 | `parent` | weekly_report, diagnose_barrier |

---

### 3.2 答题卡识别 (OCR)

**流程：**
```
选择班级 → 上传答题卡图片/PDF → 智谱 OCR 识别
→ 预览识别结果（学号/姓名/每题答案）→ 老师修正/确认
→ 入库 → 自动生成错题统计
```

**API：**
| 端点 | 用途 |
|------|------|
| `POST /api/ocr/recognize` | 单张识别 |
| `POST /api/ocr/recognize/batch` | 批量识别 |
| `POST /api/ocr/confirm` | 确认入库 |
| `POST /api/ocr/stats` | 生成错题统计 |
| `GET /api/ocr/services/status` | OCR 服务状态 |

---

### 3.3 考试管理

**流程：**
```
创建考试 → 选择班级 → 添加题目
  ├─ AI 生成题目 (POST /api/question/generate)
  ├─ 从题库选择 (GET /api/exam-bank/historical)
  └─ 手动导入 (POST /api/question/import)
→ 发布考试 → 学生作答 → 查看结果
```

**API：**
| 端点 | 用途 |
|------|------|
| `POST /api/exam/create` | 创建考试 |
| `GET /api/exam/list/{classId}` | 考试列表 |
| `GET /api/exam/{examId}` | 考试详情 |
| `GET /api/exam/{examId}/result/{studentId}` | 学生结果 |

---

### 3.4 题目管理 / 题库

**功能：**
- AI 出题：选知识点 + 难度 + 数量 → LLM 生成 → 自动审核方程式配平
- 历年真题搜索：250 道真题 (2008-2025 全国卷+湖南卷)，按知识点/年份/难度筛选
- 手动导入：上传 PDF 试卷 → MinerU 解析 → 审核 → 入库
- 题目审核：方程式配平 / 反应条件 / 产物稳定性 / 结构检查

**API：**
| 端点 | 用途 |
|------|------|
| `POST /api/question/generate` | AI 出题 |
| `POST /api/question/audit` | 题目审核 |
| `GET /api/question/historical` | 历史真题 |
| `POST /api/question/import` | 手动导入 |
| `POST /api/question/import/ocr` | OCR 导入 |
| `GET /api/exam-bank/historical` | 真题搜索 |

---

### 3.5 障碍诊断

**三种障碍类型：**
- 概念理解型 (concept) — 对化学概念理解有偏差
- 审题障碍型 (reading) — 读取题目信息不全
- 表述障碍型 (expression) — 理解但无法规范表述

**输出：** 障碍分布 + 主导类型 + 干预建议 + 个性化学习计划

**API：**
| 端点 | 用途 |
|------|------|
| `GET /api/diagnosis/barrier/{classId}/{examId}` | 班级诊断 |
| `GET /api/diagnosis/barrier/{studentId}` | 学生诊断 |
| `POST /api/diagnosis/learning-plan/generate` | 生成学习计划 |
| `POST /api/diagnosis/learning-plan/apply/{studentId}` | 应用计划 |
| `POST /api/diagnosis/learning-plan/send-to-parent/{studentId}` | 发给家长 |

---

### 3.6 学情报告

**两种视图：**
- 老师版：班级维度 / 题目维度 / 典型错误 / 干预建议
- 学生版：个人成绩 / 错题 / 知识点掌握 / 鼓励语

**API：**
| 端点 | 用途 |
|------|------|
| `GET /api/report/teacher/{examId}` | 老师报告 |
| `GET /api/report/student/{examId}/{studentId}` | 学生报告 |
| `GET /api/report/student/{studentId}` | 学生总览 |
| `GET /api/report/class/{classId}` | 班级报告 |

---

### 3.7 学情面板

**三维度：**
- 知识点维度：错误率分布 / 热力图
- 学生维度：进退步曲线 / 个人雷达图
- 时间维度：历次考试趋势

**API：**
| 端点 | 用途 |
|------|------|
| `GET /api/panel/class/{classId}` | 班级面板 |
| `GET /api/panel/class/{classId}/knowledge/{kp}` | 知识点详情 |
| `GET /api/panel/class/{classId}/student/{sid}` | 学生详情 |
| `GET /api/panel/class/{classId}/trend` | 趋势图 |

---

## 四、学生端功能

| 模块 | 功能 | API |
|------|------|-----|
| AI 辅导 | 对话式辅导（引导不直接给答案） | `POST /api/agent/chat/stream` |
| 我的练习 | 查看/完成练习任务 | `GET /api/practice/student/{id}/tasks` |
| 做题 | 逐题作答 | `GET /api/practice/{id}/questions` |
| 提交 | 提交答案 → 即时反馈 | `POST /api/practice/submit` |
| 错题本 | 错题列表 + 变式练习 | `GET /api/practice/wrong/list` |
| 复习中心 | 艾宾浩斯间隔复习 | `GET /api/review/student/{id}/due` |
| 学习计划 | AI 生成 + 查看进度 | `GET /api/diagnosis/learning-plan/{id}` |
| 我的报告 | 历次考试报告 | `GET /api/report/student/{id}` |

---

## 五、家长端功能

| 模块 | 功能 | API |
|------|------|-----|
| 首页 | 孩子本周学习周报 | `GET /api/parent/child/{id}/weekly` |
| 学情 | 学习报告 + 障碍诊断 | `GET /api/parent/child/{id}/report` |
| 通知 | 老师发送的通知 | `GET /api/parent/notifications` |

---

## 六、数据模型关键字段

### 学生 (students)
`student_id, name, class_id, barrier_type(JSON), exercises_completed`

### 考试 (exam_records)
`record_id, class_id, name, avg_score, total_students`

### 题目 (questions)
`question_id, content, options(JSON), answer, knowledge_points(JSON), difficulty, audit_status`

### 学生作答 (student_answers)
`answer_id, student_id, question_id, student_answer, is_correct, barrier_type`

### 账号 (accounts)
`account_id, username, password_hash, role, teacher_id/student_id/parent_id, status`

---

## 七、后端 Agent 可用 Skill

| Skill | 触发词示例 | 返回内容 |
|-------|-----------|---------|
| `balance_equation` | "配平 H2+O2=H2O" | 配平结果 + 元素计数 |
| `search_exam_bank` | "搜索盐类水解真题" | 真题列表 |
| `diagnose_barrier` | "分析学生障碍" | 障碍类型 + 建议 |
| `generate_questions` | "出3道化学题" | 题目列表 + 审核 |
| `chemistry_tutor` | "氧化还原是什么" | 引导式讲解 |
| `simulate_experiment` | "模拟钠与水反应" | 实验步骤/现象/原理/安全 |
| `weekly_report` | "生成周报" | 学习周报(家长版) |
| `import_exam_paper` | "导入这张试卷" | 提取题目 + 审核 + 入库 |

---

## 八、技术信息

**后端：** FastAPI (Python), SQLite, 端口 8000
**LLM：** DeepSeek V4 Flash (文本), 智谱 GLM-4.6V-FlashX (多模态)
**OCR：** 智谱 GLM-OCR
**前端 (原)：** Vite + vanilla JS 模块化 (50 个 JS 文件)
**Agent：** 纯 Python (agent/ 目录, ~1200 行)
**SSE 协议：** `POST /api/agent/chat/stream`, 结构化 JSON 事件流

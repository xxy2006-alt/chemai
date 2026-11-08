# ChemAI 前后端完整修复 + Agent 集成 — 工程计划

> 基于前端审计（50 个 JS 文件，17 个 bug）和后端审计（20+ API 文件，6 个关键问题）

---

## Phase 0: 已清理 ✅

- [x] 删除 `hermes-agent-main/`（88MB，Windows 不兼容）
- [x] 删除 `teacher_v2.html` / `student_v2.html`（Vite 构建产物，非源文件）
- [x] 删除 `chat-widget.js`（浮窗组件，不再需要）
- [x] 删除 `agent_demo.html`
- [x] `vite.config.js` — 构建入口清理
- [x] `app.js` — `apiRequest` 已恢复

---

## Phase 1: 前端 — 基础设施（先能跑）

### 1.1 统一 API 配置
- [ ] `src/services/parent.js:5` — 硬编码 `http://localhost:8001` → `''`
- [ ] `src/services/notification.js` — 7 处裸 `fetch()` → `api.get/post`（缺 token 导致 401）
- [x] `src/services/api.js` — `API_BASE` 已改为 `''` ✅
- [x] `vite.config.js` — proxy target `8000` ✅

### 1.2 登录流程修复
- [ ] `pages/login.js:28` — `authService.login(username, password, role)` 去掉第三个参数
- [ ] `pages/login.js:37` — 登录后重定向 `/index.html` → role-based（教师→`/teacher_v2.html`，学生→`/student_v2.html`）。等等，这些文件已删除，实际用的是 `index_new.html` 的 SPA 模式——确认登录后正确进入 SPA

---

## Phase 2: 前端 — 3 个高危 Bug

| # | 文件:行 | 问题 | 修复 |
|---|---------|------|------|
| 2.1 | `student/practice.js:35` | `getStudentTasks()` 缺 studentId → `/undefined/tasks` | 从 session 取 studentId |
| 2.2 | `student/learning_plan.js:65` | `plan.barrier针对性的干预` 中文属性名 JS 语法可能出错 | 加 `plan['barrier针对性的干预']` fallback |
| 2.3 | `services/integration.js:59` | `api.post(url, null, {params})` 第三参数被丢弃 | 合并到 body |

---

## Phase 3: 前端 — 14 个中低危 Bug

| # | 文件:行 | 问题 | 修复 |
|---|---------|------|------|
| 3.1 | `main.js:303` | `teacherNotificationModule` 未声明 | 加 `const` |
| 3.2 | `modules/parent/reports.js:58` | 中文 `barrierType` 无法匹配英文 key | 加映射表 |
| 3.3 | `modules/teacher/panel.js:761` | 硬编码 `barrier_type: 'concept'` + 假知识点 | 用当前选中学生的真实数据 |
| 3.4 | `services/user.js:68` | `/api/users/` vs `/api/user/` 不一致 | 统一 `/api/users/` |
| 3.5 | `services/review.js` | 整个文件与 `practice.js` 中 `reviewService` 重复 | 删 `review.js` |
| 3.6 | `modules/teacher/exam.js` + `question.js` | `runQuestionGeneration` 完全重复 | 抽到 `utils/hermes-ui.js` |
| 3.7 | `modules/teacher/report.js:263` | `trend.dates?.[i]` 在纯数组上取不到 | 修数据结构引用 |
| 3.8 | `modules/parent/index.js:67,71` | `showBindModal` 重复赋值 | 删一个 |
| 3.9 | `modules/student/learning_plan.js:169` | `querySelector([data-task-id=...])` 找不到元素 | 渲染时加 `data-task-id` 属性 |
| 3.10 | `modules/student/learning_plan.js` | `showLearningPlanModal` 双重 fetch | 统一入口 |
| 3.11 | `modules/student/review_center.js` | `status === 'mastered'` vs `level` 数字不一致 | 统一用 `status` |
| 3.12 | `services/log.js` | `getLogTypes()` 是纯 mock | 标注 TODO，保持现状 |
| 3.13 | `modules/student/practice.js` | `handleShowLearningPlan` 双重 fetch | 去掉冗余调用 |
| 3.14 | `modules/teacher/exam.js` | `switchTab` 未从 barrel export | 确认 window 赋值已覆盖 |

---

## Phase 4: 后端 — 6 个关键问题

### 4.1 `parent.py:106` — register_parent 运算符优先级 BUG（P0）
```python
# 当前（错误）：
if session.query(Account).filter(Account.username == data.phone or data.email).first():
# Python 解析为：(Account.username == data.phone) or (data.email)
# data.email 总是真值 → 永远触发"用户名已存在"

# 修复：
if session.query(Account).filter(
    (Account.username == data.phone) | (Account.username == data.email)
).first():
```

### 4.2 `practice.py` — 静默返回假数据（P0）
```python
# get_student_practice_tasks — except Exception 后返回硬编码 mock 数据
# submit_practice — 同上
# 修复：删除 except 分支中的 mock 数据，返回明确错误
```

### 4.3 `vector_search.py:241` — LLM prompt 伪造向量嵌入（P1）
```python
# _get_embedding 用 LLM "请生成768维浮点数数组" 当嵌入向量
# 修复：标注 TODO，短期内用 TF-IDF 或直接用关键词匹配
```

### 4.4 `models/database.py:357-358` — 重复 relationship（P2）
```python
class_obj = relationship("Class", back_populates="teacher_subjects")
class_obj = relationship("Class")  # 覆盖上行
# 修复：删除第二行
```

### 4.5 `exam.py:finalize_exam` — TODO 未实现（P2）
```python
# TODO: 计算平均分（需要根据答题情况计算）
# 修复：实现 avg_score = sum(scores) / len(scores)
```

### 4.6 `question.py:839` — os.popen 命令注入风险（P2）
```python
# import_questions_from_ocr: os.popen(f"pdftotext {tmp_path} -")
# 修复：用 subprocess.run([...], shell=False)
```

---

## Phase 5: ChemAgent 集成

### 5.1 后端 — 已就绪 ✅
- `POST /api/agent/chat` / `POST /api/agent/chat/stream` — SSE 流式
- `POST /api/hermes/chemistry-chat` — 已转发到 ChemAgent（复用 HermesThinking）
- `agent/provider/` — DeepSeek V4 Flash + 智谱 GLM-4.6V-FlashX + 通义千问
- `agent/skills/` — 8 个化学 Skill

### 5.2 前端 — 对接 HermesThinking 到 ChemAgent

**不改组件，只改 `hermes.js`：**

```diff
- const HERMES_API = 'http://localhost:8001'
- POST {HERMES_API}/runs  →  SSE events

+ const AGENT_API = '/api/agent'
+ POST {AGENT_API}/chat/stream  →  SSE chunks (兼容现有 HermesThinking 解析)
```

### 5.3 Skill → 前端模块映射

| ChemAgent Skill | 前端模块 | 触发场景 |
|-----------------|---------|---------|
| `balance_equation` | `teacher/question.js` | 出题后自动审核方程式 |
| `search_exam_bank` | `teacher/question.js` | 真题搜索 |
| `diagnose_barrier` | `teacher/diagnosis.js` | 班级/学生障碍诊断 |
| `generate_questions` | `teacher/exam.js` | AI 出题 |
| `chemistry_tutor` | `student/practice.js` | 做题时 AI 辅导 |
| `weekly_report` | `parent/reports.js` | 家长周报 |
| `simulate_experiment` | 教师端侧边栏 | 实验模拟 |
| `import_exam_paper` | `teacher/exam.js` | PDF 试卷导入 |

---

## Phase 6: 端到端验证

- [ ] Vite (3000) + FastAPI (8000) 同时运行
- [ ] 登录 → 教师端所有模块加载
- [ ] OCR 上传 → 选班级 → 文件选择
- [ ] 题目库 → 真题搜索 → 250 条数据显示
- [ ] 考试管理 → 创建考试
- [ ] 学情面板 → 数据展示
- [ ] AI 对话 → HermesThinking 流式渲染（走 ChemAgent）
- [ ] 学生端 → 练习/错题/复习
- [ ] 家长端 → 周报

---

## 执行顺序

```
Phase 0 ✅ 已清理

Phase 1 (前端基础设施, ~30min)
    │
Phase 2 (前端 3高危bug, ~20min)  ←── 并行 ──→  Phase 4 (后端 6个问题, ~30min)
    │                                                    │
Phase 3 (前端 14中低危, ~40min)                          │
    │                                                    │
    └──────────────────── 汇合 ──────────────────────────┘
                         │
                    Phase 5 (Agent集成, ~30min)
                         │
                    Phase 6 (验证, ~20min)
```

---

## 总计

| 类别 | Bug 数 | 预估时间 |
|------|--------|---------|
| 前端基础设施 | 3 | 30min |
| 前端高危 | 3 | 20min |
| 前端中低危 | 14 | 40min |
| 后端关键问题 | 6 | 30min |
| Agent 集成 | 1 文件改动 | 30min |
| 验证 | — | 20min |
| **合计** | **27 项** | **~170min** |

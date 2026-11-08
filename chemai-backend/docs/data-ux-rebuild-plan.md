# 数据重构 + 交互修复 — 全盘方案

> 日期: 2026-07-07 | 状态: 待实施

---

## 第一部分：三个问题的根因

### 问题 1: genPlan 渲染错误

| 现象 | 根因 |
|------|------|
| `[object Object]` 出现在计划内容里 | LLM 返回的 `barrier_interventions` / `motivation_tips` 含嵌套对象，`String()` 强制转换 |
| `**设立里程碑**` 等 Markdown 原样显示 | `escHtml` 只转义 HTML，不渲染 Markdown |
| `plan_title` 显示 `[object]` | LLM 可能把 title 返回成 `{"text":"..."}` 对象 |

**修复方向:**
- 渲染计划内容用 `innerHTML` + Markdown 渲染，而非 `contenteditable` 纯文本
- 编辑时 `contenteditable` 允许，但展示时渲染 Markdown
- `_planData` 写入前清洗：递归把非字符串值安全化

### 问题 2: Agent 审批中断挂起

| 现象 | 根因 |
|------|------|
| Agent 说"需要向您确认"后没有下文 | 前端 `agent.js` **完全没有处理** `phase: "awaiting_approval"` SSE 事件 |
| 对话永远卡住 | LangGraph `interrupt()` 暂停了图，但前端没有调用 `/chat/langgraph/resume` |
| LLM 选了 `assign_adaptive_practice` 而非 `generate_learning_plan` | 两个工具语义有重叠，"生成个性化学习方案" → LLM 误判为"布置练习" |

**修复方向:**
- 前端加 `awaiting_approval` 处理：在聊天中弹出确认按钮 [确认] [取消]
- 点了确认 → `POST /chat/langgraph/resume` 恢复图
- 强化网关关键词：`学习方案/学习规划` → 直接路由到 `generate_learning_plan`
- `generate_learning_plan` 移出 `TOOL_APPROVAL_REQUIRED`（确认一下：它已经不在审批列表里）

### 问题 3: 数据混乱

| 现象 | 根因 |
|------|------|
| 65/66 学生 barrier 完全一样 (0.33/0.33/0.34) | `randomize_students.py` 只改了 barrier 和 exercise 量，但 `init_db.py` 的默认值没变。前端实际拿的可能是 API 返回的真实数据（默认值） |
| 只有 1 人有答题记录 | 除了李世睿没人有 `student_answers` |
| "需关注" = 0、"人均练习" = 0 | barrier 都 < 0.6，没人触发"需关注"；只有 1 人有练习 |
| 前端降级到 mock 数据 | `GET /api/users/students` 可能返回空，前端用 `mockStudents()` 的 15 人假数据 |
| diagnosis.js 硬编码 barrier='concept' | 第 300 行 `barrier_type: 'concept'` 写死了 |

---

## 第二部分：数据重构方案

### 目标：66 个学生各有真实差异化数据

每个学生需要：
- `barrier_type` — 三个值各不相同，和为 1.0，主导障碍分散
- `exercises_completed` — 0-45，正态分布
- `student_answers` — 10-30 条，正确率随机 40%-95%
- `questions` — 链接到真实题目（复用李世睿那 10 道）
- `exam_records` — 每个班级 1 个已发布的考试记录

### 数据脚本设计 (`tools/rebuild_all_students.py`)

```
Step 1: 清空所有学生答题数据（保留学生基础信息）
Step 2: 给每个学生随机 barrier
Step 3: 创建 1 个 exam_record 给2419班 + 1 个给2420班
Step 4: 给每个学生生成 10-30 条答题记录
  — 链接到同一套 10 道真实题（复用李世睿的题库）
  — 正确率按 barrier 类型有微小偏向
    · concept 为主的学生：简单题正确率偏低
    · reading 为主的学生：中等难度题正确率偏低
    · expression 为主的学生：难题正确率偏低
Step 5: 更新 exercises_completed = 实际答案数
Step 6: 验证: 抽查 5 个学生数据是否各不相同
```

### 关键约束

- 保留李世睿 (202610201) 的特殊数据不变
- 保留 202610101 已改名陈思雨
- 所有 question 复用 `demo_q_00` ~ `demo_q_09` (10 道真实题)
- exam_record 使用 `class_exam_1` / `class_exam_2`

### 数据分布目标

| 指标 | 目标 |
|------|------|
| dominant:concept | ~40% (26人) |
| dominant:reading | ~35% (23人) |
| dominant:expression | ~25% (17人) |
| exercises_completed | 正态分布, 均值 20, 标准差 10 |
| 正确率 | 40%-95%, 均值 70% |
| 最大障碍值 > 0.6 | ~15 人 (触发"需关注") |

---

## 第三部分：前端交互修复

### Fix 1: genPlan 渲染 (students.js)

**改 renderPlanCard:**
- 计划标题/周期 → 纯文本展示，不 contenteditable
- 每日任务/周目标/激励建议 → `innerHTML` 渲染 Markdown (复用 `renderChemMD`)
- 障碍干预 → `_safe_barrier` 清洗后再渲染
- contenteditable 保留，但在展示时先渲染 Markdown

**改 escHtml → 新增 renderMD 函数:**
- 把 `**text**` 转 `<strong>text</strong>`
- 把 `## title` 转 `<h2>title</h2>`
- 把 `- item` 转 `<li>item</li>`

### Fix 2: Agent 审批流 (agent.js + gateway.py)

**前端 agent.js:**
```javascript
case 'phase':
  if (j.phase === 'awaiting_approval') {
    // 在聊天中弹出确认卡片
    addApprovalCard(j.message, function(approved) {
      fetch('/api/agent/chat/langgraph/resume', {
        method: 'POST',
        body: JSON.stringify({
          conversation_id: currentConvId,
          user_response: approved ? 'approved' : 'cancelled'
        })
      }).then(function(r) { return r.json() })
        .then(function(d) {
          // 重新建立 SSE 连接继续对话
        })
    })
  }
```

**网关 gateway.py:**
- 关键词加: `"方案" → generate_learning_plan`, `"学习计划" → generate_learning_plan`

### Fix 3: 审批工具本身

- `generate_learning_plan` 确认不在 `TOOL_APPROVAL_REQUIRED` 里 (已验证: 只有 `assign_adaptive_practice` 和 `delete_bank` 在审批列表)
- `assign_adaptive_practice` 的 docstring 加 "教师说'学习方案'/'学习计划'时不要选我 — 用 generate_learning_plan"

### Fix 4: 统一前端屏障标签 (diagnosis.py + students.js)

- `show_students` 第 211 行: `"concept": "计算能力"` → `"concept": "概念理解"`
- 统一所有前端 barrier 标签映射表

---

## 第四部分：执行顺序

```
Phase 1: 数据重构
  Step 1.1: 写 rebuild_all_students.py
  Step 1.2: 运行脚本, 验证 66 人数据多样化
  Step 1.3: 确认前端不再降级到 mock 数据

Phase 2: genPlan 渲染修复
  Step 2.1: Markdown 渲染 + contenteditable 分开展示/编辑
  Step 2.2: [object Object] 清洗

Phase 3: Agent 审批流
  Step 3.1: gateway.py 加关键词路由
  Step 3.2: agent.js 加 awaiting_approval 确认卡片
  Step 3.3: 验证全套流程

Phase 4: 标签统一
  Step 4.1: "计算能力" → "概念理解"
  Step 4.2: 前端所有 barrier 标签一致
```

**预估总工时: 3-4 小时**

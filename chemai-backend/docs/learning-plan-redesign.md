# 学习计划 — 重设计方案

> 日期: 2026-07-06 | 状态: 待实施

---

## 1. 现状问题

### 学生管理界面 (`students.js:418-425`)

```js
// 当前实现 — 3 个问题
window.genPlan = function() {
  api('/api/diagnosis/learning-plan/generate', {
    body: JSON.stringify({
      student_id: currentStudent.student_id,
      barrier_type: 'concept',          // ❌ 硬编码, 不用学生真实数据
      weak_knowledge_points: []         // ❌ 空数组, 计划质量差
    })
  }).then(function() { alert('学习计划已生成!') })  // ❌ 30秒空白 + 不展示内容
}
```

### Agent Chat

| 需求 | 当前状态 |
|------|---------|
| "找到张三" | ✅ `show_students` 工具可用 |
| "给张三生成学习计划" | ❌ 没有 `generate_learning_plan` Agent 工具 |
| 返回计划文档供教师查看 | ❌ 无 |
| 教师手动修改计划 | ❌ 无 |
| 通过对话让 Agent 修改 | ❌ 无 |
| 确认后发送给学生 | ❌ 没有 `send_learning_plan` 工具 |
| 学生收到计划 | ✅ `GET /learning-plan/{student_id}` API 可用, 前端模块已写但未接入 |

### 持久化

- `POST /apply` 端点只有 TODO 注释, 不存数据库
- 计划只在内存缓存 (`_plan_cache`) + 教师浏览器 localStorage
- 服务器重启 → 计划丢失

---

## 2. 目标体验

### 场景 A: Agent Chat 全流程

```
教师在 Agent Chat 输入:
  "找到张小明, 给他生成一份学习计划"

Agent 执行:
  1. show_students(student_name="张小明")
     → 返回: student_id=202610101, barrier={concept:0.45, reading:0.30, expression:0.25}

  2. generate_learning_plan(student_id="202610101")
     → 调后端 API, 用学生真实 barrier + 薄弱知识点
     → 在聊天中返回结构化计划文档:

     ┌──────────────────────────────────────────┐
     │ 📋 学习计划 · 张小明                      │
     │ 周期: 2026-07-07 ~ 2026-07-20 (2周)       │
     │                                          │
     │ 🎯 周目标                                 │
     │  第1周: 掌握离子方程式书写, 正确率≥70%      │
     │  第2周: 氧化还原反应配平, 完成10道练习      │
     │                                          │
     │ 📅 每日任务 (14天)                         │
     │  Day 1: 离子方程式拆写删查复习 + 3道练习    │
     │  Day 2: 可溶性强电解质判断 + 5道选择        │
     │  ...                                      │
     │                                          │
     │ 🧠 障碍干预                               │
     │  概念理解: 方程式四步法思维导图             │
     │  审题仔细: 每日一道精读训练                 │
     │                                          │
     │ 💡 激励建议                               │
     │  每完成一周目标解锁一个化学趣味实验视频      │
     └──────────────────────────────────────────┘

  ⚠️ 以下按钮仅在聊天中可见 (Agent 输出):
     [编辑计划] [发给学生] [重新生成]

教师: "把第二周的任务改成盐类水解专题"
  → Agent 理解修改意图, 返回更新后的计划展示

教师: "第三天的练习太多, 改成2道"
  → Agent 更新 Day 3 任务量

教师: "没问题了, 发给张小明"
  → Agent 调 send_learning_plan(student_id, plan_data)
  → 持久化到数据库 + 写入 SqliteStore 长期记忆
  → 返回: "✅ 学习计划已发送给张小明, 学生端即刻可见"
```

### 场景 B: 学生管理界面生成

```
教师打开学生管理 → 点击张小明 → Drawer 展开
  ┌─────────────────────────────────────┐
  │ 张小明 · 2419班 · 202610101       │
  │ [转班] [重置密码] [生成学习计划]       │
  │─────────────────────────────────────│
  │ 学习统计: 练习12次 | 正确率75% | ↗     │
  │ 障碍: 概念45% | 审题30% | 表述25%     │
  │─────────────────────────────────────│
  │          [点击"生成学习计划"]           │
  └─────────────────────────────────────┘

  ↓ 点击后, Drawer 内展开计划区域:

  ┌─────────────────────────────────────┐
  │ 📋 正在生成学习计划...  ⏳            │  ← spinner
  │─────────────────────────────────────│
  │ (3-5秒后)                            │
  │                                      │
  │ 📋 学习计划 · 张小明                  │
  │ ┌─────────────────────────────────┐ │
  │ │ 周期: 2026-07-07 ~ 2026-07-20    │ │  ← 可编辑字段
  │ │ [编辑]                           │ │
  │ ├─────────────────────────────────┤ │
  │ │ 🎯 周目标                         │ │
  │ │ 第1周: [离子方程式书写, 正确率≥70%] │ │  ← 可编辑
  │ │ 第2周: [氧化还原反应配平, 10道练习] │ │
  │ ├─────────────────────────────────┤ │
  │ │ 📅 每日任务                       │ │
  │ │ Day 1: [离子方程式复习 + 3道练习]   │ │  ← 可编辑
  │ │ Day 2: [强电解质判断 + 5道选择]    │ │
  │ │ ... (可展开/折叠)                  │ │
  │ ├─────────────────────────────────┤ │
  │ │ 🧠 障碍干预                       │ │
  │ │ [方程式四步法思维导图]             │ │  ← 可编辑
  │ ├─────────────────────────────────┤ │
  │ │ 💡 激励建议                       │ │
  │ │ [每周完成解锁化学趣味实验视频]      │ │  ← 可编辑
  │ └─────────────────────────────────┘ │
  │                                      │
  │ [保存修改]  [发给学生]  [取消]         │
  └─────────────────────────────────────┘
```

---

## 3. 实现方案

### 3.1 新建 Agent 工具 (2 个)

**`generate_learning_plan`** — `agent/tools/diagnosis.py`

```python
async def generate_learning_plan(
    student_id: str = "",
    student_name: str = "",
) -> str:
    """学习计划生成 — 为指定学生生成个性化学习计划

    何时用: 教师说"生成学习计划""给XX做一份学习计划""帮XX规划学习"
    会发生什么: 根据学生的障碍类型和薄弱知识点, LLM生成结构化学习计划,
               包含周目标、每日任务、障碍干预策略、激励建议
    返回: 在聊天中直接展示计划文档, 附带 [修改] [发给学生] 快捷操作
    下一步: 教师可要求修改某部分内容, 或确认后发送给学生
    """
    # 1. 调用诊断 API 获取学生的真实障碍数据
    # 2. 调用 POST /api/diagnosis/learning-plan/generate
    # 3. 返回格式化的计划文档 + _component 让前端渲染可编辑卡片
```

**`send_learning_plan`** — `agent/tools/diagnosis.py`

```python
async def send_learning_plan(
    student_id: str = "",
    plan_data: str = "",
) -> str:
    """发送学习计划 — 将确认后的计划发送给学生

    何时用: 教师在聊天中确认计划无误后, 说"发送""发给学生""推送"
    会发生什么: 持久化到数据库, 写入 SqliteStore 长期记忆,
               学生端刷新即可查看
    返回: 确认消息, 含学生姓名和发送时间
    """
```

### 3.2 修复 `POST /apply` 端点 (`app/api/diagnosis.py:545-566`)

```python
# 当前: 空壳 TODO
# 修复: 写入 SqliteStore 长期记忆 + 更新 _plan_cache

@router.post("/learning-plan/apply/{student_id}")
async def apply_student_learning_plan(student_id, plan_data, db):
    # 1. 写入 SqliteStore namespace ("student", student_id, "learning_plan")
    # 2. 更新 _plan_cache 缓存
    # 3. 可选: 写 Student 表的 barrier_type 字段更新
    # 4. 返回成功
```

### 3.3 修复 `students.js` genPlan (前端)

改动 `frontend/js/students.js:417-425`:

```
旧: 硬编码 barrier_type='concept' + 空知识点 + alert()
新:
  1. 从 currentStudent.barrier_type 取真实障碍数据
  2. 从 currentStudent.weak_kps 取薄弱知识点
  3. 点击后在 Drawer 底部展开"计划区域"
  4. 显示 spinner + "正在生成学习计划..."
  5. API 返回后渲染可编辑计划卡片
  6. 每个字段点击进入编辑模式 (contenteditable / input)
  7. [保存修改] → 更新本地 plan 对象
  8. [发给学生] → POST /apply + 提示"已发送"
```

### 3.4 注册工具到 TOOLS + TOOL_META (`agent/tools/__init__.py`)

```python
# 新增:
generate_learning_plan: {"personas": ["teacher"], "call_limit": 5},
send_learning_plan:     {"personas": ["teacher"], "call_limit": 2},
```

---

## 4. 文件变更清单

| 操作 | 文件 | 内容 |
|------|------|------|
| **修改** | `agent/tools/diagnosis.py` | 新增 `generate_learning_plan` + `send_learning_plan` |
| **修改** | `agent/tools/__init__.py` | TOOLS + TOOL_META 注册两个新工具 |
| **修改** | `app/api/diagnosis.py:545-566` | `POST /apply` 补实现(写 SqliteStore) |
| **修改** | `frontend/js/students.js:417-425` | genPlan 重写:真实数据+spinner+可编辑卡片 |
| 无需改 | `app/api/diagnosis.py:497-542` | `POST /generate` 已可用(但 genPlan 要传真实参数) |
| 无需改 | `frontend/src/modules/student/learning_plan.js` | 学生端展示模块已写好 |

---

## 5. 执行顺序

```
Step 1 — 后端: 补 POST /apply 持久化 (10min)
    │
Step 2 — Agent: 新建 generate_learning_plan + send_learning_plan 工具 (20min)
    │
Step 3 — Agent: 注册到 TOOLS + TOOL_META (2min)
    │
Step 4 — 前端: 重写 students.js genPlan (30min)
    │
Step 5 — 验证: Agent Chat 全流程 + 学生管理界面
```

**预估: ~1 小时**

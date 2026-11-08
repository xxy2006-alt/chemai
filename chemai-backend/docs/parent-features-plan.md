# 家长端功能增强 + 教师-家长打通方案

> 日期: 2026-07-07 | 状态: 待实施

---

## 1. 绑定按钮智能切换

**现状:** 右上角永远显示 `add_link` 图标，点击弹绑定窗。

**改法:** 加载 children 数据后判断 `CHILDREN.length > 0`：
- 有绑定 → 图标显示已绑定学生姓名首字 + 点击弹出操作面板（解绑 / 换绑）
- 无绑定 → 保持现状

```html
<!-- 有绑定时 -->
<button onclick="showBindManage()">张小宁 已绑定 ▾</button>

<!-- 无绑定时 -->
<button onclick="showBindModal()">+ 绑定</button>
```

**操作面板:** 弹一个小 modal：显示当前绑定学生姓名 + "解绑"按钮（二次确认）+ "绑定其他孩子"入口。

---

## 2. "主要成长空间" → "AI 学习建议"

纯文案替换，不改逻辑。`barrierText()` 函数里把 "主要成长空间" 改成 "🤖 AI 学习建议"。

---

## 3. 学习报告完整版

### 3.1 报告结构

参考市面上家长教育产品（班小二、晓黑板、ClassDojo），家长报告应包含：

| 板块 | 数据来源 | 展示形式 |
|------|---------|---------|
| 📊 学习概览 | 练习量/正确率/连续天数 | 三列统计卡片 |
| 📈 本周 vs 上周 | 两次 API 调用对比 | 箭头 + 百分比变化 |
| 🎯 知识点掌握 | 错题统计 | 标签列表（熟练/一般/薄弱三档） |
| 🧠 学习特点 | barrier_type | 通俗解读文字 |
| 💡 给家长的建议 | 基于障碍类型的家庭建议 | 文字段落 |

每板块下方有一个 `🤖 AI 总结` 按钮。

### 3.2 AI 总结按钮

点击后调 `POST /api/parent/child/{sid}/report/ai-summary`:
- `section`: 板块名 (如 "knowledge_points")
- `data`: 该板块的原始数据
- 后端调 DeepSeek: "用 2-3 句通俗中文总结以下数据，40-55 岁家长能看懂"
- 返回摘要文字，在按钮下方插入显示
- 点一次生成一次，不缓存（家长可能第二次点想看不同表述）

### 3.3 报告 Tab 布局

```
┌─────────────────────────────────┐
│ 📊 学习概览                       │
│  [26道] [73%] [5天]              │  ← 统计卡片
│  🤖 AI总结                       │  ← 点击后下方插入摘要
├─────────────────────────────────┤
│ 📈 进步趋势                       │
│  练习量 ↑3  正确率 ↑10%           │
│  🤖 AI总结                       │
├─────────────────────────────────┤
│ 🎯 知识点掌握                     │
│  盐类水解 [薄弱] 离子反应 [一般]   │
│  氧化还原 [熟练] ...              │
│  🤖 AI总结                       │
├─────────────────────────────────┤
│ 🧠 学习特点                       │
│  审题仔细度是主要成长空间...       │
│  (此板块无需AI总结, 已是通俗语言)   │
├─────────────────────────────────┤
│ 💡 家庭配合建议                    │
│  每天陪孩子读一道题...            │
│  🤖 AI总结                       │
└─────────────────────────────────┘
```

---

## 4. 教师端 → 家长端打通

### 4.1 确认流程

```
教师在 Agent Chat 输入:
  "把李世睿的学习报告发给家长"

Agent 调用:
  generate_parent_report(student_name="李世睿")
    → 查学生 → 聚合诊断数据 → 生成报告预览
    → 聊天中展示报告预览卡片

教师确认/修改后:
  "没问题，发吧"

Agent 调用:
  send_report_to_parent(student_id="202610201", confirmed_report=<报告>)
    → 查绑定的家长 → 写 ParentNotification
    → 返回: "✅ 学习报告已发送给李世睿家长(李建国)"
```

### 4.2 Agent 工具设计

**`generate_parent_report`**

```python
async def generate_parent_report(
    student_name: str = "",
    student_id: str = "",
) -> str:
    """家长报告生成 — 为指定学生生成面向家长的完整学习报告预览

    何时用: 教师说"发报告给XX家长""把XX的学习报告发给家长"
    会发生什么: 聚合学生的练习数据、障碍诊断、知识点掌握情况,
               生成一份家长可读的报告, 在聊天中展示预览
    返回: 报告预览卡片, 教师可确认、修改或取消
    下一步: 教师确认后调 send_report_to_parent 发送
    """
    # 1. 解析学生
    # 2. 调诊断 API 获取障碍数据
    # 3. 调 weekly API 获取练习统计
    # 4. 组装报告 JSON
    # 5. 返回格式化预览
```

**`send_report_to_parent`**

```python
async def send_report_to_parent(
    student_id: str = "",
    report_data: str = "",
) -> str:
    """发送家长报告 — 将确认后的报告推送给绑定家长

    何时用: 教师确认报告后说"发送""发给家长"
    会发生什么: 查绑定的家长, 写 ParentNotification,
               家长端消息Tab立即可见
    返回: 确认消息, 含家长姓名和发送时间
    """
```

### 4.3 通知格式

```python
ParentNotification(
    notification_id=...,
    parent_id=...,
    student_id=...,
    type="weekly_report",
    title="📋 李世睿的学习报告",
    content=json.dumps(report_data),  # 完整报告 JSON
    is_read=False,
    sent_at=...
)
```

### 4.4 家长端展示

家长端通知列表里，`type === 'weekly_report'` 的通知 → 点击不标记已读，而是展开报告面板（复用报告 Tab 的渲染逻辑）。

---

## 5. 文件变更清单

| # | 文件 | 操作 | 内容 |
|---|------|------|------|
| 1 | `frontend/m/parent.html` | 修改 | 绑定按钮条件判断 + AI推荐改名 |
| 2 | `frontend/m/parent.html` | 修改 | 报告Tab重做（完整报告 + AI总结按钮） |
| 3 | `app/api/parent.py` | 新增 | `POST /child/{sid}/report/ai-summary` |
| 4 | `agent/tools/diagnosis.py` | 新增 | `generate_parent_report` + `send_report_to_parent` |
| 5 | `agent/tools/__init__.py` | 修改 | 注册两个新工具 |

预估: ~1.5h

---

## 6. 执行顺序

```
Step 1: 后端 AI 摘要 API          (10min)
Step 2: Agent 两个新工具 + 注册    (20min)
Step 3: 前端报告Tab重做            (30min)
Step 4: 前端绑定按钮 + AI推荐改名   (10min)
Step 5: 验证全流程                 (20min)
```

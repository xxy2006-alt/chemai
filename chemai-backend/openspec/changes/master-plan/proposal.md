# Agent 页面驱动 — 完整计划

> 最后更新: 2026-06-16
> 协议设计: Agent 通过 SSE navigate/populate/action 事件驱动前端页面跳转 + 数据填充 + UI 操作

---

## 协议（已实现）

```
Backend SSE 事件流                          Frontend 消费
─────────────────                          ──────────
navigate  {page:"exam-v2", params:{...}}   → window.location 跳转
populate  {target:"questions", data:{...}} → 页面组件预填数据
action    {action:"openTab", payload:"x"}  → 页面执行 UI 操作
```

---

## 四个页面驱动矩阵

### exam-v2 (考试工作台)

| 事件 | 字段 | 效果 | 状态 |
|------|------|------|------|
| navigate | page="exam-v2" | 打开考试工作台 | ✅ 已实现 |
| populate | target="questions" | 题目列表预填到出题区 | ✅ 已实现 |
| populate | target="searchResults" | 真题搜索结果预填 | ✅ 已实现 |
| action | openTab:generate | 切到 AI 出题 tab | ✅ 已实现 |
| action | openTab:browse | 切到历史真题 tab | ✅ 已实现 |
| action | openTab:upload | 切到 OCR 上传 tab | ✅ 已实现 |
| action | filterKp | 按知识点筛选 | ✅ 已实现 |

### diagnosis (诊断)

| 事件 | 字段 | 效果 | 状态 |
|------|------|------|------|
| navigate | page="diagnosis" | 打开诊断页面 | ✅ |
| populate | target="diagnosis" | 诊断结果预填渲染 | ✅ |
| action | selectClass | 选中班级，触发 change | ✅ |
| action | selectStudent:张三 | 展开学生详情 | ✅ |
| action | showPlan | 展开学习计划 | ✅ |

### students (学生管理)

| 事件 | 字段 | 效果 | 状态 |
|------|------|------|------|
| navigate | page="students" | 打开学生管理 | ✅ |
| populate | target="weeklyReport" | 周报内容预填 | ✅ |
| action | searchStudent:张三 | 搜索并高亮学生 | ✅ |
| action | openWeeklyReport | 打开周报 | ✅ |

### teacher (教师面板)

| 事件 | 字段 | 效果 | 状态 |
|------|------|------|------|
| navigate | page="teacher" | 打开教师面板 | ✅ |
| action | showClass:高三1 | 定位班级 | ✅ |
| action | openWarnings | 展开预警面板 | ✅ |

---

## 实现计划

### 当前: exam-v2 + diagnosis 已完成

```
agent-page-driver (archived) → 后端 SSE 导航事件 + 两个页面 bridge 消费者
```

### 下一步: Phase 5 Agent 聊天 UI（P1）

Change: `phase5-agent-chat-ui` (4h) ⬜ 待你确认后启动

参考 `agent/PHASE5_PLAN.md`：
- index.html → Chat-first 体验（侧边栏对话历史 + 快捷提问 + 底部状态栏）

---

## 不做的事

- ❌ students/teacher 页面的复杂数据 pipeline（Agent 能导航过去 + 高亮就够了）
- ❌ 不在 master-plan 里规划基础设施/部署/测试（那是另一条线）

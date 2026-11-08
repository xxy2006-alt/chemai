# 家长端前端 — 实施计划

> 日期: 2026-07-06 | 状态: 后端 100%, 前端 ~20%

---

## 1. 现状审计

### 已完成 (无需改动)

| 层 | 文件 | 说明 |
|-----|------|------|
| 数据库 | `app/models/database.py` | Parent / StudentParentBinding / ParentNotification 三个模型 |
| API | `app/api/parent.py` | 11 个端点，前缀 `/api/parent` |
| 注册 | `app/main.py:115` | `app.include_router(parent.router, prefix="/api/parent")` |
| 角色 | `agent/personas/parent.yaml` | system_prompt, available_skills, data_access |
| 工具 | `agent/tools/__init__.py` | 4 个 parent 工具: web_search, diagnose_barrier, weekly_report, memory_student_get |
| 前端模块 | `frontend/src/modules/parent/` | 5 个 JS 文件已编码（home/reports/notifications/settings/index） |

### 缺口 (需要新建/修改)

| # | 缺口 | 文件 | 影响 |
|---|------|------|------|
| 1 | 无 HTML 页面 | `frontend/m/parent.html` (不存在) | 家长登录后进了学生聊天页 |
| 2 | 无 API 服务层 | `frontend/src/services/parent.js` (不存在) | 5 个前端模块 import 失败 |
| 3 | Persona 硬编码 | `frontend/m/index.html:248` → `persona:'student'` | 家长聊天用错了 persona |
| 4 | 无家长聊天入口 | `frontend/m/` 下无家长聊天页 | 家长无法跟 AI 对话看报告 |
| 5 | 周报数据是硬编码 | `app/api/parent.py:413-416` | accuracy=0.85, weak_kps=["盐类水解","电离平衡"] |

---

## 2. 架构设计

### 2.1 页面结构

```
家长登录 (login.html)
  │
  └─ role === 'parent' → /m/parent.html
       │
       ├── Tab 1: 首页 (home.js)       — 子女卡片 + 统计概览 + 绑定孩子
       ├── Tab 2: 学习报告 (reports.js) — 周报摘要 + 障碍分析 + 薄弱知识点
       ├── Tab 3: 消息通知 (notifications.js) — 通知列表 + 已读/未读
       ├── Tab 4: AI 助手 (chat)        — 家长 persona 的 Agent 聊天
       └── Tab 5: 设置 (settings.js)    — 账号信息 + 解绑 + 通知偏好
```

### 2.2 数据流

```
家长点击"AI 助手"
  │
  ├── POST /api/agent/chat/langgraph/stream
  │     body: { persona: "parent", message, provider: "deepseek", version: "v2" }
  │
  ├── SSE 事件 → 渲染聊天卡片
  │     - weekly_report   → 周报内容直接展示
  │     - diagnose_barrier → 障碍诊断展示 + "建议家长做什么"
  │     - web_search       → 搜索结果
  │
  └── 家长说"看看孩子本周情况"
       → Agent 调 weekly_report(student_id=已绑定孩子)
       → 返回周报文本 → 聊天区直接展示
```

### 2.3 API 服务层 (`services/parent.js`)

```
parentService = {
  getChildren()         → GET  /api/parent/children?parent_id=...
  getReport(student_id) → GET  /api/parent/child/{student_id}/report
  getWeekly(student_id) → GET  /api/parent/child/{student_id}/weekly
  getNotifications()    → GET  /api/parent/notifications?parent_id=...
  markRead(id)          → PUT  /api/parent/notifications/{id}/read
  bindStudent(data)     → POST /api/parent/bind
  unbindStudent(id)     → DELETE /api/parent/bind/{id}
  sendBindCode(sid)     → POST /api/parent/send-bind-code/{sid}
}
```

---

## 3. 实施步骤

### Step 1: 创建 `frontend/m/parent.html` (新建)

移动端家长主页，结构参考 `m/index.html` 的学生端模板。

```
m/parent.html:
  - 底部 Tab 栏: 首页 | 报告 | 通知 | AI助手 | 设置
  - div#page-home     → 加载 modules/parent/home.js
  - div#page-reports  → 加载 modules/parent/reports.js
  - div#page-notifications → 加载 modules/parent/notifications.js
  - div#page-chat     → 内嵌 Agent 聊天 (复用 m/index.html 的聊天逻辑, persona='parent')
  - div#page-settings → 加载 modules/parent/settings.js
```

**工作量:** ~150 行 HTML + CSS（参考现有 m/index.html 模板）

### Step 2: 创建 `frontend/src/services/parent.js` (新建)

API 服务层，封装所有 `/api/parent` 端点调用。复用 `src/services/api.js` (或 `frontend/js/api.js`) 的 token 注入逻辑。

```
parent.js:
  8 个函数, 每个 5-10 行
  全部用 api.get() / api.post() 封装（自动带 token）
```

**工作量:** ~60 行 JS

### Step 3: 修复父模块导入 (修改 5 个文件)

`frontend/src/modules/parent/*.js` 已经写好了业务逻辑，只需要确认导入路径正确：

| 文件 | 当前 import | 修复 |
|------|-------------|------|
| home.js | `import { parentService } from '../../services/parent.js'` | 确认 services/parent.js 存在 |
| reports.js | 同上 | 同上 |
| notifications.js | 同上 | 同上 |
| settings.js | 同上 | 同上 |
| index.js | 同上 | 同上 |

模块内部逻辑无需改动 — 它们已经完成了 DOM 操作、事件绑定、状态管理。

**工作量:** 验证导入路径，无需改代码

### Step 4: 家长聊天 — SSE persona 路由 (修改 2 处)

1. **`frontend/m/parent.html`** — 新建的聊天区直接传 `persona: 'parent'`
2. **`frontend/login.html:238`** — 已路由到 `/m/index.html`（共用入口），需要在 `m/index.html` 增加 persona 检测，或改为跳到 `/m/parent.html`

当前 `login.html:238`:
```js
if(ud.role==='student'||ud.role==='parent')target='/m/index.html';
```

修复方案:
```js
if(ud.role==='parent')target='/m/parent.html';
else if(ud.role==='student')target='/m/index.html';
```

这样家长和学生各自进入独立页面，persona 各自硬编码正确。

**工作量:** 改 1 行 login.html + 新建 parent.html 聊天 tab

### Step 5: 修复周报硬编码数据 (后端, 可选立即做)

`app/api/parent.py:413-416`:
```python
# 当前 (硬编码):
accuracy_rate=0.85,
weak_knowledge_points=["盐类水解", "电离平衡"],
streak_days=student.exercises_completed % 30

# 修复 (从 StudentAnswer 表真实聚合):
accuracy_rate = _calc_accuracy(student_id, week_start)
weak_knowledge_points = _calc_weak_kps(student_id, week_start)
streak_days = _calc_streak(student_id, week_start)
```

**工作量:** 3 个聚合函数，~30 行 Python

---

## 4. 文件变更清单

| 操作 | 文件 | 行数 |
|------|------|------|
| **新建** | `frontend/m/parent.html` | ~150 |
| **新建** | `frontend/src/services/parent.js` | ~60 |
| **修改** | `frontend/login.html:238` | 1 行 |
| 验证 | `frontend/src/modules/parent/home.js` | 确认导入 OK |
| 验证 | `frontend/src/modules/parent/reports.js` | 确认导入 OK |
| 验证 | `frontend/src/modules/parent/notifications.js` | 确认导入 OK |
| 验证 | `frontend/src/modules/parent/settings.js` | 确认导入 OK |
| 验证 | `frontend/src/modules/parent/index.js` | 确认导入 OK |
| 可选 | `app/api/parent.py:413-416` | ~30 行 (周报真数据) |

---

## 5. 验证清单

- [ ] 家长账号登录 → 进入 `/m/parent.html`（不是学生聊天页）
- [ ] 首页 Tab → 显示已绑定子女卡片 + 练习统计
- [ ] 绑定孩子 → 输入学生ID+绑定码 → 绑定成功
- [ ] 报告 Tab → 显示周报摘要 + 障碍类型 + 薄弱知识点
- [ ] 通知 Tab → 显示通知列表 + 点击标记已读
- [ ] AI 助手 Tab → SSE 流式聊天, persona='parent'
- [ ] 对 AI 说"孩子本周情况" → Agent 调 weekly_report → 聊天区展示周报
- [ ] 对 AI 说"孩子主要问题" → Agent 调 diagnose_barrier → 聊天区展示诊断
- [ ] 设置 Tab → 账号信息 + 解绑 + 退出登录

---

## 6. 执行顺序

```
Step 2 (parent.js)  ←── 先建服务层（其他都依赖它）
    │
Step 1 (parent.html)  ←── 建页面骨架 + 聊天 Tab
    │
Step 3 (验证导入)     ←── 5 个模块文件，确认能加载
    │
Step 4 (修复 login.html 路由) ←── 1 行改动
    │
Step 5 (周报真数据)   ←── 可选，提升体验
    │
验证清单全部打勾 → 家长端上线
```

**预估总工时: ~2 小时（新建 2 个文件 + 改 1 行 + 验证 5 个文件）**

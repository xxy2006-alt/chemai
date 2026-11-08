# 五问题修复方案

> 日期: 2026-07-07 | 状态: 待实施

---

## 问题 1: Agent 找不到李世睿

**现象:** Agent Chat 说"帮我找下李世睿"→ Agent 返回找不到。

**根因:** `show_students` 的参数是 `class_id`/`class_name`——没有 `student_name` 参数。LLM 调用 `show_students(class_name="李世睿")` 时，`class_name` 去 `classes` 表匹配而非 `students` 表。真正能按姓名找学生的工具是 `diagnose_barrier(student_name="...")`，但 LLM 不知道。

**修复:**
- `agent/tools/diagnosis.py` — `show_students` 函数签名加 `student_name=""` 参数
- 如果传了 `student_name`，优先走 LIKE 模糊搜索（跟 `diagnose_barrier` 一样的逻辑），返回匹配学生列表

**文件:** `agent/tools/diagnosis.py` (约 15 行新增)

---

## 问题 2: 所有学生数据一模一样

**现象:** 66 个学生 `barrier_type` 全是 `{concept:0.33, reading:0.33, expression:0.34}`，练习数全 0。

**根因:** 初始化脚本 `init_db.py` 用的统一默认值。

**修复:**
- 写一个数据随机化 Python 脚本 `tools/randomize_students.py`
- 给每个学生随机障碍分布（三值归一化到 1.0，各有差异）
- 随机 `exercises_completed`（0-50）
- 模拟 7-30 天答题记录，正确率随机 40%-95%
- 错题随机分配知识点

运行一次，DB 直接改。

**文件:** 新建 `tools/randomize_students.py`

---

## 问题 3: 学习计划——慢 + 不知是否送达

**现象:** 生成等很久（LLM 同步调用 15-30s），发送后不知道学生收到没。

**根因有两个:**

a) 读取链断裂 — `GET /learning-plan/{student_id}` 只查内存缓存，从不读 SqliteStore。`POST /apply` 写 SqliteStore，两条路没接上。

b) 异步写入竞态 — `loop.create_task()` 异步写 SqliteStore，可能在 HTTP 200 返回前未写完。服务器重启后 `_plan_cache` 清空，学生看不到计划。

**修复:**
- `GET /learning-plan/{student_id}` 改为三级查找：`_plan_cache` → SqliteStore → LLM 生成
- `POST /apply` 改为先同步写 SqliteStore（await），再写缓存，再返回 200
- 前端学生端加 2 秒轮询重试（应对极端情况）

**文件:** `app/api/diagnosis.py` (约 30 行修改)

---

## 问题 4: 学生端个人设置——敬请期待

**现象:** `m/report.html` 点击设置显示 `alert('个人设置：即将上线')`。

**修复:**
- 将 alert 替换为设置面板，4 个功能：
  1. **修改密码** — 对接已有 `POST /api/auth/change-password`
  2. **查看绑定码** — 显示当前学生的 `bind_code`，供家长端绑定
  3. **个人信息** — 姓名/班级/学号（只读展示）
  4. **关于** — 版本号 + ChemAI 简介
- 布局参考同页面的菜单列表风格，使用模态弹窗展示

**文件:** `frontend/m/report.html` (约 80 行修改)

---

## 问题 5: 家长端 lijg/123456 登录显示无效 token

**现象:** 输入 lijg/123456 → "无效 token"。

**根因有两个，叠加导致必现:**

a) `POST /api/parent/login` 不生成 JWT。只返回 `success`, `parent_id`, `name`, `role`，没有 `token` 字段。

b) `/api/parent/` 不在 `PUBLIC_PREFIXES` 白名单。auth 中间件在 login 请求到达前就拦截了。

**修复:**
- `app/api/parent.py` `login_parent` — 调用 `create_access_token()` 生成 JWT，返回中添加 `token` + `refresh_token` 字段
- `app/main.py` `PUBLIC_PREFIXES` — 追加 `"/api/parent/"`
- 前端 `parent-login.html` 已正确处理 token 存储（`d.token || ''`），无需改

**文件:** `app/api/parent.py` (约 5 行新增), `app/main.py` (1 行新增)

---

## 执行顺序

```
Step 1: 问题 5 (家长登录 token)   — 阻塞性 bug, 不修家长完全无法用
Step 2: 问题 1 (Agent 找学生)     — 影响教师体验
Step 3: 问题 3 (学习计划链)       — 功能断裂, 教师发了学生看不到
Step 4: 问题 2 (学生数据随机)     — 演示效果差
Step 5: 问题 4 (学生设置)         — 功能空白
```

**预估总工时:** ~2 小时（5 个文件修改 + 1 个新建脚本）

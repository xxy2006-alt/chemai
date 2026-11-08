# RBAC 强制执行 — 开发任务

> 每一步都带「验证」。**验证不通过不进下一步。**
> 阶段 0 / 1 / 6 不改行为，可独立提交、独立回滚；阶段 2 / 3 才真正改变线上行为。

---

## 0. 角色模型（无行为变更）

- [x] 0.1 建立 `Role` 枚举 + 中文显示名映射表
  - **已完成**：`middleware/auth.py` 的 `Role(str, Enum)` + `ALL_ROLES` + `ROLE_LABELS`。
    继承 `str` 是刻意的 —— 现有代码到处是裸字符串比较（`role == "teacher"`），
    枚举值要能直接当字符串用。
  - **它的真实价值是「7 个角色的唯一清单」**：此前角色集合散在 `ROLE_PERMISSIONS` 的键、
    `ROLE_LABELS` 的键、`SELF_ROLES`、`STAFF_ROLES` 好几处，加一个角色要改四五处
    **且没有东西提醒你漏了哪处**。现在有断言钉住它们互相一致。
  - 落地时立刻见效：`test_permission_matrix.py` 里本地又抄了一份 `ALL_ROLES`，
    被 ruff 的 F811 当场抓到 —— 正是这个枚举要防的漂移。
  - **验证**：`test_role_enum_is_the_single_source_of_truth`（7 个值、无重复、
    ROLE_LABELS / SELF_ROLES / ROLE_PERMISSIONS 的键都与枚举一致）+ 7 角色中文名齐全

- [x] 0.2 数据迁移：`accounts.role` 中 `学科组长` → `subject_lead`（1 行）；`teachers.role` 停止读写
  - **已完成**：迁移函数 `migrate_role_values` 写入 `migrate.py`（幂等）。`teachers.role` 已整列删除（模型/写入/打印/孤儿字典键/demo 脚本全部清理），`migrate_teachers_table` 从"建列"改为"删列"
  - **验证**：迁移后 4 个教师账号全部能登录，且 `/api/auth/me` 返回的 role 为英文值

- [x] 0.3 同步改 4 处硬编码中文字面量：
  `app/api/auth.py:78`、`app/middleware/auth.py:32`、`:40`、`:325`、`app/utils/init_db.py:81`、`:232`
  - **已完成**：另含 `middleware/auth.py:355`、`init_db.py` 种子、`tools/rebuild_demo_dataset.py:138`。`教务管理员` 一并改为 `academic_admin`（无账号无数据，纯代码）
  - **验证**：**海老师（`subject_lead`）登录后 `name` / `teacher_id` / `school_id` 三个字段齐全** —— 这正是 P1-3 修过的 bug，此验证专门防它复发
  - **验证**：`python -m pytest tests/ -q` 全绿

- [x] 0.4 新增 `super_admin` 账号（不挂 `school_id`、无 `teachers` 记录）；`admin_001` 保持校级 `admin`
  - **已完成**：`init_db` 种子加 `superadmin / super123456`（`acc_super`）——
    `teacher_id` / `student_id` / `parent_id` **全为空**（ADR-0011 里超管的形状就是「不挂学校」）。
    `admin_001` 保持校级 `admin` 不变。
  - `get_user_info` 加超管分支：中文名走 `role_label()` 单一来源，**刻意不去 teachers
    表借 school_id** —— 借了就等于给了常驻跨校权限，正是 ADR-0011 要避免的。
  - **验证**：超管登录成功（实测 `role=super_admin / name=平台超级管理员`）✅
  - **验证**：超管默认数据范围为空 —— 实测 `/api/classes` 返回 **0 个班**、
    `/api/users/students` 返回 **0 个学生** ✅

- [x] 0.5 重建 `ROLE_PERMISSIONS`
  - **已完成**：矩阵在阶段 4.6 第一批重建（11 个内容资源键）+ 后续扩展
    （`integration` / `log` / `agent` / `break_glass`）。现在 19 个资源键。
  - 新增两条**完整性断言**（比逐项核对更值钱）：
    - `test_every_declared_resource_exists_in_the_matrix` —— 端点里声明的资源
      矩阵里必须有人拥有，否则那组端点**谁都进不去**（拼错资源名不会报错，
      只会静默 403）
    - `test_matrix_resource_keys_are_all_used_somewhere` —— 矩阵里的键必须真有端点在用。
      这条**当场抓到一个我自己留的**：阶段 4.6 批次 A 删了 `/api/grading` 路由，
      矩阵里的 `grading` 键忘了清（已删）
  - ⚠️ **与原文的一处偏差**：原文要求「矩阵不含 `student` / `parent` 条目」，但**基础矩阵里
    学生本来就有三个键**（`self_data` / `assignment` / `grade`，来自最初的设计，
    不是本次引入）。其中 `grade` 曾**有真实后果**（学生能列学校年级列表）——
    已于 2026-09-12 移除，见下方「`grade` 键的语义重叠」。
    `parent` 确实没有条目 ✅。`self_data` / `assignment` 是死键（无端点消费），
    已登记进 `DEAD_MATRIX_KEYS` 显式豁免（只减不增）。**这三条要不要清理，待项目方定。**
  - **验证**：见上两条断言 + `test_every_declared_action_is_a_known_action`
    （动作只能是 create/read/update/delete，拼错同样会静默 403）

### ~~`grade` 键的语义重叠~~ → **已解决**（2026-09-12）

`ROLE_PERMISSIONS['student']` 里曾有 `grade: ['read']` —— 原意大概是
**「读自己的成绩」**，但它与「年级管理」的资源键**撞名**了，后果是
`GET /api/grades`（返回学校年级元数据：grade_id / 名称 / 年份 / school_id）
**对学生开放**。

**处置：删掉那条授权，`grade` 只留给年级管理。**

⚠️ **没有新建「成绩」资源键，因为不需要** —— 学生读**自己**成绩的路径已经存在：
`/api/report/student/{id}`（返回 `your_score` / `class_avg_score` / `rank`，
`frontend/m/report.html:202` 调的就是它），由 `analysis:read` + `allow_self` +
`ScopeGuard` 收窄到本人 —— ADR-0008 的模型。
新建一个没有端点消费的 `score` 键只会立刻变成**死键**，而
`test_matrix_resource_keys_are_all_used_somewhere` 正是禁止死键的。

**实测（真实账号）**：
| 调用 | 改动前 | 改动后 |
|---|---|---|
| 学生 → `GET /api/grades` | 200，能看到 3 个年级 | **403** |
| 教师（hai）→ 同一端点 | 200 | 200，3 个年级（员工照旧） |
| 管理员 → 同一端点 | 200 | 200 |
| 学生 → `GET /api/report/student/{自己}` | 200 | 200（读自己成绩的路仍通） |

**验证**：`test_student_cannot_list_school_grades`（学生/家长 deny、教师 allow）
+ 决策表新增 `GET /api/grades` 一行；`SELF_ROLE_MATRIX_EXCEPTIONS` 随之清空
（那条豁免不再需要，测试的「白名单只减不增」反向校验会逼着删）。

---

## 1. 前端铺垫（无行为变更）— 阶段 2 的前置

> 本阶段**不改任何行为**，纯粹让所有调用方带上已有的 token。做完可以先放着观察。

- [x] 1.1 `frontend/m/index.html:246` 的流式对话补 `Authorization` 头（当前是裸 fetch，只发 `Content-Type`）
  - **验证**：学生端完整走一次对话（发消息 → 收流式回复），行为与改造前一致
  - ⚠️ **这一条不做，阶段 2 会把学生端聊崩**

- [x] 1.2 检查 `frontend/m/` 其余裸 fetch（`parent.html:638,651,674,701` 的 `/api/agent` 调用）是否带 token
  - **已完成**：前 3 处改用本文件自带的 `api()` 助手；流式那处单独补 `Authorization`。另修 `legacy/teacher/pages/ocr-sheets.html`（补 fetch 拦截器，覆盖其全部 7 个调用）与 `legacy/teacher/diag.html`（1 处）
  - **验证**：家长端发消息正常

- [x] 1.3 修正 `tools/verify_all_features.py:191,192` —— 调 `/api/knowledge/list` 时传 `None` 而非 token
  - **验证**：`python tools/verify_all_features.py` 全绿

- [x] 1.4 确认 React 教师端无需改动（`api.ts:50-52` 已默认附加 Authorization）
  - **已核实**：React 端对 7 个待保护前缀共 42 处调用，全部走带 token 的 `api` 助手或 `agent-sse.ts`（显式 `Authorization`）；仅 2 处 `public:true`，均为 `/api/auth/login`
  - **验证**：教师端 6 个页面（chat/class/students/exam/diagnosis/ocr-sheets）功能照旧

- [ ] 1.5 **打开 uvicorn 访问日志**，观察部署环境真实流量
  - **验证**：能列出访问过 `/api/parser/`、`/api/knowledge/`、`/api/integration/` 的来源 IP
  - ⚠️ 这是唯一能证实/排除外部调用方的手段（当前 `_server.log` 里 0 条 HTTP 记录）
  - **✅ 能做的部分已做**（2026-09-13）：起服务开 `--access-log`，用无头浏览器把
    **四个客户端全跑一遍**（教师端 admin/hai、学生端、家长端、legacy），收集真实访问记录。
    **结果：整个应用只调 21 个端点**（去重后）。据此确认：
    - `/api/knowledge/list` **被调 3 次** —— 教师端在用（删它会打断功能）
    - `/api/parser/*` **0 次** —— 删除未打断任何东西（与既有结论一致）
    - `/api/integration/*` 0 次 —— 该页是新加的，没有客户端流程访问它
      （另用无头浏览器单独验过 `/#/integration`：页面四要素齐全、
      发出 `GET /api/integration/api-keys`、控制台无错误）
  - **⏸ 剩下的部分只能项目方做**：上面量到的是**本应用自己的流量**，
    证明不了「有没有**外部系统**（定时任务、别处的脚本、第三方集成）在调」。
    那需要真实部署环境跑一段时间。目标端点只剩 `/api/knowledge/` 与 `/api/integration/`
    （`/api/parser/` 已删）。

---

## 2. 白名单收缩（认证生效）

- [x] 2.1 从 `app/main.py` 的 `PUBLIC_PREFIXES` 移除 8 个业务前缀：
  `/api/classes`、`/api/question/`、`/api/exam-bank/`、`/api/agent/`、`/api/ocr/`、`/api/parser/`、`/api/knowledge/`、`/api/parent/`
  - **已完成，但计划有一处修正**：`/api/parent/` **不能整段移除** —— 该前缀下有 `POST /api/parent/login` 和 `POST /api/parent/register`，这两个端点天然发生在拿到 token 之前，移除即导致家长登录失效（实施时发现）。改为只放行这两条精确路径，`/api/parent/` 其余端点（`children`/`bind`/`report`/`send-bind-code`…）一律要求认证。
  - **验证**：`curl /api/classes` 无 token → 401（改造前是 200 + 全部班级）
  - **验证**：`curl /api/classes` 带学生 token → 200（此时仍能看全部，范围限制在阶段 4）

- [x] 2.2 `/docs`、`/redoc`、`/openapi.json` 改为仅开发环境开放
  - **验证**：生产配置下 `curl /docs` → 404

- [x] 2.3 全链路回归：教师端 6 个页面 + 学生端 + 家长端
  - **已验证**：13 个受保护端点匿名全部 401；家长端 `lgh/123456` 登录→`children`→`notifications`→`agent/conversations` 全链路 200；学生端登录→练习/知识卡→agent 200；教师端 classes/knowledge/exam-bank/ocr 200。`python -m pytest tests/ -q` → **362 passed**
  - **验证**：`python -m pytest tests/ -q` 全绿
  - **验证**：`python -m pytest tests/test_regression_auth_data.py -q` 全绿（认证 + 数据可见性）
  - **验证**：手工点一遍三个角色，无 401

- [x] 2.4 ⚠️ **若决定先单独堵班级接口**（不等整套方案），本条可提前到阶段 0 之前执行：
  删 `/api/classes` 白名单 + 给 `class_api.py` 5 个端点加认证
  - **验证**：无 token 调 `DELETE /api/classes/class_2025_1` → 401

---

## 3. 默认拒绝骨架（授权生效）

> **方案 B（2026-09-11 决定）**：阶段 3 只建**机制 + 守卫**，router 声明随阶段 4 逐个走。
> 理由：若在阶段 3 一次性声明全部 router，会产生「权限已收窄但范围还没接」的中间态，
> 某些角色的页面会先开始报错。改成每个 router「声明 + 接 scope + 测试」原子完成。

- [x] 3.1 router 级权限声明机制
  - **已完成，且无需新代码**：`PermissionChecker` 本来就是可 `Depends` 的可调用类，
    `app.include_router(router, prefix=..., dependencies=[Depends(PermissionChecker(资源, 动作))])`
    即可把声明挂到 router 级；特权限动在端点上再加一个 `Depends`。
    阶段 4 的迁移模式即「router 声明基线 + 端点覆盖特权动作」。

- [x] 3.2 **完整性守卫测试**（`tests/test_permission_matrix.py`）
  - **已完成**：守卫规则为「每个 /api/ 端点必须满足：有声明 ∪ 公开 ∪ 在 BACKLOG 里」。
    `BACKLOG` 是**只减不增**的迁移待办（25 个前缀），迁移完一个就移除一个。
  - **验证（已做突变测试）**：往非 backlog 前缀塞未声明端点 → 守卫抓到并报出 `GET /api/grades/sneaky`；
    塞到 backlog 前缀（`/api/question`）→ 正确豁免。证明守卫不是空转。
  - 另含三条防退化断言：参考 router 必须 100% 声明、BACKLOG 不含已消失前缀、已声明完的 router 不得赖在 BACKLOG 里。

- [x] 3.3 ~~给 21 个 router 逐个声明基础权限（一次做完）~~ → **并入阶段 4**（方案 B）
  - **已完成**：阶段 4.1~4.7 把 232 个端点全部声明完毕，`BACKLOG` 清空。

### 实施中修正的两处事实

- **端点总数 246**（运行时 `app.routes` 实数），此前报告里的 234 是 AST 静态统计口径，两者差在 `mcp` / `workspace` 等动态注册的路由。
- **已完整声明的 router 有 3 个**（`/api/grades`、`/api/school`、`/api/teacher-applications`），不止 `grade` 一个 —— 三者同为阶段 4 的参考实现。

---

## 4. 逐个 router 迁移（按危害排序）

> 每个 router 一次做完四件事，**一个文件一次提交**：
> ① 在 `include_router` 处声明基线权限 ② 特权动作在端点覆盖 ③ 接 scope 数据范围 ④ 补矩阵测试用例
>
> **迁移完一个，就从 `tests/test_permission_matrix.py` 的 `BACKLOG` 里移除它** ——
> 此后该 router 的任何新端点漏声明都会被守卫挡下。这是 BACKLOG「只减不增」的落地方式。

- [x] 4.1 实现 scope 模块：`RequestScope.from_user()` → `class_ids()` / `allows_class(cid)` / `allows_student(sid)`
  - **已完成**：新增 `app/middleware/scope.py` + `tests/test_request_scope.py`（19 个测试，全绿）。
    `class_ids()` 是唯一计算点，其余方法从它派生。
  - **真实数据实测**：`admin → {1班,2班}`；`subject_lead 海老师 → {1班,2班}`；**`teacher 刘老师 → {2班}`**；`super_admin → {}`。
    刘老师与管理员的范围差异，就是本次修复要的可见结果。
  - **验证**：单测覆盖 7 个角色各自的范围输出（超管=空集、admin=本校全部、subject_lead=本校×本学科、teacher=任教班、student/parent=自己）
  - **验证**：缓存 key 含 `school_id`（若加缓存）

- [x] 4.2 `user.py` — 能重置任意学生密码为 `123456`、能改任意教师 `school_id`
  - **已完成**：router 基线 `student:read` + 9 处端点级覆盖；`RequestScope` 接入 `GET /students`（按可见班级过滤）、
    `GET /student/{id}/detail`、`PUT/DELETE /student/{id}`、`approve`、`transfer`、`reset-password`、`batch-import`；
    教师端点按 `school_id` 收窄并与 token 比对。`/api/users` 已移出 BACKLOG、加入 `REFERENCE_ROUTERS`。
  - **实测（真实账号）**：学生 token 调用户管理 → 403；刘老师重置换班学生密码 → 403；
    admin 把教师挪到别校 → 403；`GET /students` 范围 admin=66 人/hai=66 人/liu=32 人（仅 2 班）。
  - ⚠️ **连带影响（待阶段 5 消化）**：`teacher` 角色对 student 只有 `read`，因此教师端点
    `reset-password` / 调班 / 删除全部 403。`StudentsPage.tsx:416` 的重置按钮对教师仍可见 → 点了报错。
    这正是方案 B 说的"声明早于前端能力清单"的中间态，由阶段 5 的菜单/按钮驱动解决。
  - **验证**：学生 token 调 `POST /api/users/student/{id}/reset-password` → 403
  - **验证**：教师 token 调 `PUT /api/users/teacher/{id}` → 403

- [x] 4.3 `parent.py` — 无需 token 即可给任意学生生成绑定码（`:501`）
  - **已完成**：13 个端点里 9 个本就有 `get_current_parent_id` 守卫（身份取自 token，不接查询参数）；
    补上 3 个裸奔的 —— `send-bind-code`、`notify`、`send-report`。`login`/`register` 保持公开（拿到 token 之前）。
  - **守卫扩展**：`_declared_permission` 现在也认 `get_current_parent_id` / `get_current_user`
    这类「身份守卫」（本人角色不走资源矩阵 —— ADR-0008）。参考实现断言对公开端点豁免。
  - **实测**：三个端点匿名 → 401；家长正常链路（登录/children/notifications/report）→ 200；
    家长给**别人**孩子生成绑定码 → 403，给自己孩子 → 200；学生 token 调家长端点 → 403。
  - ✅ **已删除**（2026-09-11 决定）：三个端点零调用方（前端 / agent 工具 / 脚本全都没有），
    与 `/api/parser/` 同类，按阶段 6 的方式直接删除。`parent.py` 从 13 个端点降到 10 个；
    随之成为孤儿的导入（`PermissionChecker` / `get_current_user` / `RequestScope`）已一并清理，`ruff check app/` 全绿。
  - **验证**：无 token → 401；学生 token → 403；家长 token 给非绑定学生 → 403

- [x] 4.4 `class_api.py` — 身份从 token 取，废弃 `teacher_id` 查询参数
  - **已完成**：router 基线 `class:read` + 3 处端点覆盖；`get_classes` 按 `scope.class_ids()` 过滤，
    **移除 `teacher_id` 查询参数**；`get_class_students` 加班级归属校验。`/api/classes` 已进 `REFERENCE_ROUTERS`。
  - **实测**：匿名 401 / 学生 403；范围 admin=2 班、hai=2 班、**liu=1 班**；
    **刘老师传 `?teacher_id=teacher_hai` 仍只拿到自己的班**（反模式已死）；
    liu → 1班学生名单 403、2班 200；liu PUT/DELETE 班级 403、admin PUT 200。
  - **验证**：教师 token 调 `/api/classes` → 只返回自己任教的班
  - **验证**：学生 token 调 `/api/classes/{别的班}/students` → 403

- [x] 4.5a `analytics.py` + `panel.py`（19 个端点）—— 读任意班级学生数据
  - **已完成**：两处 router 基线 `analysis:read`（4 个员工角色都有，学生/家长没有）；
    新增 `ScopeGuard(param, kind)` 依赖 —— 校验路径参数落在调用者范围内，每端点一行。
    `/api/analytics`、`/api/panel` 已进 `REFERENCE_ROUTERS`。
  - **实测**：匿名 401 / 学生 403；班级范围 admin 2/2、hai 2/2、**liu 1班=403 2班=200**；
    教师范围 `liu 查 teacher_hai → 403`、`liu 查自己 → 200`、`admin 查任意 → 200`。
  - ⚠️ 实施中脚本插入 `ScopeGuard` 时踩到一个语法陷阱：`panel.py` 有两个**连续非默认参数**
    （`class_id, knowledge_point` / `class_id, student_id`），插入点必须在它们之后。已修，ruff 全绿。

- [x] 4.5b `report.py` + `diagnosis.py`（27 个端点）—— 含**学生自助入口**
  - **已完成，采用方案 B**：给 `PermissionChecker` 加 `allow_self` 选项 ——
    本人角色（student/parent）放行，随后由 `ScopeGuard` 收窄到「自己」。ADR-0008 的落地方式。
  - **不能用 router 基线**：基线总是执行，学生会被 `analysis:read` 挡掉。故逐端点声明。
  - **新增 `ScopeGuard` 的 `kind="exam_record"`**：考试记录 → 它所属班级 → 范围（查不到一律 403，不泄漏存在性）。
  - `allow_self` 端点显式清单（13 个）：report 的 5 个 `/student/*` + diagnosis 的 8 个
    `/learning-plan/*` `/plan/*` `/barrier/{student_id}` `/history/{student_id}`。
  - **实测**：学生看自己 200 / 看别人 403 / 调员工端点（班级报告、班级统计、export）403；
    刘老师看自己班学生 200、别班 403；匿名 401。
  - ⚠️ **契约风险（已写进 docstring）**：`allow_self=True` 的端点**必须**做范围校验，
    否则本人角色能读别人数据。守卫测试只能看到"声明存在"，看不到契约是否被遵守。
  - ⚠️ `analysis` 资源在矩阵里只有 `read`，所以 `run-llm`（POST）、`override`（PUT）
    这类写操作也用 `analysis:read` 把关 —— 语义偏松，若要细分需扩矩阵。
  - **验证**：学生 token 调 `/api/analytics/class/{id}/overview` → 403
  - **验证**：教师 token 读非任教班级 → 403

- [x] 4.6 其余 router（**已完成**，除 4.7 的 `integration`）
  - **规模**：14 个前缀 130 个端点里，迁完 11 个前缀 **109 个端点**；另处理 `auth`(6)；
    删除 3 个前缀共 **11 个端点**（`/api/parser/` 5 + `/api/grading` 3 + `/api/mcp` 3）。
    最终 API 路由数 246 → **232**。
  - **验证**：`ruff check app/ agent/` 全绿 / `pytest tests/` **548 passed**
    （阶段 4.5 结束时是 403）/ 新增两个测试文件：`test_permission_roles.py`(45)、
    `test_conversation_ownership.py`(17)，`test_permission_matrix.py` 21 → 103。
    所有新增断言都做过**突变测试**（改动被保护的代码 → 断言必须变红），共 11 次全中。
  - **E2E（真实无头浏览器，5 场景）**：全部 `缺token 0 / 4xx5xx 0 / 控制台错误 0` → OK。
    教师端×2（admin / hai）· 学生端 `m/` · 家长端 `m/` · legacy `ocr-sheets.html`。
    其中**学生端与家长端的流式对话端点真的被调用了**（`流式=True`）—— 正是本次改动
    风险最高的两条链路，归属校验没有打断它们。
    ⚠️ 覆盖缺口：E2E 的教师端场景没发对话消息（`流式=False`），所以**教师端 chat 流式**
    与 `/api/agent/upload` 只被单测覆盖、没有 E2E 证据。
  - **已完成（4.6 第一批）**：
    - **删除 `/api/parser/`**（决策 20，5 个端点零调用方）；底层 `chem_skills.chemistry_parser` 库未动
    - **`POST /api/logs` 加管理员校验** —— 此前完全无鉴权，任何 token 可伪造审计日志并冒用 `user_id`。
      `/api/logs` 已进 `REFERENCE_ROUTERS`（两个端点都有声明）
    - **`/api/knowledge`（2）**：router 基线 `knowledge:read`
    - **`/api/workspace`（3）**：router 基线 `workspace:read`
  - **矩阵扩展（2026-09-12 与项目方确认）**：原矩阵只覆盖「学校治理」域，**内容生产完全没覆盖**，
    且把任课教师写成了全只读 —— 与前端实际用法矛盾（教师端 `question.py` 4 处、`exam.py` 8 处都在写）。
    新增 11 个内容资源（`question` / `exam` / `exam_bank` / `grading` / `ocr` / `practice` /
    `notification` / `warning` / `knowledge` / `memory` / `review` / `workspace`）。
    约定：**任课教师能出题建考试**；学科组长同权；**教务管理员能建能改不能删**
    （沿用设计文档「不能删年级 / 不能建删教师」的同一惯例）。
  - **已完成（批次 A，2026-09-12）**：`question`(22) / `exam`(12) / `exam-bank`(9)。
    router 基线 + 写操作覆盖 create/update/delete；`ScopeGuard` 接 `class_id`(class) /
    `exam_record_id`(exam_record) / `student_id`(student)；`POST /exam/create` 的
    `class_id` 在请求体里，就地校验。**删除 `/api/grading`(3)** —— 整个前缀零调用方，
    且与 `/api/ocr/grading/*` 是同一件事的两份实现（UI 用的是后者）。
    矩阵调整：`exam_bank` 的教师/学科组长从 `_R` 提到 `_CRU`（教师端 `ExamPage` 有
    建题库、导入题目共 5 处调用）；**删除仍留管理员** —— `ExamRecord` 无创建者字段、
    `QuestionSet.teacher_id` 由客户端自报，放开删除等于「教师可删全校任意考试/题库」。
  - **已完成（批次 B）**：`ocr`(21，`ocr.py` + `ocr_sheets.py` 同一前缀)。
    顺带修掉 `GET /api/ocr/tasks` 的泄漏：`teacher_id` 由调用方自报且**留空即返回
    所有教师的任务**，改为身份取自 token（校级管理员仍可看全校并按 `teacher_id` 筛）。
    ⚠️ 学科组长本该看「本校×本学科」，但 `OCRTask` 没有 class_id/subject 可推导，
    故一律收窄到自己（fail-closed，已写进 docstring）。
  - **已完成（批次 C）**：`notification`(13) / `warning`(5) / `memory`(3)。
    `notification` **不能用 router 基线** —— `GET /parent/{parent_id}/notifications`
    是家长端点，加基线会把家长自己的通知挡掉；改逐端点声明。
    `GET /student/{student_id}/notifications` 补 `allow_self`（此前学生读不了自己的
    通知、家长读得了自己的，两边不对称）。
  - **已完成（批次 D）**：`practice`(18) / `review`(6)，全部逐端点声明。
    ⚠️ **这里不能加 router 基线**：`include_router(dependencies=[...])` 的基线总是执行、
    且在端点自己的依赖之前，给 `/api/practice`、`/api/review` 加基线会把 `allow_self`
    里的学生挡在端点外 —— 与 4.5b（report/diagnosis）同一个坑。已加结构性防线
    `test_allow_self_endpoint_is_not_blocked_by_a_router_baseline` 防复发。
    顺带修掉三个同类泄漏（`student_id` 是可选查询参数、**留空即返回/修改所有学生**）：
    `GET /practice/wrong/list`、`GET /practice/review/list`、
    `POST /practice/wrong/{question_id}/master`。
  - **已完成（auth 白名单收窄）**：`PUBLIC_PREFIXES` 的整段 `/api/auth/` 改为逐条
    `login` / `refresh` / `apply`；`me` / `logout` 移出并加身份守卫。
    `GET /me` 无 token 现在是 **401**（此前 200 + `success:false`）。
  - **已完成（批次 E）**：`agent`(9) + **新增会话归属表**。
    新增 `conversation_owners` 表与 `middleware/conversation.py`（唯一判定点）。
    改造前 `thread_id` 是 `{prefix}{毫秒时间戳}`（**可枚举**）且不记录归属 ——
    任何登录用户都能列出/读取/删除任意会话。现在 list/history/delete/stream/resume/reset
    全部按归属校验；`resume` 原来回退到共享的 `"default"` 线程（等于所有人共用一个会话）已去掉。
    **老会话兜底**：员工角色认领 `t-`/`c` 开头，本人角色一律 403。实测依据：
    checkpoint 库 1316 个线程里 1208 个是 `eval` 前缀（评测框架），真正的用户会话
    只有 `t-`(9)/`m-`(16)/`p-`(11) —— 影响面很小，教师那 9 条是主要演示面。
    ⚠️ **实施中发现（改变了方案）**：**三个自助端都会自己造 thread_id** ——
    学生端 `m/index.html:152`（无 sessionStorage 时）、家长端 `m/parent.html:632`、
    legacy 教师端 `js/agent.js:43`。`/chat/new` 只被"新对话"按钮和 React 教师端用到。
    也就是说**会话身份从来不由服务端产生**，任何"必须先在 `/chat/new` 登记"的设计
    都必然漏掉它们。
    故「**首次使用时登记**」不是兜底而是**正式规则**：`require_owned` 的判据是
    「checkpoint 库里有没有这个会话」—— 没有=全新，就地登记；有且无主=老会话，按
    前缀策略。这样三个自助端**零前端改动**即可工作（前端规范化归入阶段 5）。
    已知代价：能猜中别人未来某毫秒 id 的人可以抢先占掉它、让对方 403 一次 ——
    只造成困扰、不泄漏内容。
    ⚠️ **同批修掉一个越权洞**（用 lgh 验收时抓到）：`require_owned` 走到「就地登记」
    这一支后**无条件放行**，而 `claim_conversation` 对已有归属是 no-op（防抢注）→
    **「已属他人、但 checkpoint 里还没内容」的会话任何人能读**。修法是登记后复验。
  - **存量老会话显式回填**（`python -m app.utils.migrate`，幂等）：
    老会话在 checkpoint 数据里**没有任何身份线索**（msgpack 只有 messages / 路由信息，
    `ChatRequest.student_id` 没落进图状态），只能按「这个部署是谁在用」显式回填：
    `p-*`(12) → `parent_demo_001`(lgh，唯一家长账号)；`m-*`(16) → `202610201`(李雨萱，
    演示学生账号)；`t-*`(9) 不回填（员工前缀兜底已覆盖）。账号映射是模块常量
    `LEGACY_CONVERSATION_OWNERS`，不做任何猜测；账号不存在就整条跳过。
  - **以 lgh 为对象的验收**（真服务 + 真账号，12 项全通过）：lgh 列表 12 条 /
    读自己的老会话 200 / **另一个家长读同一条 403** / 另一个家长列表 0 条 /
    学生列表 16 条 / lgh 读全新自造 id 200（首次登记）/ 另一个家长读该新 id 403 /
    匿名 401 / 家长列 `t-` 0 条。用 `/chat/history` 而非 `/stream` 验证归属 ——
    同一个 `require_owned`，但不真调 LLM。
  - **决策记录（2026-09-12 与项目方确认）**：
    - ✅ **已删除 `/api/mcp`(3) + `app/mcp/`** —— 零调用方，且**不是真 MCP**（手搓 HTTP JSON，
      无 JSON-RPC 2.0 / `initialize` 握手），真 MCP 客户端连不上，留着也服务不了它
      唯一被写下来的用途（Hermes 集成）
    - 保留 `/api/memory`(3) 并接权限（规划中的功能面，与 grading 那种重复实现不同类）
    - 约 40 个单个零调用方端点（question 7 / ocr 9 / notification 9 / agent 2…）
      **一律保留并接权限，不删** —— 大多是「前端只做了一半」的功能面，删代码是阶段 6 的活
    - 矩阵新增 `agent` 资源（四个员工角色同权、都含 delete）—— 会话是**每人自己的数据**，
      角色只区分「能不能用这个功能」，真正的作用域由归属表决定，故刻意不做动作区分
  - **（4.7 见下，已完成）**
  - **⚠️ 待提醒**：`/api/workspace/*` 是**服务器本地文件系统的目录浏览器**
    （列目录 + 建目录），模块 docstring 的设计前提是「单机部署 = 老师本机」。
    若将来部署到真正的服务器上，这个端点需要重新评估。
  - **验证**：每个 router 至少一组「角色 A 能 / 角色 B 不能」的断言 → 已落地为
    `tests/test_permission_roles.py`（真发请求，54 条），并做过突变测试确认非空转。

### 4.6 实施中发现、需要项目方定的事

- ~~**`super_admin` 角色没有任何内容资源键**~~ → **已定**（2026-09-12）：
  超管能力**镜像 admin**（见 4.7），数据范围仍为空集（ADR-0011）。
  注意区分：这个角色**至今没有任何账号在用**（0 行），唯一的管理员账号是 `admin`，
  它一直权限齐全、E2E 实测全通过。此处只是把 0.4 建超管账号时要做的决定提前定了。
- ~~**`GET /api/auth/apply/{app_id}` 是 IDOR**~~ → **已修**（2026-09-12）：
  `app_id` 改为 `app_{时间戳}_{12位 hex}`，把「按时间枚举」堵死。存量
  `teacher_applications` 表 **0 行**，无需迁移。
  **决策记录（为什么是修不是删）**：这条流**两侧前端都还没做**（`apply` 与配套的
  `/api/teacher-applications` 都零调用方），所以它不是「废弃/被取代」（那才是
  `/api/parser/` `/api/grading` `/api/mcp` 的情况），是「还没开始建」。
  而且删提交侧会连累管理侧 —— 管理端点会指向一张永远写不进数据的表、页面永远空；
  真要删得两边一起删（7 个端点），那是产品决策不是权限改造的活。
### ~~矩阵动作不够用导致的「语义偏松」~~ → **已解决**（2026-09-13，`4fc1655`）

原来是这 5 处：`memory`/`warning`/`review`/`analysis` 的写端点只能借 `read`（或 `update`）
把门。处置：**扩矩阵，给每个写端点它自己该用的动作。**

关键是**先把这一类找全再改** —— 我原先列的是 5 处、实际是 **14 个端点**。
新增守卫 `test_write_endpoints_are_not_gated_by_read_alone`（写动词的端点不能只用
`read` 把关），它当场多报出 8 个：7 个确实是只读（搜索 / 连接测试，登记进
`WRITE_VERBS_THAT_ARE_READS`），**1 个是真的**：

> **`POST /api/workspace/mkdir` 用 `workspace:read` 把门** —— 它在服务器文件系统上
> **建目录**。四个员工角色本来就有 `workspace:create`，改门不改变可见性。

**矩阵新增**：`analysis` 加 create+update · `memory` 加 create · `warning` 加 create ·
`review` 加 create+update · `notification` 给三个非 admin 员工角色加 update。

⚠️ **一处有意放宽**：`notification` 的「标记已读 / 订阅 / 退订」从**只有 admin** 放宽到
四个员工角色（那本来就是自助动作）。**删除通知仍是 admin**（破坏性，保留限制）。
这四个端点零调用方，线上行为无变化。

**可见性守恒**：其余 13 个端点做过**逐条新旧对照** —— 能过的角色集合完全一致，
扩动作只修语义、没让任何人多进或少进一个端点。

**验证**：新增守卫 + 7 条显式登记（两个方向都校验）+ 语义钉表补 12 行；
突变验证把 mkdir 改回 read → 守卫变红；flows 验收 31/31、主验收 5 场景全绿。
- **`chem_skills/chemistry_exam/handler.py` 链路是断的（既有破损，非本次引入）**：
  它走 HTTP 调 `/api/question/*`，但 `_templates/base_handler.py` **完全不带
  Authorization 头** —— 阶段 2.1 把 `/api/question/` 移出白名单那一刻起就在 401。
  只报告不顺手修（按 CLAUDE.md）。
- **`tests/conftest.py` 有 7 个 ruff 问题**（E401/E402/F401）、
  **`tests/test_api_auth_notification.py` 有一处未使用的 `datetime` 导入** ——
  均为既有问题，且 `tests/` 不在 `ruff check app/` 的基线口径内。只报告。

- [x] 4.7 `integration.py` — 16 个管理端点限 `admin` / `super_admin`
  - **已完成**：15 个限管理员（LMS 配置 / Webhook / API 密钥 / SFTP / 集成日志），
    走新增的 `integration` 资源键；`integration.py` **逐端点声明**（不能加 router
    基线 —— 前缀下有个必须公开的端点，见下）。
  - ⚠️ **一处刻意偏离本条原文**：`GET /lti/.well-known/jwks.json` 保持**公开**。
    LTI 1.3 规范要求平台在**无鉴权**的情况下抓取工具的 JWKS 来验签 —— 锁上等于
    把 LTI 协议本身弄坏；JWKS 装的本来就是公钥（设计上就该公开）。
    已加进 `PUBLIC_PREFIXES`，并加断言 `test_lti_jwks_is_public_by_design` 钉住，
    防止将来做真 LTI 实现时顺手锁上（它现在只是个返回假密钥的 TODO 桩）。
  - **超管能力对齐管理员**（2026-09-12 项目方确认「超管账号应当有管理员的全部权限」）：
    `ROLE_PERMISSIONS['super_admin']` 镜像 admin，**深拷贝**（不共享 list 对象，
    防「改 admin 悄悄改掉超管」）。与 ADR-0011 不冲突 —— 「能不能调端点」（能力）
    与「能看到哪些数据」（范围）是两层：超管能力齐全，但 `RequestScope` 仍返回空集，
    跨校看数据要走 break-glass。
    ⚠️ **这依赖「每个端点都接了范围校验」**：只声明能力没接范围的端点，超管会直接
    拿到全量数据。新增端点时别忘这一层。
  - **🎯 BACKLOG 清空** —— 至此每个 /api/ 端点要么带声明、要么是公开端点，
    没有任何前缀还享受豁免。**这是阶段 4 的收官标志**，此后新增端点漏声明会被
    守卫直接拦下。
  - **验证**：教师 token 调 `/api/integration/api-keys` → 403 ✅
    （另含学生/家长/学科组长 403、admin 通过、匿名 401、JWKS 免 token）
  - **验证**：`python -m pytest tests/test_permission_matrix.py -q` 全绿

---

## 5. 前端能力清单（**已完成**）

> ⚠️ **先记住一条**：菜单过滤与路由守卫都是 **UX 一致性，不是安全边界** ——
> 真正的边界是后端那 232 个端点（阶段 4 已落地）。守卫写错只会让人看到点不动的
> 菜单/页面，不会漏数据。别把这里当成权限的落点。

- [x] 5.1 登录响应加 `role_label` + `permissions` + `menus`
  - **已完成**：加在 `get_user_info()` 里 —— 它是 login / refresh / `/me` 三处的**共同来源**，
    所以能力清单只在这一处算，三个端点天然一致，不会有哪个端点忘了带。
  - `ROLE_LABELS`（7 个角色的中文显示名，阶段 0.1 要的那张表；`Role` 枚举本身仍待补）、
    `MENUS`（菜单注册表，**每项声明它需要的资源/动作**，由 `menus_for()` 从矩阵派生）
  - 后端只下发**菜单 key 列表**；path / 中文名 / 元素符号留在前端。
    权限单一真源在后端，展示单一真源在前端
  - 实测：admin/super_admin 7 项（含 `integration`）· academic_admin/subject_lead/teacher
    6 项 · **student/parent 0 项**
  - **验证**：`test_menus_are_derived_from_the_matrix`（菜单每一项必须等价于
    `can(role, 资源, 动作)`，防「菜单写死一套、矩阵改另一套」）+ 7 角色中文名齐全 +
    死菜单检测。突变验证：把 integration 菜单误指向 analysis → 3 条断言变红

- [x] 5.2 存储能力清单
  - **已完成**：`lib/api.ts` 加 `getCaps/setCaps/can/hasMenu/fetchCaps`；
    `clearAuth()` 一并清 caps（不然退出后残留上一角色的菜单）。
    新增 `lib/use-capabilities.ts`：优先本地缓存；本地没有但**有 token** 时拉 `/me` 水合 ——
    阶段 5 之前登录的老会话、清了 localStorage 都能自愈。坏数据当作「没有」触发水合
  - ⚠️ **顺手修掉一处重复**：`LoginPage.tsx` 自己抄了一份登录逻辑、不走 `lib/api` 的
    `login()` —— 能力清单因此存不进去（登录后还得靠 `/me` 补一次）。已改为调共享的 `login()`
  - **验证**：刷新页面角色仍在（本地缓存 + `/me` 兜底，两条路都通）

- [x] 5.3 菜单由 `menus` 驱动，路由守卫加角色判断
  - **已完成**：`NAV_ITEMS`（写死 6 项）→ `MENU_REGISTRY` + 由后端 key 派生，
    **顺序沿用后端下发**。认不出的 key 跳过并 `console.warn` —— 静默丢弃会表现成
    「后端加了菜单、前端就是不显示」，很难查
  - `ProtectedLayout` 区分三种状态：无 token → 弹回登录页；拉清单中 → 转圈；
    **有身份但没菜单 → 专门的「无教师端权限」页**（学生/家长）。**不能**弹回登录页 ——
    刚登录成功又被弹回去，用户会以为登录失败、反复重登
  - `RequireMenu` 路由守卫：没有对应菜单 → 送到它能进的第一页
  - **验证（真无头浏览器，脚本 `_e2e_verify.phase5.py`）**：
    管理员侧边栏 7 项含「LMS 集成」/ 教师 6 项无它 / **两者菜单不同** ✅
    教师直接敲 `/#/integration` → 被送到 `/#/chat` ✅
    学生直接敲 `/#/chat` → 显示「没有教师端权限」页 ✅

- [x] 5.4 LMS 集成页面：`API密钥` + `Webhook` 两个 Tab
  - **已完成**：`IntegrationPage`，入口只对 `integration` 菜单可见
  - **验证**：`admin` 可见入口、`teacher` 看不到 ✅（E2E 实测）
  - ⚠️ **顶部如实标注这是展示性占位** —— 后端现状（4.7 时核实）：`GET /api-keys`
    是硬编码空列表 + TODO、密钥不落库；`WebhookService.webhooks` 是**进程内存字典、
    重启即丢**。不说清楚的话，管理员创建完密钥一刷新就没了，会当成 bug 报上来
  - `POST /api-keys` 的 `name`/`permissions` 是**查询参数**（端点没有 Pydantic 模型），
    列表要用重复 key 传 —— 前端按真实契约拼的

---

## 6. 死代码清理（可独立于 2~5 进行）

- [x] 6.1 删除 `app/api/parser.py` 全部 5 个端点 + `main.py` 的注册 + 白名单项
  - **已完成**：随阶段 4.6 第一批一起做的（`b2eb47c`）。核对：`app/api/parser.py`
    不存在、`main.py` 里 `parser` 出现 0 次

- [x] 6.3 删除 `teachers.role` 列（承接 0.2）
  - **已完成**：随 0.2 一起做的。核对：`teachers` 表现有列
    `[teacher_id, school_id, name, phone, status, created_at, updated_at]` —— 无 `role`；
    `migrate.py` 里显示「teachers.role column already absent, skip」

- [x] 6.2 清理 `classes.teacher_id`（**分两半**）
  - **上半 ✅ 已完成（`66b56b7`）**：停止读那个字段。
    `classes.teacher_id` 建表时被写死 `None`（init_db 的 `teacher_id=None`），
    所以**三处都在静默失效**：
    | 位置 | 症状 |
    |---|---|
    | `class_api.get_classes` | 班主任 `teacher_id`/`teacher_name` 恒 null、`is_class_teacher` 恒 False |
    | `panel.get_teacher_overview` | 「教师管理的班级」永远查不到，只靠硬塞 `demo_class` 兜着 |
    | `report`（教师总览分支） | `class_ids` 恒空 → 永远返回空考试列表 |
    统一改从 `teacher_class_subject` 取（任课/班主任关系的真源）：班主任 = `is_class_teacher`
    的那位；「教师所带班级」= `join teacher_class_subject`。`init_db` 去掉写死的 `teacher_id=None`。
    **实测**：`teacher_hai → [class_2025_1, class_2025_2]`（修复前空）、
    `class_2025_1 班主任 = 海老师 / class_2025_2 = 刘老师`（修复前 null）。
  - **下半 ✅ 已完成（`567e400`）**：真正删掉那一列。三处一起改：`Class.teacher_id`
    列 + `Class.teacher` relationship + `Teacher.classes` 反向关系（后两者全仓库零引用，
    但**必须一起删** —— 它们的 join 条件就是这个外键推出来的）+ 测试里两处
    `Class(..., teacher_id="t1")`。
    **删列踩了两个坑**（都写进 `migrate.py` 注释了）：
    1. **不能直接 `ALTER TABLE DROP COLUMN`** —— 该列在 `classes` 自己的**表级外键**里，
       SQLite 不允许删被表级 FK 引用的列，也没有 `DROP CONSTRAINT`。
       **别照 `teachers.role` 的先例想当然**（那个能直接删是因为没有外键）。只能整表重建。
    2. **`PRAGMA foreign_keys` 是逐连接的、且在事务里是空操作** —— 换连接设无效；
       在 SQLAlchemy 连接上先 execute 再 `begin()` 会 autobegin 冲突。最后用底层
       DBAPI 连接才成。
    **安全措施**：动手前备份 `chemai.db`；全程一个事务 + `foreign_key_check` 校验后才提交
    （**实测失败过两次，旧表两次都原样还在** —— SQLite 的 DDL 是事务性的）。
    **验证**：幂等（再跑输出 `already absent, skip`）；数据核对 2 个班（34/33）/66 学生/
    外键完整性与删列前一致；真服务回归班主任仍正确、三个账号数据齐全。
  - **验证（上半）**：`GET /api/classes` 的班主任为真实值 ✅ /
    前端 `ClassPage.tsx` 零引用该字段 ✅（实测 0 处）
  - **验证**：新增 `test_class_list_returns_real_head_teacher`；突变验证 —— 把实现
    改回读 `classes.teacher_id` → 断言变红

---

## 7. 端到端验证

- [x] 7.1 表驱动矩阵测试覆盖 7 角色 × 全部端点
  - **已完成，做成两层**（全部端点 × 7 角色逐格手写不现实，也没必要）：
    - **不变量（覆盖全部 232 个端点）**：本人角色只能经 `allow_self` / 公开 /
      身份守卫进入；例外按 `(角色, 端点)` 显式登记，并用「白名单只减不增」反向校验
    - **显式决策表**：17 个代表端点 × 7 角色逐格标出 A/D/P，整张矩阵一眼可见
  - **它抓到的真问题**：`/api/logs` 的门是**借来的** `grade:read`，而学生恰好有那个键 ——
    权限层对他们是开着的，真正拦住的是函数体里手写的 `role != "admin"`（矩阵之外的
    第二套授权）。已给它独立的 `log` 资源键并删掉手写判断。
  - **验证**：`pytest tests/test_permission_matrix.py -q` → **153 passed** ✅
  - **验证**：完整性守卫绿（BACKLOG 已清空）✅
  - **突变验证**：误给 `parent` 一个资源键 → 不变量变红

- [x] 7.2 三条真实链路走查（**真服务 + 真账号**，脚本 `_e2e_verify.flows.py`，31/31 通过）
  - **教师端** ✅ 学科组长（hai）看到全校本学科 **2 个班**；任课教师（liu）只看到自己
    任教的 **1 个班** —— 两者范围确实不同。
    ⚠️ 原文写「看不到数学班」，但**真实库里两个班都是化学、没有数学班**，
    所以改用「范围收窄的差异」来表达同一件事。
  - **学生端** ✅ 读自己的练习任务/报告 200；读别人的练习任务/报告 403
  - **家长端** ✅ 读绑定学生（202610201）的报告 200；读非绑定学生 403

- [x] 7.3 越权尝试回归（**每条都被拒**，同上脚本）
  - 学生：删班级 403 / 改他人诊断 403 / 读他人报告 403 / 读他人练习 403 /
    列全部学生 403 / 读操作日志 403
  - 教师：读非任教班级名单 403 / 读非任教班级学生详情 403 / 重置学生密码 403 /
    删班级 403 / 读集成配置 403
  - 匿名：8 个非白名单端点（classes/users/question/exam-bank/warning/agent/integration/logs）
    **全部 401**
  - **另加对照组**（管理员读班级 / 海老师读名单 / 刘老师读自己班学生 / 学生读自己报告 /
    家长读绑定报告 / 公开登录端点）**全部通过** —— 没有对照组的话，「全拒」也会显示全绿，
    那种绿是假的

- [x] 7.4 超管 break-glass 走一遍（**ADR-0011 此前只有决策、没有实现**）
  - **已完成**：新增 `break_glass_sessions` 表 + `middleware/break_glass.py` +
    三个端点（开提权 / 查生效状态 / 提前结束）。**判定在读时做**（`expires_at` 到点即失效），
    不需要定时任务，服务重启、时钟跳过都不会让权限残留。审计写 `operation_logs`。
  - **验证（真服务 + 真账号，脚本 `_e2e_verify.breakglass.py`，14/14 通过）**：
    - 超管默认看不到任何学校数据 ✅（`/api/classes` 0 个班、`/api/users/students` 0 个学生）
    - 发起 break-glass 后可见 ✅（跨校看到 2 个班）+ **有审计记录** ✅
      （`acc_super / break_glass_start`，detail 带理由与到期时间、指向同一次提权）
    - 超时后自动失效 ✅（状态为无、重新看不到数据）
    - 边界：校级 admin 403 / 匿名 401 ✅
  - **突变验证**：去掉提权判定让超管直接放开 → 5 条断言变红（含「默认空集」）

---

**依赖关系：**
```
0 (角色模型)
 └─▶ 1 (前端铺垫) ─▶ 2 (白名单收缩) ─▶ 3 (默认拒绝骨架) ─▶ 4 (接 scope) ─▶ 5 (前端能力清单)
                                                                              └─▶ 7 (端到端验证)
 6 (死代码清理) ─ 独立，任何时候可做，6.3 依赖 0.2
```

**关键约束：**
- 阶段 1 **必须**在阶段 2 之前完成，否则学生端对话 401
- 阶段 2 与 4 之间存在中间态：任意有效 token 仍能读任意数据 —— 4.2 / 4.3 排最前以缩短窗口
- 每个 router 一次做完，不留半途；完整性守卫跟着走

**估时（人天）：** 阶段 0: 1 | 阶段 1: 0.5 | 阶段 2: 0.5 | 阶段 3: 2 | 阶段 4: 6~8（139 个端点） | 阶段 5: 2 | 阶段 6: 0.5 | 阶段 7: 1 → **约 14~16 人天**

阶段 4 是绝对大头，且没有捷径（除非接受自动注入查询条件的魔法方案，已在设计阶段否决）。

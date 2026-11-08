# 交接说明 —— 权限机制改造

> 下次开新会话时把这个文件丢进去即可接续。
> **规范状态在 [`tasks.md`](./tasks.md)**（已完成 / 剩余 / 待定项都在里面），本文件只写
> 那些**别处没记、不知道就会踩坑**的东西。

---

## 一句话背景

用户反馈「登录超级管理员和 hai 老师，感觉权限都差不多」。审计发现 246 个 API 端点里
只有 11 个（4.5%）真正做了角色判断，75 个连 token 都不需要。根因不是"有人写错了检查"，
而是**"没写检查不会报错"**。本次把权限机制从纸面落到请求链路。

## 工作区状态（⚠️ 最容易出事的地方）

- **⚠️ authz 有自己的分支 + 自己的 worktree：`feature/rbac-enforcement` @ `D:\化学-rbac`。
  在这个目录里干活，别去主工作区。** 2026-09-12 曾长期提交到项目方当时签出的分支上，
  结果两条工作线的提交**交替插在同一条线性历史里**（项目方的 `spec #N` 提交和 authz
  提交互相夹着），而且两边在同一个工作区里来回切分支、互相把对方的未提交改动带走。
  故改用 worktree 彻底隔离。
- **本仓库用 worktree 并行开发**（`git worktree list`）：
  | 路径 | 分支 | 谁的 |
  |---|---|---|
  | `D:\化学` | `feature/zcode` | 主工作区（项目方） |
  | `D:\chemai-wt-planloop` | `feat/plan-confirmation-loop` | 项目方 |
  | `D:\化学-test` | `test` | 项目方 |
  | `D:\化学-rbac` | `feature/rbac-enforcement` | **authz（我）** |
- **新 worktree 的坑**：worktree 只含**被跟踪的文件**，被 ignore 的运行时数据要自己接过来。
  已用软链/junction 接好（**单一真源**，两边看到同一份数据）：
  `chemai.db` / `chemai_checkpoints.db` / `chemai_store.db` / `.env`（软链到主工作区），
  `frontend/node_modules`（junction）。**换新 worktree 时照做一遍**，否则会看到
  `no such table: warning_logs` 这类假失败。
- 交错历史**故意没剥离**（rebase 会冲突、且当时工作区有在飞文件）—— 项目方分支上
  仍然"含有"authz 的历史提交，既成事实，功能上无害。
- **提交前先 `git branch --show-current`**（确认是 `feature/rbac-enforcement`）。
- 工作区里**同时有用户自己未提交的改动**（`agent/tools/exam_bank.py`、
  `tests/test_web_search.py`、`chem_skills/chemistry_memory/memory_data/*`、
  `DESIGN.md`、`UI组件/`、`design-demos/*` 等）。

**提交时只 stage 自己动过的文件，永远不要 `git add -A`。** 上一轮提交的过滤命令可以复用：

```bash
git diff --cached --name-only | grep -E "agent/|package.json|agent-stream|MessageList|ChatPage|test_approval|test_history|test_send_conf|\.archive" || echo "干净 ✓"
```

## 已提交的 commit

| commit | 内容 |
|---|---|
| `436d935` | 阶段 0~4.5a：角色模型 / 默认拒绝 / 数据范围 / scope 模块 / user / parent / classes / analytics / panel |
| `d4fa9d5` | 阶段 4.5b：report / diagnosis（含 `allow_self` 设计） |
| `b2eb47c` | 4.6 第一批：内容资源矩阵扩展 / 删 `/api/parser/` / `POST /api/logs` 补鉴权 / knowledge + workspace 基线 |
| `b4220de` | 4.6 批次 A：question / exam / exam-bank（43 端点）+ 删 `/api/grading` |
| `2471a02` | 4.6 批次 B：ocr（21 端点）+ 修 `/api/ocr/tasks` 身份取自 token |
| `dc99a45` | 4.6 批次 C：notification / warning / memory（21 端点） |
| `39ba940` | 4.6 批次 D：practice / review（24 端点，`allow_self` 学生自助） |
| `5761692` | 4.6：auth 白名单收窄，me/logout 移出 |
| `d49c4ca` | 4.6 批次 E：agent 9 端点 + 会话归属表；删 `/api/mcp` |
| `3f6c476` | 修家长端会被 403（补「全新会话首次认领」） |
| `45ed96e` | 修归属两个洞（复验登记结果）+ 存量老会话显式回填 |
| `6fa922a` | 4.7：integration 16 端点 + 超管能力对齐 admin，**BACKLOG 清空** |
| `695d2fe` | 修 `/api/auth/apply/{app_id}` 的 IDOR（app_id 不可枚举） |
| `d5a9cbc` | 5.1：登录下发 `role_label` / `permissions` / `menus` |
| `bd852be` | 5.2~5.4：能力清单落前端（菜单派生 / 路由守卫 / 无权限页 / LMS 集成页） |
| `6443b4e` | authz 改用独立 worktree（与项目方彻底隔离） |
| `15fc005` | 7.1：7 角色 × 全部端点的决策表 + 修 `/api/logs` 借用的伪门 |
| `a6306dc` | 0.4 + 7.4：超管账号 + break-glass 提权（ADR-0011 落地） |
| `ad5f1f2` | 0.1 / 0.5 + 7.1~7.4 收尾：Role 清单统一、矩阵完整性断言 |
| `115e4f4` | 消除 `grade` 键语义重叠（学生不再能列学校年级） |
| `567e400` | 6.2 下半：删掉 `classes.teacher_id` 列（整表重建） |
| `4fc1655` | 扩矩阵动作：14 个写端点不再借 `read` 把门 |
| `fc68fa0` | 文档：5 处语义偏松标记为解决 |
| `2721c01` | ADR-0014 决策：Agent 工具层纳入 Data Scope（接缝统一校验） |
| `718d9f1` | ADR-0014 第一步：身份上下文扩为完整身份（user_id + role + school_id），三个 agent 端点都注入 |
| `255d01e` | ADR-0014 第二步：`TOOL_META` 加 `scope` 声明 + 完整性守卫（L0） |
| `7b62685` | ADR-0014 第三步：接缝执行数据范围校验（封上家长查别人孩子那条路） |
| `8d6bcc0` | 修前端：登录失败不再崩页面 |
| `6bd514e` | ADR-0014 第四步：评测身份按 persona 解析真实账号 + 场景引用换新数据 |
| `a186471` | 修候选泄漏：姓名搜索的范围过滤挪到「搜」的时候 |
| `c920173` | ADR-0014 落地记录 + HANDOFF 换新账号 |
| `11e3d71` | **merge: main 并入本分支**（36 个提交，9 处冲突 + 2 处假成功，见下节） |

> `test` 分支另有 `8e3c3a3`（聊天修复：建议卡改为填进输入框）已并入 main。

**阶段 0~7 全部做完，ADR-0014（agent 工具层的 Data Scope）四步全部落地。** 剩下的见下面「还没做」。

## 别处没记、但会踩的坑

**1. Playwright 版本对不上**
Python 包要 chromium build **1223**，机器上装的是 **1234**。必须显式指定：
```python
p.chromium.launch(executable_path=r"C:\Users\Administrator\AppData\Local\ms-playwright\chromium-1234\chrome-win64\chrome.exe", headless=True)
```

**2. React 教师端是 HashRouter**
测页面必须用 `/#/class`、`/#/students`，**用 `/class` 页面根本不加载** —— 我第一轮 E2E
就是这样假绿的，什么都没测到。

**3. legacy 页不能用 `wait_until="networkidle"`**
`ocr-sheets.html` 引了外部 CDN 字体，请求挂住就永远不算 idle（页本身 8ms 就返回 200）。
用 `domcontentloaded`。

**4. E2E 脚本在 `chemai-backend/_e2e_verify.perms.py`**
被 `.gitignore` 的 `/_*.py` 规则忽略（所以不会进 git）。端口写在文件顶部 `BASE`，
每次换端口记得改。

**5. 守卫测试的 `BACKLOG` 是「只减不增」的**
迁移完一个 router 必须把它从 `BACKLOG` 移除、加进 `REFERENCE_ROUTERS`，
否则 `test_fully_declared_routers_are_not_in_backlog` 会红。
新端点若在未迁移的 router 里可以豁免，否则守卫会拦。

**6. `teachers.role` 已整列删除**
`migrate_role_values` 现在**只处理 `accounts.role`**（原来的版本会去 UPDATE 一个已被删掉的列，
我踩过这个顺序 bug）。角色唯一真源是 `accounts.role`。

**7. `allow_self=True` 的契约**
本人角色（student/parent）会被放行，**必须**靠端点自己收窄到「自己」：路径参数用
`ScopeGuard`、请求体/查询参数用 `require_student`、不透明 ID（如 `task_id`）先落到
学生再判范围（见 `POST /review/submit`）。
守卫测试只能看到"声明存在"，**看不到契约是否被遵守** —— 契约由
`tests/test_permission_roles.py` 里的「学生能读自己的 / 读同学的必须 403」钉住。
4.6 之后它被用在 report / diagnosis / practice / review / notification / agent 六个前缀。

**8. `/api/workspace/*` 是服务器本地文件系统浏览器**
列目录 + 建目录。模块 docstring 的前提是「单机部署 = 老师本机」。**若部署到真服务器，要重新评估。**

**9. ⚠️ router 基线会吃掉 `allow_self`（4.6 批次 D 当场踩到）**
`include_router(dependencies=[Depends(PermissionChecker(...))])` 的基线**总是执行**，
而且**在端点自己的依赖之前**。所以给一个「学生也要用」的前缀加基线，学生会先被
基线挡掉，端点上写的 `allow_self=True` 根本没机会生效 —— 表达出来的现象是
「明明写了 allow_self，学生还是 403」。
- 4.5b 在 report/diagnosis 上踩过，4.6 批次 D 在 practice/review 上又踩了一次
  （写的时候以为对，4 条角色断言当场变红）
- **规则**：前缀下有本人角色（student/parent）端点 → 只能逐端点声明，不能加基线
- 已加结构性防线 `test_allow_self_endpoint_is_not_blocked_by_a_router_baseline`，
  它会在你给这类前缀加基线时直接变红

**10. `student_id` 是可选查询参数的端点 = 隐藏的「返回所有人」**
本项目反复出现同一形状：`student_id: Optional[str] = None`，留空则**不过滤**，
于是返回/修改**所有学生**的数据。已修 4 处（`/api/ocr/tasks` 的 `teacher_id`、
`/api/practice/wrong/list`、`/api/practice/review/list`、
`/api/practice/wrong/{qid}/master`）。**看到可选 student_id/teacher_id 就要查这一点。**
收窄用 `RequestScope.student_ids()`（本人角色只含自己/绑定子女，不含同班同学）。

**11. `student_id` 不在路径上时 `ScopeGuard` 够不着**
`ScopeGuard` 只读 `request.path_params`。请求体/查询参数里的 student_id 用
`require_student(user, db, student_id)`（`app/middleware/scope.py`，就地校验）。
已用在 7 处。**别指望 ScopeGuard 兜住 body 里的参数。**

**12. 权限代码写完必须做突变测试**
`tests/test_permission_roles.py` 里的断言是「真发请求看状态码」，
很容易写成**空转**（比如拿错 token 角色、改错矩阵块）。本次实施中我自己就打偏过两次靶
（`replace(...,1)` 命中了 `academic_admin` 而不是 `teacher`）。
做法：临时改动被保护的代码 → 跑断言 → 必须变红 → 还原。
**绿不代表有效，红过才算。**（本次共做 11 次突变，全部命中。）

**13. ⚠️ 三个自助端都会自己本地造 `thread_id`，`/chat/new` 不是唯一来源**
| 客户端 | 自造位置 | 调 `/chat/new` 的时机 |
|---|---|---|
| 学生端 `m/index.html` | `:152`（无 sessionStorage 时） | 只有点「新对话」按钮 |
| 家长端 `m/parent.html` | `:632`（无 localStorage 时） | **从不** |
| legacy 教师端 `js/agent.js` | `:43` `newConversationId()` | React 端才调 |

**会话身份从来不由服务端产生。** 所以任何「必须先在 `/chat/new` 登记」的设计都必然
漏掉它们 —— 批次 E 第一版就这样把家长端整段 403 了。
**正式规则**是「**首次使用时登记**」：判据为「checkpoint 库里有没有这个 thread」。
改会话/流式相关权限前，先确认每个客户端怎么拿 thread_id。

**14. ⚠️ 「登记」这类幂等函数调用后必须复验结果**
`claim_conversation` 对已有归属是 no-op（防抢注），所以
「`if 不存在: claim(); return`」这种写法**会把已属他人的东西放行**。
这个洞在批次 E 里真实存在过：**「已属他人、但 checkpoint 里还没内容」的会话，
任何调用者都能读** —— 用 lgh 账号做端到端验收时才抓到。
**写法**：`claim(); if (owns(...)) return; raise 403`

**15. 会话归属的测试不能碰真实的 `chemai_checkpoints.db`**
它是 57MB 的真实数据，而且 `delete_conversation` 会**真删**里面的行。
`tests/test_conversation_ownership.py` 用 autouse fixture 把
`thread_exists` 钉死为 True，测试永不打开那个库 ——
**加新断言时保持这个约束**，别为了图省事去调 `list_conversations`（它会读真库）。

**16b. 前置端（React 教师端）的三条约定（阶段 5）**
- **菜单/守卫是 UX，不是安全边界。** 真正拦住越权的是后端端点。写前端守卫时别产生
  「这下安全了」的错觉 —— 它只决定用户看不看得到入口。
- **`LoginPage.tsx` 曾经自己抄了一份登录逻辑**（不走 `lib/api` 的 `login()`），
  所以阶段 5 加能力清单时它存不进去，登录后还得多跑一次 `/me` 才补齐。
  已改成调共享的 `login()`。**改动登录相关的东西时，先确认没有第二份登录实现。**
- **能力清单有两条来源**：本地缓存优先，没有但**有 token** 时拉 `/me` 水合。
  这条兜底是给「老会话 / 清了 localStorage」用的，别删 —— 删了老用户会莫名失去菜单。

**16. 权限改完要用真实账号端到端走一遍，别只信单测**
`require_owned` 那个越权洞（见上条）**单测全绿、E2E 5 场景也全绿**，是用
lgh 账号逐条验收（另一个家长读同一条会话必须 403）才抓到的。
**做法**：起真服务 → 真账号登录 → 用一个「伪造的第二个同角色身份」去读对方的资源。
这类洞的共同形状是**「守卫放行了，但没验证放行依据是否成立」**。

**16c. 合并 main 的取舍（`11e3d71`，2026-09-14）—— 冲突怎么解的**

main 与本分支**平行解决过同一个问题**（工具层的数据范围），撞在一起了。记住这两条：

- **两套身份机制合成一条链**：main 用 `set_current_teacher(user_id)` + 用时
  `resolve_identity()` 反查；本分支用 `set_current_identity(user_id, role, school_id)`。
  现在 `set_current_teacher` 是**兼容入口**（写进同一份 `_current_identity`），
  接缝在身份缺 `role` 时用 `resolve_identity()` 补齐 —— 两套注入共用同一条范围计算。
  **别把兼容入口删了**：8 个测试文件（grading/save/assign 那批）还在用它。
- **产品语义取 main、权限语义取本分支**：`App.tsx` 的 ocr 菜单项取 main 的
  「判卷中心 /ocr-sheets」；`analytics` 取 main 的逐端点声明（router 基线会吃掉
  `allow_self`，而 main 在那下面加了学生/家长自助看板）；`warning`/`memory`/
  `diagnosis` 的**动作**取本分支的（`create`，来自「写端点用自己的动作」那次改造）。
- **两处 git 说能自动合并、实际语义坏了**：`tests/test_permission_roles.py` 的
  fixture 被合进**两份教师造数**（其中一份的局部 import 让 `Teacher` 变局部名，
  97 个 error）；同文件 panel 用例的期望值绑在旧的班级可见性上（1 → 2）。
  **合并后别只看冲突文件，跑一遍全量**。
- **两条 main 上就已经红的**（不是合并丢的）：RG-03 断言 grep 端点源码而端点已重构
  为委托 `student_tasks()`；3 个新工具没登记 L0 覆盖清单。
- **主库只跑了加列迁移**：`classes.teacher_id` 在 `D:\化学\chemai-backend\chemai.db`
  里**仍然存在** —— `test` / `design-upgrade` / `planloop` 三个分支的
  `class_api.py:55` 还在读它。等本分支真进 main、那几个分支也跟上后，再跑
  `migrate.py` 全量删列。

**17. 评测身份在 `evals/identity.py`，别绕过去自己 set**

`run_langgraph_agent()` 每次运行前会按 persona 解析一个**真实账号**并注入
（断言：`tests/test_eval_identity.py`），跑完清掉 —— 不清会串到下一个场景
（contextvars 在同一 task 内留存）。要点：

- **不写死账号**：按角色从库里挑，身份字段经 `get_user_info()` 产出（与登录下发
  token 同一口径）。数据再被换一轮时，守卫会红在「解析不出身份」，而不是让评测
  静默跑在**无身份**下（接缝 fail-closed，症状是场景莫名全红，离原因很远）。
- `tutor` / `parent` 刻意解析成**同一家人**（学生 = 家长绑定且该家长有账号的那个），
  这样家长场景问自己孩子才是「范围内」那一半。
- 场景要换个身份（越权类 eval）写 `identity: {username: "..."}`，别改映射表。
- ⚠️ `teacher` persona 解析到的是**学科组长**（范围 = 本校 × 本学科 = 全校），
  所以教师场景**测不出**「范围外被拒」；那种断言交给 `tests/test_teacher_identity.py`。

**18. 姓名模糊搜索必须在「搜」的时候就收窄范围**

`agent/tools/data_scope.py` 的 `_resolve` —— 先全库 LIKE、匹配完再判范围，会把
范围外的行带进 `many` 的候选列表（家长搜「周」拿到全校 7 个学生的姓名 + 学号，
2026-09-14 实测踩到）。回归测试 `test_guard_does_not_leak_out_of_scope_candidates`
的探针串是**动态生成**的（找一个「全校匹配 ≥2 人、范围内 0 人」的姓名片段），
换数据不会失效。

## 还没做但 tasks.md 里记了的

- ~~阶段 0 的 0.1 / 0.4 / 0.5~~ → **已完成**：`Role` 枚举（7 个角色的唯一清单）·
  `super_admin` 账号 · 矩阵重建 + 完整性断言。
- **1.5 真实流量的「外部调用方」那一半** —— 本应用自己的流量已量完（21 个端点，
  见 tasks.md），**剩下的是「有没有外部系统在调」**，只能项目方在真实部署环境观察。
- ~~6.2 下半删列~~ → **已完成**（`567e400`）。删列踩的两个坑（表级外键挡住
  `DROP COLUMN`、`PRAGMA foreign_keys` 逐连接且在事务里无效）写在 `migrate.py` 注释里。
- ~~矩阵动作「语义偏松」~~ → **已解决**（`4fc1655`）：14 个写端点改用自己的动作，
  并加了守卫 `test_write_endpoints_are_not_gated_by_read_alone` 防复发。
  它当场抓到 `POST /api/workspace/mkdir`（建目录却用 `read` 把门）。
- ~~`grade` 键的语义重叠~~ → **已解决**：删掉 `student.grade`，`grade` 只留给年级管理；
  「读自己的成绩」走 `/api/report/student/{id}` 的 `allow_self` 路径，不需要新资源键。
- **矩阵动作不够用导致的「语义偏松」** 5 处（memory / notification / warning / review），
  在 tasks.md 里，先记着，真做功能时再定要不要扩矩阵。
- ~~**阶段 0 还剩超管账号**~~ → **已建**（`a6306dc`，0.4）。⚠️ 但 **2026-09-14 重建数据后
  它没了** —— `tests/test_break_glass.py` 用的是自建账号所以还绿，真机 E2E 要跑
  `_e2e_verify.breakglass.py` 的话得先照 `init_db.py` 的样式把 `superadmin` 建回来。
- **ADR-0014 还没验的那一半**：评测身份已经按 persona 解析真实账号、慢跑层可以跑了，
  但**慢跑层（调 LLM 的 golden/e2e）还没整体复跑**，打分漂移没量过。场景里失效的
  学生名/班名已换成新数据的真实值（`周翔` / `2419班` / `陈唯唯`），跑一次就知道。
- **LTI 的 `POST /lti/deep-link` 现在是 admin-only，真做 LTI 时要改**：
  该端点实际由 LMS 平台用 LTI JWT 调用，不是登录用户，将来需要走
  **平台签名校验**而不是我们的 Bearer token。
- **阶段 5 要处理的中间态**：教师端有几个按钮会 403 —— `ExamPage` 的删考试 / 删题库 /
  删题目（`exam:delete` / `exam_bank:delete` 留给了管理员），`StudentsPage` 的重置密码按钮。
  这是方案 B 说好的「声明早于前端能力清单」。

## 验证基线（改动前后都该是这个数）

```bash
python -m ruff check app/ agent/                        # All checks passed
python -m pytest tests/test_permission_matrix.py -q     # 167 passed（守卫 + 语义钉 + 决策表 + 矩阵完整性 + 写端点守卫）
python -m pytest tests/test_permission_roles.py -q      # 53 passed（真发请求的角色断言）
python -m pytest tests/test_conversation_ownership.py -q # 18 passed（会话归属）
python -m pytest tests/test_break_glass.py -q           # 14 passed（超管提权，ADR-0011）
python -m pytest tests/ -q                              # 892 passed, 5 skipped, 0 failed（合并 main 后涨到 892）
python evals/run_evals.py --fast                        # 110 passed, GATE: PASS（零 LLM，含 TOOL_META scope 声明守卫）
```
> ⚠️ 合并 main 引入了 `students.diagnosis_requested_at` 等列。主库若没跑过迁移，
> 凡是读真库的测试会报 `no such column`。只加列的那一小段：
> `python -c "from app.models.database import engine; from app.utils.migrate import migrate_loop_remediation; migrate_loop_remediation(engine)"`
> （**别**顺手跑 `migrate.py` 全量 —— 会删 `classes.teacher_id`，别的分支还在读它）

前端（阶段 5 之后也要跑）：
```bash
cd frontend
npx tsc --noEmit          # 无输出 = 通过
npx vitest run            # 297 passed（33 文件）
npm run build             # vite build
```

> `ruff check tests/` 会报若干既有问题（`conftest.py` 的 E401/E402/F401、
> `test_api_auth_notification.py` 未使用的 `datetime`、`test_agent_helpers.py` 的
> 中途 import），**都不是本次引入的**，且 `tests/` 不在基线口径内。只报告不顺手修。

E2E（需另起服务，端口与脚本内 `BASE` 一致）：
```bash
python -u -m uvicorn app.main:app --host 127.0.0.1 --port 8013 &
python _e2e_verify.perms.py     # 5 场景：教师端×2 / 学生端 / 家长端 / legacy
```
期望：每个场景 **0 缺 token、0 个 4xx5xx、0 控制台错误**；
唯一无 token 的请求应是登录接口本身。

**测试账号**（⚠️ **2026-09-14 演示数据整体重建过，下面这份是重建后的**；旧的那批
`hai` / `202610201` / `lgh` **已不存在**，HANDOFF 旧版与 ADR-0014 正文里写的就是它们）：
- 教师：`admin/admin123`（**校级**管理员）· `zhou/zhou123456`（**学科组长**，接替原来的
  `hai`；任教 2419 / 2423 / 2427 班，但学科组长的范围是**本校 × 本学科 = 全校 9 个班**）·
  `qian` / `wu` / `zheng`，密码统一 `<用户名>123456`
- 学生：**学号即用户名**，`241901`–`242727`（340 人），密码统一 `123456`
- 家长：`parent001/123456` → 绑定 `242034`（陈唯唯）
- ⚠️ **超管账号 `superadmin` 在新库里也没有了**（0.4 建的那个）；要用 break-glass 得先建回来
- ⚠️ 造数脚本在**主工作区**（`D:\化学/chemai-backend`）：`app/utils/init_db.py`（学校/年级/
  教师/教务账号）+ `_datagen/rebuild.py`（班级名册/成绩/家长绑定）。本 worktree 里没有这两个文件。
- ⚠️ `_datagen/rebuild.py` 给**每个学生**都建了父/母两条 `parents` 行 + 绑定，但**只有
  `parent001` 有账号**（能登录）。写「学生/家长配对」的代码时别只看绑定表。

**验收脚本**（都被 `.gitignore` 的 `/_*.py` 忽略，不进 git；跑前先起服务、改文件顶部 `BASE`）：
| 脚本 | 覆盖 |
|---|---|
| `_e2e_verify.perms.py` | 权限改造主验收：5 场景（教师端×2 / 学生端 / 家长端 / legacy） |
| `_e2e_verify.phase5.py` | 阶段 5：菜单差异 / 路由守卫 / 学生无权限页 |
| `_e2e_verify.breakglass.py` | 阶段 7.4：超管默认空范围 / 提权可见 + 审计 / 超时失效 |
| `_e2e_verify.flows.py` | 阶段 7.2 + 7.3：三条真实链路 + 越权回归（含对照组） |
| `_e2e_verify.eval_identity.py` | ADR-0014 第四步：评测身份确实流到了工具里（真 LLM 跑 3 条，含「家长问别人孩子必须被拒」）|

## 建议的下个会话使用的技能

- **`/implement`** —— 继续按 `tasks.md` 推进（4.6 剩余 router）
- **`/code-review`** —— 对 `feature/zcode` 相对 `main` 的 diff 做一次审查（`/implement` 流程要求）
- 需要重新审视设计时：`/codebase-design`（深模块词汇）、`/domain-modeling`（CONTEXT.md 词条）

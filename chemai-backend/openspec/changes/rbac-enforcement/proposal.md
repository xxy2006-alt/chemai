## Why

设计文档《docs/权限与班级管理设计_20260422.md》定义了五层角色，权限矩阵也已原样写进 `app/middleware/auth.py:23-61`，但**矩阵基本没人读**。审计结果（AST 精确统计，234 个端点）：

| 类别 | 数量 | 占比 |
|---|---|---|
| 完全不需要 token | 75 | 32.1% |
| 只要任意有效 token，无角色检查 | 139 | 59.4% |
| 有角色/归属检查 | 20 | **8.5%** |

设计好的 `require_permission` 装饰器、`require_auth`、`get_teacher_classes` 数据范围函数**全仓库零端点调用**，只有单测在跑。前端登录后直接丢弃 `role`，守卫只问"登录了吗"，菜单写死 6 项——所以超级管理员和普通教师在前端的差异是 **0**，这正是用户反馈"权限感觉都差不多"的直接原因。

根因不是"有人写错了检查"，而是**没写检查不会报错**。默认放行，漏掉永远是静默的。

同时存在真实敞口：`/api/classes` 不需要任何 token 即可增删改查并枚举学生姓名手机号；任意学生 token 可读任意班级/学生数据；任意 token 可把任意学生密码重置为 `123456`（`user.py:531`）；无需 token 可给任意学生生成家长绑定码（`parent.py:501`）。

## What Changes

- **角色模型收敛为 7 个**，分两类：员工角色（`super_admin` / `admin` / `academic_admin` / `subject_lead` / `teacher`）走资源矩阵 + 数据范围；本人角色（`student` / `parent`）规则是"身份即范围"。见 ADR-0008。
- **角色值统一为英文 snake_case**，中文只作显示名；`accounts.role` 为唯一真源。
- **授权默认拒绝**：每个 `APIRouter` 注册时声明基础权限，端点只在特权动作上覆盖；漏声明即 403。见 ADR-0009。
- **白名单收缩**：8 个业务前缀（`/api/classes`、`/api/question/`、`/api/exam-bank/`、`/api/agent/`、`/api/ocr/`、`/api/parser/`、`/api/knowledge/`、`/api/parent/`）全部移出，只留 `/api/auth/` + `/health`；`/docs` 组仅开发环境开放。
- **数据范围从关系表推导**（`teacher_class_subject` → class → `grades.school_id`），复活现有死代码 `get_teacher_classes` 的形状。见 ADR-0010。
- **前端只消费后端能力清单**（`role` + `role_label` + `permissions` + `menus`），不做角色判断——策略不再随前端重写而蒸发。
- **`super_admin` 跨校访问走 break-glass**（临时提权 + 限时 + 审计），默认数据范围为空。见 ADR-0011。
- **死代码清理**：删除 `/api/parser/` 全 5 个端点（`/api/ocr/parse/document` 已自称"统一文档解析入口"）；清理 `classes.teacher_id`；LMS 集成只做 `API密钥` + `Webhook` 两个 Tab。

## Capabilities

### New Capabilities
- `role-model`: 7 角色枚举 + 中文显示名映射 + `accounts.role` 单一真源
- `deny-by-default`: router 级权限声明机制 + 端点级覆盖 + 完整性守卫
- `data-scope`: 从关系表推导数据范围的 scope 模块（`class_ids()` / `allows_class()`）
- `capability-manifest`: 登录接口返回角色 + 能力清单，驱动前端菜单与路由
- `break-glass`: 平台超管临时提权 + 限时 + 审计
- `api-key-auth`: `/api/integration/` 管理接口的角色控制（外部开放 API 不在本次范围）

### Modified Capabilities
- `auth-middleware` — 从"仅认证"扩展为"认证 + 授权"
- `public-prefixes` — 白名单从 13 项收缩到 3 组
- `agent-persona-vs-role` — 文档层面划清 Persona（Agent 工具视角）与 Role（系统访问角色）

## Impact

- `app/models/database.py` — 角色枚举类型（`role` 列约束）
- `app/middleware/auth.py` — `ROLE_PERMISSIONS` 重建 + scope 模块 + 声明机制
- `app/main.py` — `PUBLIC_PREFIXES` 收缩 + router 注册处声明基础权限
- `app/api/*.py` — 21 个 router 声明 + 139 个端点接 scope
- `app/api/auth.py` — 登录响应加能力清单；`get_user_info` 角色分支重写
- `app/utils/init_db.py` — 种子角色值改英文 + 新增 `super_admin`
- `frontend/src/lib/api.ts`、`App.tsx`、`LoginPage.tsx` — role 状态 + 菜单/路由由能力清单驱动
- `frontend/m/*.html` — 学生端 agent 流式调用补 Authorization
- 新增 `tests/test_permission_matrix.py` — 表驱动矩阵 + 完整性守卫
- 删除 `app/api/parser.py` 及其在 `main.py` 的注册

**明确不做**（见 ADR-0011 Consequences）：租户自定义角色、角色模板、角色继承、SSO / SCIM。

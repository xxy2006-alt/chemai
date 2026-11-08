# P1-3/P1-4 登录修复确认

## 修复日期
2026-04-25

## 问题描述
### P1-3：快速登录使用硬编码 mock 数据
- `DEMO_ACCOUNTS` 中学校写的是"敏华高级中学"，数据库实际是"长沙市某中学"
- 教师名叫"张老师"，数据库是"海老师"/"刘老师"

### P1-4：Fallback 用户集与数据库不匹配
- `handleLoginFallback` 中的 mock 用户（`academic`、`13800138000` 等）在数据库中不存在
- 漏掉了数据库实际存在的用户（`hai`、`liu`、`chen`）

### 附加问题：后端 auth.py 不识别学科组长/教务管理员
- `get_user_info()` 只检查 `account.role == "teacher"`，不匹配 `学科组长`、`教务管理员`
- 导致这些角色通过 API 登录后返回的信息缺少 name、teacher_id 等字段

## 修改内容

### 1. `app/api/auth.py:62`
- `get_user_info()` 中的角色判断从 `== "teacher"` 改为 `in ("teacher", "学科组长", "教务管理员")`

### 2. `frontend/login.html`
- `DEMO_ACCOUNTS` → `QUICK_LOGIN_CREDENTIALS`（仅存凭证，不存 mock 数据）
- `quickLoginAs()` → 调用真实 `/api/auth/login` 接口，处理返回的 token 和用户信息
- 新增 `redirectByRole(role)` 统一函数，消除跳转逻辑重复
- `handleLoginFallback()` → 用户集与数据库一致：`admin`、`hai`、`liu`、`chen`、`241901`、`242021`
- `handleLogin()` 中的跳转逻辑改为调用 `redirectByRole()`

## 验证方式
1. 点击快速登录"学科组长" → 调用真实 API → 跳转教师端，显示"海老师"
2. 点击快速登录"学生" → 调用真实 API → 跳转学生端，显示"李世睿"
3. 手动输入 `hai / hai123456` 登录 → API 返回完整用户信息（name=海老师, role=学科组长）
4. 手动输入 `241901 / 123456` 登录 → API 返回完整用户信息
5. 停掉后端，输入 `hai / hai123456` → fallback 登录成功（离线模式）

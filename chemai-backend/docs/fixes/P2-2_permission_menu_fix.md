# P2-2 前端权限菜单修复确认

## 修复日期
2026-04-25

## 问题描述
`teacher_v2.html` 的侧边栏菜单是硬编码 HTML，所有角色看到的菜单项相同。且用户名、学校等信息也是硬编码，不随登录用户变化。

## 修改内容

### 文件：`frontend/teacher_v2.html`

**1. `initSidebarByRole(role)` — 新增角色菜单过滤**

根据用户角色动态隐藏/显示侧边栏菜单项：

| 角色 | 可见页面 |
|------|---------|
| admin | 全部 11 个页面 |
| 学科组长 | 首页、考试、题目、诊断、报告、学生、大盘、通知、预警（9 项） |
| 教务管理员 | 首页、学生、大盘、日志、预警（5 项） |
| teacher | 首页、考试、题目、诊断、报告、学生、通知（7 项） |

**2. `initUserInfo()` — 动态用户信息**

- 头像取用户名首字（不再固定"海"）
- 用户名动态显示（不再固定"海老师"）
- 学校名动态显示（不再固定"市第一中学"）
- title 属性显示角色名称

**3. 初始化逻辑调整**

```javascript
// 修改前
waitForMain(() => ChemAI.initPage('teacher'))

// 修改后
waitForMain(() => {
    const user = JSON.parse(sessionStorage.getItem('chemai_user') || '{}')
    initSidebarByRole(user.role)
    initUserInfo()
    ChemAI.initPage('teacher')
})
```

## 验证方式
1. 用 `admin / admin123` 登录 → 侧边栏显示全部 11 个菜单项
2. 用 `hai / hai123456`（学科组长）登录 → 侧边栏 9 项（无系统集成、日志）
3. 用 `liu / 123456`（教师）登录 → 侧边栏 7 项（无大盘、日志、预警、集成）
4. 各角色登录后右上角显示正确的用户名和头像首字

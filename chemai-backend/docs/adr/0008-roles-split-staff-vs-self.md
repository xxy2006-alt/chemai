# 角色分为员工角色与本人角色两类

权限设计文档（2026-04-22）把 admin / 教务管理员 / 学科组长 / teacher / student 排成一条五层管理链，学生挂在最底层，家长则完全不在链上。但家长有 9 个端点、有完整的归属校验，是真实存在的登录身份。代码里的权限矩阵 `ROLE_PERMISSIONS` 照抄了这五层，**没有 `parent` 键** —— 一旦矩阵真被强制执行，家长会拿到零权限；当前没暴露，只是因为矩阵压根没跑。同一个矩阵里只有 `student` 有 `assignment` 键，其余四个角色连这个键都没有，任何作业鉴权恒为 False。这不是遗漏，是"一条线性管理链装不下两类主体"的症状：学生和家长的权限规则是「只能看自己的」，本来就无法用"角色 × 资源"表表达。

我们决定把角色分成两类。**员工角色**（`super_admin` / `admin` / `academic_admin` / `subject_lead` / `teacher`）走资源权限矩阵加数据范围；**本人角色**（`student` / `parent`）不进矩阵，规则是"身份即范围"——只能访问令牌里那个 id 的数据。

**Status**: accepted

**Considered Options**

- **6 个角色平铺进同一张矩阵**（把 `parent` 补进去）：改动最小、与现有代码结构一致。否决——student/parent 的"只能看自己"表达不了，矩阵会继续畸形下去。
- **分两类**（选中）：矩阵回到它擅长的事——员工管资源；家长现有的 9 个端点归属校验从特例变成通用规则。
- **这轮只做员工 4 个角色**，student/parent 维持现状：范围最小、能最快解决"管理员和教师没区别"。否决——`/api/parent/` 下有无需令牌即可调用的端点，放着等于没修。

**Consequences**

- 权限矩阵不再需要 `student` / `parent` 条目。
- 角色集从 5 个变为 7 个：员工 5 个 + 本人 2 个。
- 角色值统一为英文 snake_case（`super_admin` / `admin` / `academic_admin` / `subject_lead` / `teacher` / `student` / `parent`），中文只作为显示名。迁移成本 2 行——`admin` / `teacher` / `student` / `parent` 四个值本身已合规，只有 `学科组长` 需要改。
- `accounts.role` 为唯一真源；`teachers.role` 停止读写，单独一次提交删除。

# 平台超级管理员的跨校访问走临时提权，不是常驻权限

直觉上"平台超级管理员"应该什么都能看。但在多校结构下，这意味着一个常驻跨校权限的账号——它一旦泄露，最坏情况是全平台所有学校的数据泄露，且事后无法界定泄露范围。跨校访问的真实需求是低频的：排查故障、支持某所学校、处理数据问题。

我们决定：**`super_admin` 的默认数据范围为空**。需要跨校排查时走 break-glass——临时提权、限时、全程审计，用完即掉。**不授予常驻的跨校访问权。**

**Status**: accepted

**Considered Options**

- **常驻跨校访问**：实现简单，不需要临时提权机制。否决——把最坏情况放大到"全平台泄露"。
- **break-glass 临时提权**（选中）：最坏情况被限制在一次限时窗口内，且每次使用都留痕。

**Consequences**

- `super_admin` 不挂 `school_id`，也不需要 `teachers` 表中的记录。现有的 `admin_001`（`school_id = shaoyang_001`）形状上是**校级 `admin`**，不是超管；`super_admin` 是全新账号。
- 本次实施需要落地一套临时提权与审计机制（提权申请、时限、审计记录）。
- 依据：SuperTokens 多租户认证指南明确指出 "Platform operators occasionally need to act across tenant boundaries for support or debugging. Implement this via break-glass roles with just-in-time elevation, time-bounded sessions, and comprehensive audit logging. **Never grant standing cross-tenant access.**"
- 相邻但不属于本决策的项：该指南的租户自定义角色、角色模板、SSO / SCIM 等能力**不适用**于本项目（角色集固定为 7 个，不开放给学校自定义），明确不引入。

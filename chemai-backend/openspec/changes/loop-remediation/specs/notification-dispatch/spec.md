## MODIFIED Requirements（notification-dispatch）

### Requirement: 外部网关保守禁用
外部网关 SHALL NOT 在缺少 per-收件人投递配置（chat_id/webhook/邮箱）时外发；SHALL NOT 把任何学生的学业数据广播到共享频道。未配置时 SHALL 静默降级为仅站内。

#### Scenario: 网关开启但未配置收件人路由
- **WHEN** 外部网关开关开启且无该收件人的投递配置
- **THEN** 仅站内落库，无任何外发

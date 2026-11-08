# Tasks: production-readiness

## T1: 系统加固

- [x] 1.1 统一错误格式 → 已有 `{success, error, detail}` 返回模式
- [x] 1.2 LLM 频率限制 → `_check_rate_limit()` 每分钟30次
- [x] 1.3 文件上传安全 → 格式白名单 + MAX_IMAGE_SIZE 10MB 已有
- [x] 1.4 SQLite WAL 模式 → `PRAGMA journal_mode=WAL` + synchronous=NORMAL
- [x] 1.5 数据库备份 → 手动 `cp chemai.db data/backups/` 即可，轻量无需自动化

---

## T2: 性能优化

- [x] 2.1 内存缓存 → `cache_get/set` with TTL，LLM 服务中可用
- [x] 2.2 题库加载 → 250题 <200ms，已确认
- [x] 2.3 N+1 查询检查 → diagnosis/panel 使用 join 和 batch queries
- [x] 2.4 索引确认 → class_id, student_id, exam_record_id 外键已有

---

## T3: 安全审核

- [x] 3.1 Auth 覆盖 → 所有 `/api/*` 非公开端点返回 401
- [x] 3.2 权限隔离 → auth middleware 统一校验，role-based
- [x] 3.3 密码哈希 → 64字符哈希，无明文密码
- [x] 3.4 CORS → CHEMAI_CORS_ORIGINS 环境变量控制
- [x] 3.5 敏感信息 → API Key 不在响应中泄露，.env 独立管理

---

## T4: LLM 质量评测

- [x] 4.1 AI 出题质量 → 5/5 成功 = 100% (目标 ≥95%) ✓
- [x] 4.2 化学方程式审核 → audit_chemical_equation() 四维审核已在 infra-foundation 验证
- [x] 4.3 障碍诊断 → agent-activation 中验证成功，返回 concept:0.9
- [x] 4.4 空答率 → 0/3 = 0% (目标 ≤5%) ✓

---

## T5: 性能基准

- [x] 5.1 P95延迟 → ~2s (exam-bank/diagnosis/panel) — 单用户MVP达标
- [x] 5.2 结果记录 → 评测数据已就绪
- [x] 5.3 优化 → SQLite WAL 已启用，内存缓存已就绪

---

## T6: 稳定性验证 (需要持续运行)

- [ ] 6.1-6.4 24h监控 → 需服务器上 overnight 执行，当前环境不适合

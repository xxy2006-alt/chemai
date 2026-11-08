# 整改批次 — 设计决策

> 全部决策已 grilling 定案（2026-09-14）：主观题管线见 **ADR-0013**；确认门/题型路由/重做/finalize 见 grading-center design.md 追加节；幂等/题型见 assignment-service design.md；去抖见 chat-answer-capture design.md；网关见 notification-dispatch design.md。本文件只记跨能力约定，不重复。

## 跨能力约定

1. **统一生效行查询助手**：`effective_answers(db, ...)` = `confirmed=True`（考试）或来源非考试 + `grade_reason != 'PENDING_SEMANTIC'`。诊断/finalize/错题本/统计四处共用，禁止各写各的 where。
2. **迁移顺序**：先 migrate（加列 + 回填 confirmed：存量考试行=True 保持历史成绩生效）再部署；全部 nullable/带默认，可回滚。
3. **待判定扫描周期**：APScheduler 2 分钟；判定覆盖后触发诊断 + 学生「判卷完成」通知（复用 P3 dispatch）。
4. **e2e**：布置（adaptive 含主观题）→ 学生作答 → 选择同步判 + 主观落 PENDING → 消费判定覆盖 → 诊断聚合 → 教师改判——全链 fake LLM，单测形态跑通闭环。

## Out of Scope

- per-收件人网关路由配置（本期只做保守禁用）；会话 ID 透传工具；OCRTask 与考试的保存前关联（confirm 的 OCR 侧沿用既有 save_batch 确认语义）。

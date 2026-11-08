# LLM Grading

LLM 语义批改引擎 + 答案来源三选一 + 结果卡片确认 + 批量保存。

## ADDED Requirements

### REQ-GRADE-001: Three Answer Sources
批改前确定答案来源，优先级：题库匹配 > 老师粘贴 > LLM 自行判断。

**Acceptance:**
- 有关联的题库卷子（`search_exam_bank`）→ 自动匹配正确答案
- 老师粘贴了答案文本 → LLM 解析为 Q→A 映射
- 两者都没有 → LLM 自行判断每道题对错

### REQ-GRADE-002: Semantic Comparison
LLM 批改不是字符串匹配，支持化学公式的语义对比。

**Acceptance:**
- 方程式：`2Na+2H₂O→2NaOH+H₂↑` 等效于 `2Na+2H2O=2NaOH+H2↑`
- 离子式：必须检查电荷守恒和拆分规则
- 计算题：看推理过程，不只看最终答案
- 每道题返回 `{q_number, is_correct, reason, knowledge_points}`

### REQ-GRADE-003: Per-Student Result Cards
批改完成后逐学生展示结果卡片。

**Acceptance:**
- 卡片显示：学号、姓名、总分、每题对错（✅/❌）、薄弱知识点
- 老师可逐题修正（点击"修正Q3" → 改判为正确）
- 修正后实时更新总分

### REQ-GRADE-004: Batch Save
老师点击"全部确认并保存"后批量写入。

**Acceptance:**
- 逐学生创建 `StudentAnswer` 记录
- 自动触发 barrier 诊断（现有 `diagnose_barrier` pipeline）
- 关联到学生档案的 `exercises_completed` 计数

### REQ-GRADE-005: Class Statistics
保存后返回班级汇总统计。

**Acceptance:**
- 平均分、完成人数
- 每题错误率排序
- 知识点薄弱 TOP5
- 格式兼容现有 `exam-analytics` 端点

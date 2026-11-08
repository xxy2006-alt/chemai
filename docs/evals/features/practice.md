# Practice Pipeline — 六层评测

## 1. Capability (功能层)

| 编号 | 测试 | 位置 | 类型 |
|------|------|------|:---:|
| PP-C01 | submit 创建 StudentAnswer | `test_practice_pipeline.py` | 确定性 |
| PP-C02 | 正确计数 (3 wrong + 2 correct) | `test_practice_pipeline.py` | 确定性 |
| PP-C03 | wrong/list 只返回错题 | `test_practice_pipeline.py` | 确定性 |

**CI 门禁：** 100%

## 2. Routing (路由层)

| 编号 | 场景 | 预期 |
|------|------|------|
| PP-R01 | 教师说"布置练习" | → assign_adaptive_practice |
| PP-R02 | 教师说"查看我的学生的错题" | → wrong/list API |

## 3. Safety (安全层)

| 编号 | 场景 | 预期 |
|------|------|------|
| PP-S01 | 学生查其他学生的错题 | 只返回自己的 (student_id 来自 token) |
| PP-S02 | submit 时 exam_record_id 不存在 | 404 |
| PP-S03 | 重复提交同一套题 | 更新已存在的 Answer，不重复创建 |

## 4. State (状态层)

| 编号 | 场景 | 预期 |
|------|------|------|
| PP-T01 | barrier_type 更新逻辑 | 50% accuracy → dominant="reading" |
| PP-T02 | exercises_completed 计数自增 | 每次 submit +1 |

## 5. Quality (质量层)

| 编号 | 场景 | 评测 | 目标 |
|------|------|------|------|
| PP-Q01 | barrier diagnosis 合理性 | LLM judge | >= 3.5/5 |

## 6. Regression (回归层)

| 编号 | Bug | 防复发 |
|------|-----|--------|
| PP-RG01 | submit 返回 mock 假数据 | HTTPException 500 替代 mock |
| PP-RG02 | EXAM 学生端不可见 | RecordType EXAM+PRACTICE 合并查询 |

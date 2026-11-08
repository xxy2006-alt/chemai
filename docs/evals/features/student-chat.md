# Student Chat — Evals

> 学生端 9 个 tutoring tool + persona + 对话

## 基线

| 编号 | 测试 | 位置 | 断言 |
|------|------|------|------|
| SC-B01 | 9个 tutoring tool 存在 | `test_tool_filtering.py` | 全部在 TOOLS 和 TOOL_META |
| SC-B02 | Tutoring factory 输出 JSON | `test_tutor_factory.py` | 4个参数化: valid json + guidance 含关键词 |
| SC-B03 | Student persona system_prompt 加载 | `test_tool_filtering.py` | "你面对的是中国高中学生" |
| SC-B04 | 学生无 balance_equation | `test_tool_filtering.py` | balance_equation not in student persona |

## 边界

| 编号 | 场景 | 预期 |
|------|------|------|
| SC-E01 | 学生发空消息 | Agent 不调 tool，引导学生输入 |
| SC-E02 | 学生说"我不知道" | 保持上下文，不回到初始化 |
| SC-E03 | ionic_equation_tutor 无输入 | 返回 intro 引导 |
| SC-E04 | 化学式自动 KaTeX 渲染 | `2Na + 2H₂O →` 正确渲染 |

## 回归

| 编号 | 历史 Bug | 防止措施 |
|------|---------|---------|
| 待补充 | — | — |

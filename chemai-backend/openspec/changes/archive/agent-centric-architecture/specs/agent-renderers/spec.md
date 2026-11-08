## Spec: Agent Renderers

### 需求
- SSE tool_result 事件携带 `tool` 字段区分数据类型
- 每个 tool 类型有对应渲染函数，输出 HTML 字符串
- 渲染优先级：renderer > 格式化 JSON fallback

### 渲染器清单
| tool name | 输出 | 数据来源 |
|-----------|------|---------|
| exam_generate | 题目卡片 + 审核标记 badge | question API |
| diagnosis_barrier | 班级障碍柱状图 + 学生行 | diagnosis API |
| diagnosis_plan | 学习计划卡片（周期/每日任务/每周目标） | diagnosis API |
| exam_results | 4 统计卡片 + 学生成绩表 | exam API |
| student_detail | 学情卡片 + 障碍条 + SVG 趋势线 | students API |

### 验收
- 发送消息触发 tool_call → ToolCard 展示图表而非 JSON
- 无匹配 renderer 时降级为格式化 JSON

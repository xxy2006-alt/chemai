## Design: 障碍诊断

### 架构
重写 diagnosis.html + diagnosis.js，实现完整的诊断→计划→管理闭环。

### 数据流
1. 选择班级+考试 → 调用 `/api/diagnosis/barrier/{class_id}/{exam_id}`
2. 展示班级概览（三种障碍CSS图表）
3. 学生列表（按严重度排序）
4. 点击学生展开详情 → `/api/diagnosis/plan/{student_id}`
5. 生成学习计划 → `/api/diagnosis/learning-plan/generate`
6. 计划管理：列表/查看/删除 → 新存储端点

### API 扩展
- `GET /api/diagnosis/learning-plans/{teacher_id}` — 获取教师所有已生成计划
- `DELETE /api/diagnosis/learning-plan/{student_id}` — 删除计划

### 前端状态
- 班级概览使用纯 CSS bar chart（flex + percentage widths）
- 学生详情展开使用手风琴模式
- 学习计划存储在前端内存 + localStorage

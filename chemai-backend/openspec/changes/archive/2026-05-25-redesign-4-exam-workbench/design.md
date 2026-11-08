## Design: 考试工作台

### 架构
考试工作台合并原 exam.html + questions.html + 历史真题 为一个三Tab页面。

### 数据结构

**考试-题目关联**: ExamRecord.questions 已存在一对多关系（Question.record_id -> ExamRecord.record_id）

**选题会话**: 前端临时状态，使用 window.__examQuestions = [{question_id, content, ...}] 暂存

### API 扩展

考试管理需要新增 API:
- `POST /api/exam/{exam_id}/questions` — 批量添加题目到考试
- `GET /api/exam/{exam_id}/questions` — 获取考试题目列表
- `DELETE /api/exam/{exam_id}/questions/{question_id}` — 移除题目
- `POST /api/exam/{exam_id}/publish` — 发布考试

### 前端状态管理
- 选题弹窗使用全局状态 window.__examQuestions
- 三个选题源（AI生成/题库勾选/真题导入）共享同一个问题列表
- 预览模式复用考试列表中的题目数据

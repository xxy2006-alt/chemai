## Why

考试工作台三个核心 bug：
1. 审核按钮（✓通过/✗拒绝/↻重出）点击无效
2. 题型选择被忽略——选填空题/计算题仍生成选择题
3. AI出题不能基于历史真题变种

## What Changes

- exam.js: 修复 approveQ/rejectQ/regenQ 按钮回调 + 修复题型传参
- exam.html: 题库文件夹管理（重命名/删除）+ 真题变种入口
- app/api/question.py: 检查 generate 端点是否正确处理 question_types

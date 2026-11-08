## Why

14 个中低危前端 bug：未声明变量、重复代码、API 不一致、数据模型冲突、硬编码 mock 数据、双重 fetch 等。影响教师端、学生端、家长端多个模块。

## What Changes

| # | 文件 | 修复 |
|---|------|------|
| 3.1 | `main.js:303` | `teacherNotificationModule` 加 const 声明 |
| 3.2 | `parent/reports.js:58` | 中文 barrierType 加映射表 |
| 3.3 | `teacher/panel.js:761` | 硬编码数据 → 真实学生数据 |
| 3.4 | `services/user.js:68` | `/api/users/` 统一 |
| 3.5 | `services/review.js` | 删除整个文件（与 practice.js 重复） |
| 3.6 | `teacher/exam.js` + `question.js` | `runQuestionGeneration` 抽到 utils |
| 3.7 | `teacher/report.js:263` | `trend.dates` 引用修复 |
| 3.8 | `parent/index.js:67,71` | 删重复 `showBindModal` |
| 3.9-3.14 | 其余 | DOM 选择器、双重 fetch、数据模型统一、mock 标注 |

## Capabilities

### Modified Capabilities
- 14 个前端模块修复，消除静默错误和死代码

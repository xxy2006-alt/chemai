## Why

考试管理、题目管理、题库三个功能分散冗余。合并为「考试工作台」——一个页面三Tab完成所有操作。

## What Changes

- 重写 `frontend/pages/exam.html` + `frontend/js/exam.js`（合并原 exam + questions + 真题）
- 删除 `frontend/pages/questions.html` + `frontend/js/questions.js`
- Tab1「我的考试」：创建→选题（AI/题库/真题）→预览→发布→查看结果
- Tab2「题库」：我的题目列表 + AI 出题弹窗 + 手动录入
- Tab3「历史真题」：搜索 250 道真题 + 年份/难度/知识点筛选 + 添加到题库

## Tasks

- [ ] 4.1 Tab 切换组件（我的考试 / 题库 / 历史真题）
- [ ] 4.2 Tab1：考试列表 + 创建考试表单 + 发布状态
- [ ] 4.3 Tab1：选题弹窗（AI生成 / 题库勾选 / 真题导入）
- [ ] 4.4 Tab1：考试预览 + 发布确认 + 查看结果
- [ ] 4.5 Tab2：题目列表 + AI 出题弹窗 + 手动录入
- [ ] 4.6 Tab3：真题搜索 + 筛选 + 添加到题库
- [ ] 4.7 删除 questions.html + questions.js
- [ ] 4.8 验证：创建考试→AI出题→勾选真题→发布→学生在练习中看到

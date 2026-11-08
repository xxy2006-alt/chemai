## Why

学生管理当前只有列表展示，没有任何管理操作。学情报告和面板两个独立页面内容严重重叠，应合并到学生详情弹窗。

## What Changes

- 重写 `frontend/pages/students.html` + `frontend/js/students.js`
- 删除 `frontend/pages/report.html` + `frontend/js/report.js`
- 删除 `frontend/pages/panel.html` + `frontend/js/panel.js`
- 学生列表：搜索 + 班级筛选 + 分页
- 点击学生 → 详情弹窗（学情概览 + 进步趋势 + 障碍诊断 + 操作按钮）
- 操作：转班 / 重置密码 / 查看报告

## Tasks

- [ ] 6.1 学生列表：搜索框 + 班级下拉筛选 + 分页
- [ ] 6.2 学生详情弹窗（Modal，800px 宽）
- [ ] 6.3 弹窗-学情概览：最近成绩 + 练习正确率 + 完成次数
- [ ] 6.4 弹窗-进步趋势：简单折线图（纯 CSS/SVG）
- [ ] 6.5 弹窗-障碍诊断：当前障碍类型 + 薄弱知识点
- [ ] 6.6 弹窗-操作：转班 / 重置密码 / 查看报告
- [ ] 6.7 删除 report.html + report.js + panel.html + panel.js
- [ ] 6.8 验证：搜索→点击学生→详情弹窗全部信息正确

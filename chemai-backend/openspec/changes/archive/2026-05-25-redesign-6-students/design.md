## Design: 学生管理

### 架构
重写 students.html + students.js，合并 report/panel 功能到详情弹窗。

### 详情弹窗结构（4个区块）
1. 学情概览：练习次数/正确率/最近考试得分/班级排名
2. 进步趋势：最近N次考试的折线图（纯SVG）
3. 障碍诊断：当前障碍类型 + 薄弱知识点
4. 操作区：转班/重置密码/查看报告/生成学习计划

### API 扩展
- `POST /api/users/student/{id}/reset-password` — 重置学生密码

### 数据流
- 学生列表: GET /api/users/students → 前端搜索/筛选/分页
- 详情: GET /api/users/students + /api/diagnosis/plan/{id} + /api/diagnosis/history/{id}

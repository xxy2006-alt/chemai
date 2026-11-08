## 1. teacher.html 瘦身

- [x] 1.1 删除底部学生列表表格（`<table class="data-table">` 和相关 `<tbody>`）
- [x] 1.2 删除学生详情弹窗（`#studentModal` 和 `showStudentDetail`/`closeStudentModal` 函数）
- [x] 1.3 删除 `renderStudentTable` 函数调用和相关 mock 数据依赖
- [x] 1.4 新增「重点关注学生」精选卡片横条组件（HTML + CSS + JS 渲染逻辑）
- [x] 1.5 新增从 mockPanelData/mockStudentsData 提取 top 5 需关注学生的逻辑
- [x] 1.6 卡片点击跳转到 `/pages/students.html`

## 2. students.html 页面结构重写

- [x] 2.1 替换页面 HTML 结构：统计条 + 工具栏 + 卡片网格容器 + Drawer + 弹窗
- [x] 2.2 实现班级概览统计条（4 KPI 卡片：总人数/活跃/需关注/平均练习次数）
- [x] 2.3 实现工具栏：搜索输入框 + 班级下拉筛选 + 障碍类型下拉筛选 + 添加学生按钮
- [x] 2.4 保持侧边栏和页面标题结构不变，视觉风格对齐实验室笔记本主题

## 3. 学生卡片网格

- [x] 3.1 实现 `cardHTML(student)` 函数，CSS Grid 响应式布局
- [x] 3.2 每张卡片渲染：头像首字母圆、姓名、班级、障碍类型色标 tag、练习次数、最后活跃日期
- [x] 3.3 实现多维度筛选逻辑（姓名搜索、班级过滤、障碍类型过滤）
- [x] 3.4 实现分页（每页 12 张卡片，页码导航）
- [x] 3.5 实现空状态占位（无匹配学生时展示）
- [x] 3.6 实现 mock 数据降级（API 失败时自动使用 mockStudentsData）

## 4. Drawer 详情面板

- [x] 4.1 实现右侧滑出 Drawer 容器（480px 宽，backdrop overlay，CSS transition 动画）
- [x] 4.2 实现学生信息头部：姓名、班级、操作按钮（转班/重置密码/生成学习计划）
- [x] 4.3 实现学习统计 KPI 卡片行（练习次数、正确率、趋势箭头、最后活跃）
- [x] 4.4 实现障碍诊断三维分布条（概念/审题/表述 百分比色条）
- [x] 4.5 实现成绩趋势迷你折线图（Chart.js，160px 高，无坐标轴标签）
- [x] 4.6 实现薄弱知识点标签列表
- [x] 4.7 实现最近活动时间线（最多 5 条）
- [x] 4.8 实现空数据状态占位（各区块独立处理缺失数据）
- [x] 4.9 Drawer 关闭逻辑（backdrop 点击、× 按钮、ESC 键）

## 5. 添加学生弹窗

- [x] 5.1 实现添加学生 Modal（居中弹窗，backdrop overlay）
- [x] 5.2 实现手动输入模式：姓名 input + 班级下拉
- [x] 5.3 实现表单验证（姓名不能为空，班级必须选择）
- [x] 5.4 实现提交逻辑（调用 API 创建学生，成功后刷新列表并关闭弹窗）
- [x] 5.5 实现邀请码模式（Tab 切换 + 班级选择 + 生成/展示/复制邀请码 + API 回退本地生成）

## 6. students.js 重构

- [x] 6.1 保留现有 API 调用函数（`getToken`, `api`）
- [x] 6.2 保留转班弹窗逻辑
- [x] 6.3 重构数据加载流程：统一入口 → 渲染统计条 → 渲染卡片网格
- [x] 6.4 新增 Drawer 状态管理（当前选中学生、打开/关闭）
- [x] 6.5 复用 mockStudentsData 函数（在 students.js 中独立实现）
- [x] 6.6 保留 mock 数据 badge 显示逻辑

## 7. 联动与验证

- [x] 7.1 teacher.html 重点关注学生卡片点击 → 跳转 students.html + sessionStorage 传参自动打开 Drawer
- [x] 7.2 students.html 详情 Drawer 中转班按钮 → 打开转班弹窗
- [x] 7.3 浏览器验证：桌面端 3+ 列卡片（240px minmax）、移动端 1 列（@media 600px）
- [x] 7.4 验证无真实 API 时 mock 数据完整展示
- [x] 7.5 验证 sidebar 导航 teacher/students 两项均正确激活（app.js 已配置）
